# poll/routes.py
from __future__ import annotations

import os
from flask import render_template, request, redirect, url_for, flash, abort, current_app, jsonify
from datetime import datetime, timezone

from flask_login import login_required, current_user
from sqlalchemy import select, asc, func, or_
from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import Poll, Ballot, BallotItem, Team, User, DefaultBallot
from utils.logo_map import logo_map

from . import bp  # your Blueprint: bp = Blueprint("poll", __name__, url_prefix="/poll")


# -------------------------
# Config / helpers
# -------------------------
MAX_RANK = 25

# -------------------------
# Stats helpers (drop-in)
# -------------------------
from sqlalchemy.orm import joinedload

UNRANKED_RANK = 26  # treat unranked as 26 for distances/volatility

def _build_consensus(rows: list[dict]) -> tuple[dict[int,int], list[int]]:
    """
    From already-computed rows (sorted by points desc), build:
      - consensus_map: {team_id -> consensus rank}
      - consensus_ids: [team_id,...] top 25 in order
    """
    consensus_ids = [r["team_id"] for r in rows[:MAX_RANK]]
    consensus_map = {tid: i+1 for i, tid in enumerate(consensus_ids)}
    return consensus_map, consensus_ids

def _fetch_ballots_with_ranks(session, poll_id: int):
    """
    Returns a list of voters with their rank maps:
    [
      {"voter_name": str, "ranks": { team_id: rank, ... }},
      ...
    ]
    """
    ballots = (
        session.execute(
            select(Ballot)
            .options(
                joinedload(Ballot.items),   # eager-load items
                joinedload(Ballot.user),    # eager-load user
            )
            .where(Ballot.poll_id == poll_id, Ballot.submitted_at.isnot(None))
            .order_by(Ballot.id.asc())
        )
        .unique()
        .scalars()
        .all()
    )

    out = []
    for b in ballots:
        voter_name = b.user.username if (b.user and b.user.username) else f"User {b.user_id}"
        ranks = {it.team_id: it.rank for it in b.items}
        out.append({"voter_name": voter_name, "ranks": ranks})
    return out

def _spearman_footrule_distance(voter_ranks: dict[int,int], consensus_map: dict[int,int]) -> int:
    """
    Sum |rank_voter(t) - rank_consensus(t)| over the union of teams in
    the consensus top-25 and the voter ballot (unranked treated as UNRANKED_RANK).
    """
    all_ids = set(consensus_map.keys()) | set(voter_ranks.keys())
    total = 0
    for tid in all_ids:
        rv = voter_ranks.get(tid, UNRANKED_RANK)
        rc = consensus_map.get(tid, UNRANKED_RANK)
        total += abs(rv - rc)
    return total

def _compute_poll_stats(session, poll_id: int, rows: list[dict]) -> dict:
    """
    Build:
      - deviant_ballots: ballots sorted by deviation from consensus (desc = most deviant first)
      - rank_spread: per-team (max rank, min rank, spread)
      - rank_stddev: per-team rank std dev
    """
    import math
    from collections import defaultdict

    if not rows:
        return {"deviant_ballots": [], "rank_spread": [], "rank_stddev": [], "extra": []}

    consensus_map, _ = _build_consensus(rows)
    team_name = {r["team_id"]: r["team"] for r in rows}

    ballots = _fetch_ballots_with_ranks(session, poll_id)

    if not ballots:
        rows = []
        submitters = []
        stats = {"deviant_ballots": [], "rank_spread": [], "rank_stddev": [], "extra": []}
        return render_template(
            "poll_results.html",
            poll=poll,
            top25=[],
            others=[],
            submitters=submitters,
            logo_map=logo_map,
            stats=stats
        )

    # Deviant ballots by footrule distance (higher = more deviant)
    deviant = []
    for b in ballots:
        dist = _spearman_footrule_distance(b["ranks"], consensus_map)
        deviant.append({"voter_name": b["voter_name"], "deviation": dist})
    deviant.sort(key=lambda x: x["deviation"], reverse=True)

    # Team rank collections
    team_ranks = defaultdict(list)
    for b in ballots:
        for tid in team_name.keys():
            team_ranks[tid].append(b["ranks"].get(tid, UNRANKED_RANK))

    spread_rows, std_rows = [], []   # <-- fixed line

    for tid, ranks in team_ranks.items():
        if not ranks:
            continue
        mx, mn = max(ranks), min(ranks)
        spread = mx - mn
        mean = sum(ranks) / len(ranks)
        variance = sum((r - mean) ** 2 for r in ranks) / len(ranks)
        stddev = math.sqrt(variance)
        spread_rows.append({
            "team_id": tid,
            "team": team_name.get(tid, f"Team {tid}"),
            "max_rank": mx,
            "min_rank": mn,
            "spread": spread
        })
        std_rows.append({
            "team_id": tid,
            "team": team_name.get(tid, f"Team {tid}"),
            "stddev": stddev
        })

    spread_rows.sort(key=lambda x: x["spread"], reverse=True)
    std_rows.sort(key=lambda x: x["stddev"], reverse=True)

    extra = []  # add fun notes later

    return {
        "deviant_ballots": deviant,
        "rank_spread": spread_rows,
        "rank_stddev": std_rows,
        "extra": extra,
    }


def points(rank: int) -> int:
    return max(0, (MAX_RANK + 1) - int(rank))

def require_admin():
    if not (current_user.is_authenticated and getattr(current_user, "is_admin", False)):
        abort(403)


# -------------------------
# Routes
# -------------------------
@bp.get("/")
@login_required
def dashboard():
    with SessionLocal() as s:
        open_poll = s.execute(
            select(Poll).where(Poll.is_open == True).order_by(Poll.season.desc(), Poll.week.desc())
        ).scalars().first()

        latest_past = s.execute(
            select(Poll).where(Poll.is_open == False).order_by(Poll.season.desc(), Poll.week.desc())
        ).scalars().first()

        user_ballot = None
        if open_poll:
            user_ballot = s.execute(
                select(Ballot).where(Ballot.poll_id == open_poll.id, Ballot.user_id == current_user.id)
            ).scalars().first()

    return render_template(
        "poll_index.html",
        open_poll=open_poll,
        latest_past_poll=latest_past,
        user_ballot=user_ballot
    )


@bp.get("/vote")
@login_required
def vote_form():
    with SessionLocal() as s:
        # Get latest open poll
        poll = s.execute(
            select(Poll).where(Poll.is_open == True).order_by(Poll.season.desc(), Poll.week.desc())
        ).scalars().first()

        if not poll:
            flash("No open poll.", "warning")
            return redirect(url_for("poll.dashboard"))

        # Ensure the user has a ballot row
        ballot = s.execute(
            select(Ballot).where(Ballot.poll_id == poll.id, Ballot.user_id == current_user.id)
        ).scalars().first()
        if not ballot:
            ballot = Ballot(poll_id=poll.id, user_id=current_user.id)
            s.add(ballot)
            s.commit()
            s.refresh(ballot)

        # Teams for palette
        teams = s.execute(select(Team).order_by(asc(Team.name))).scalars().all()

        # Build rank map for the user's existing ballot
        items = s.execute(
            select(BallotItem).where(BallotItem.ballot_id == ballot.id)
        ).scalars().all()
        rank_map = {it.rank: it.team_id for it in items}

        # ---- NEW: fetch committee defaults (prefer poll-specific, else global) ----
        defaults_rows = s.execute(
            select(DefaultBallot)
            .where(
                or_(
                    DefaultBallot.poll_id == poll.id,
                    DefaultBallot.poll_id.is_(None),
                )
            )
            .order_by(DefaultBallot.rank.asc())
        ).scalars().all()

        default_rank_map = {row.rank: row.team_id for row in defaults_rows}

    # Build logo map from /static/logos (you already import logo_map)
    return render_template(
        "poll_vote.html",
        poll=poll,
        teams=teams,
        rank_map=rank_map,
        default_rank_map=default_rank_map,   # <-- pass it in
        MAX_RANK=MAX_RANK,
        logo_map=logo_map
    )



@bp.post("/vote")
@login_required
def submit_vote():
    with SessionLocal() as s:
        poll = s.execute(
            select(Poll).where(Poll.is_open == True).order_by(Poll.season.desc(), Poll.week.desc())
        ).scalars().first()
        if not poll:
            flash("No open poll.", "warning")
            return redirect(url_for("poll.dashboard"))

        ballot = s.execute(
            select(Ballot).where(Ballot.poll_id == poll.id, Ballot.user_id == current_user.id)
        ).scalars().first()
        if not ballot:
            ballot = Ballot(poll_id=poll.id, user_id=current_user.id)
            s.add(ballot)
            s.flush()

        # Collect ranks from form (rank_1..rank_25)
        chosen: dict[int, int] = {}
        seen: set[int] = set()
        for r in range(1, MAX_RANK + 1):
            team_id = request.form.get(f"rank_{r}", type=int)
            if team_id:
                if team_id in seen:
                    flash("Duplicate team in your ballot.", "danger")
                    return redirect(url_for("poll.vote_form"))
                seen.add(team_id)
                chosen[r] = team_id

        if not chosen:
            flash("Select at least one team.", "warning")
            return redirect(url_for("poll.vote_form"))

        # Replace ballot items
        s.query(BallotItem).filter(BallotItem.ballot_id == ballot.id).delete()
        for r, t in chosen.items():
            s.add(BallotItem(ballot_id=ballot.id, rank=r, team_id=t))

        ballot.submitted_at = datetime.now(timezone.utc)

        try:
            s.commit()
            flash("Ballot submitted!", "success")
        except IntegrityError:
            s.rollback()
            flash("Save conflict. Try again.", "danger")

    return redirect(url_for("poll.dashboard"))

@bp.get("/api/polls/<int:poll_id>/default")
@login_required
def api_poll_default(poll_id):
    """Return the current default map {rank: team_id}.
       If you seeded with poll_id=None, we fall back to global defaults.
       If you seeded with a week_key, you can pick the latest, or pass one via query param later.
    """
    week_key = None  # simple version: latest by id if multiple exist

    with SessionLocal() as s:
        q = select(DefaultBallot).where(
            or_(
                DefaultBallot.poll_id == poll_id,
                DefaultBallot.poll_id.is_(None)
            )
        )
        if week_key:
            q = q.where(DefaultBallot.week_key == week_key)
        q = q.order_by(DefaultBallot.rank)

        rows = s.scalars(q).all()
        payload = {str(r.rank): r.team_id for r in rows}

    return jsonify(payload)

@bp.get("/results")
@login_required
def results():
    with SessionLocal() as s:
        # Prefer currently open poll, else latest
        poll = s.execute(
            select(Poll).order_by(Poll.is_open.desc(), Poll.season.desc(), Poll.week.desc())
        ).scalars().first()

        if not poll:
            flash("No polls yet.", "warning")
            return redirect(url_for("poll.dashboard"))

        ballots = s.execute(
            select(Ballot).where(Ballot.poll_id == poll.id, Ballot.submitted_at.isnot(None))
        ).scalars().all()

        # Aggregate points
        agg: dict[int, dict[str, int]] = {}
        for b in ballots:
            for it in b.items:
                info = agg.setdefault(it.team_id, {"points": 0, "firsts": 0, "apps": 0})
                info["points"] += points(it.rank)
                info["apps"] += 1
                if it.rank == 1:
                    info["firsts"] += 1

        rows = []
        if agg:
            teams = s.execute(select(Team).where(Team.id.in_(list(agg.keys())))).scalars().all()
            names = {t.id: t.name for t in teams}
            for tid, info in agg.items():
                rows.append({
                    "team_id": tid,
                    "team": names.get(tid, f"Team {tid}"),
                    "points": info["points"],
                    "firsts": info["firsts"],
                    "appearances": info["apps"]
                })
            rows.sort(key=lambda r: (-r["points"], -r["firsts"], r["team"]))

        # Build Top 25 + Others receiving votes
        top25 = rows[:MAX_RANK]
        others = [{"team": r["team"], "points": r["points"]} for r in rows[MAX_RANK:] if r["points"] > 0]
        others.sort(key=lambda x: x["points"], reverse=True)

        # Submitters (as before)
        submitters = s.execute(
            select(User.username)
            .join(Ballot, Ballot.user_id == User.id)
            .where(Ballot.poll_id == poll.id, Ballot.submitted_at.isnot(None))
            .order_by(User.username.asc())
        ).scalars().all()

        # Stats / fun stuff
        stats = _compute_poll_stats(s, poll.id, rows)

    return render_template(
        "poll_results.html",
        poll=poll,
        top25=top25,
        others=others,
        submitters=submitters,
        logo_map=logo_map,
        stats=stats
    )


@bp.get("/admin")
@login_required
def admin_panel():
    require_admin()
    with SessionLocal() as s:
        polls = s.execute(
            select(Poll).order_by(Poll.season.desc(), Poll.week.desc())
        ).scalars().all()
        team_count = s.execute(select(func.count(Team.id))).scalar_one()

    return render_template("poll_admin.html", polls=polls, team_count=team_count)


@bp.post("/admin/new")
@login_required
def admin_new_poll():
    require_admin()

    season = request.form.get("season", type=int)
    week = request.form.get("week", type=int)
    title = request.form.get("title", "").strip()

    if not (season and week and title):
        flash("Season, week, title required.", "danger")
        return redirect(url_for("poll.admin_panel"))

    with SessionLocal() as s:
        p = Poll(season=season, week=week, title=title, is_open=True)
        s.add(p)
        try:
            s.commit()
            flash(f"Opened {season} W{week}.", "success")
        except IntegrityError:
            s.rollback()
            flash("Poll already exists for that week.", "danger")

    return redirect(url_for("poll.admin_panel"))


@bp.post("/admin/close/<int:poll_id>")
@login_required
def admin_close_poll(poll_id: int):
    require_admin()
    with SessionLocal() as s:
        p = s.get(Poll, poll_id)
        if not p:
            flash("Poll not found.", "warning")
        else:
            p.is_open = False
            s.commit()
            flash("Poll closed.", "success")

    return redirect(url_for("poll.admin_panel"))


@bp.post("/admin/teams/seed")
@login_required
def admin_seed_teams():
    require_admin()
    defaults = [
        "Georgia", "Ohio State", "Michigan", "Texas", "Alabama", "Oregon", "Notre Dame", "Washington",
        "Florida State", "Penn State", "Ole Miss", "LSU", "Tennessee", "Oklahoma", "Utah", "Kansas State",
        "Missouri", "Clemson", "Arizona", "Louisville", "Iowa", "North Carolina", "USC", "Miami (FL)", "Liberty"
    ]

    with SessionLocal() as s:
        existing = {t.name for t in s.execute(select(Team)).scalars()}
        for name in defaults:
            if name not in existing:
                s.add(Team(name=name))
        s.commit()

    flash("Seeded teams.", "success")
    return redirect(url_for("poll.admin_panel"))
