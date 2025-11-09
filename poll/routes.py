# poll/routes.py
from __future__ import annotations

import os
from flask import render_template, request, redirect, url_for, flash, abort, current_app, jsonify, send_file
from datetime import datetime, timezone

from flask_login import login_required, current_user
from sqlalchemy import select, asc, func, or_
from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import Poll, Ballot, BallotItem, Team, User, DefaultBallot
from utils.logo_map import logo_map

from . import bp  # your Blueprint: bp = Blueprint("poll", __name__, url_prefix="/poll")

from typing import Optional

import io
from PIL import Image, ImageDraw, ImageFont

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


# -------------------------
# Vote form (optionally for a specific poll_id)
# -------------------------
@bp.get("/vote")
@bp.get("/polls/<int:poll_id>/vote")
@login_required
def vote_form(poll_id: Optional[int] = None):
    with SessionLocal() as s:
        if poll_id is not None:
            poll = s.get(Poll, poll_id)
            if not poll:
                flash("Poll not found.", "warning")
                return redirect(url_for("poll.poll_list"))
            if not poll.is_open:
                flash("That poll is closed to voting.", "info")
                return redirect(url_for("poll.results", poll_id=poll.id))
        else:
            # Fallback: latest open poll
            poll = (
                s.execute(
                    select(Poll).where(Poll.is_open == True)
                    .order_by(Poll.season.desc(), Poll.week.desc())
                ).scalars().first()
            )
            if not poll:
                flash("No open poll.", "warning")
                return redirect(url_for("poll.dashboard"))

        # Ensure the user has a ballot row for THIS poll
        ballot = (
            s.execute(
                select(Ballot).where(Ballot.poll_id == poll.id, Ballot.user_id == current_user.id)
            ).scalars().first()
        )
        if not ballot:
            ballot = Ballot(poll_id=poll.id, user_id=current_user.id)
            s.add(ballot)
            s.commit()
            s.refresh(ballot)

        teams = s.execute(select(Team).order_by(asc(Team.name))).scalars().all()

        items = s.execute(
            select(BallotItem).where(BallotItem.ballot_id == ballot.id)
        ).scalars().all()
        rank_map = {it.rank: it.team_id for it in items}

        defaults_rows = s.execute(
            select(DefaultBallot)
            .where(or_(DefaultBallot.poll_id == poll.id, DefaultBallot.poll_id.is_(None)))
            .order_by(DefaultBallot.rank.asc())
        ).scalars().all()
        default_rank_map = {row.rank: row.team_id for row in defaults_rows}

    return render_template(
        "poll_vote.html",
        poll=poll,
        teams=teams,
        rank_map=rank_map,
        default_rank_map=default_rank_map,
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

# -------------------------
# Poll list (all polls)
# -------------------------
@bp.get("/polls")
@login_required
def poll_list():
    with SessionLocal() as s:
        polls = (
            s.execute(
                select(Poll).order_by(Poll.season.desc(), Poll.week.desc())
            ).scalars().all()
        )
    return render_template("poll_list.html", polls=polls)

# -------------------------
# Results (optionally for a specific poll_id)
# -------------------------
@bp.get("/results")
@bp.get("/polls/<int:poll_id>/results")
@login_required
def results(poll_id: Optional[int] = None):
    with SessionLocal() as s:
        if poll_id is not None:
            poll = s.get(Poll, poll_id)
            if not poll:
                flash("Poll not found.", "warning")
                return redirect(url_for("poll.poll_list"))
        else:
            # Prefer currently open poll, else latest past
            poll = (
                s.execute(
                    select(Poll).order_by(Poll.is_open.desc(), Poll.season.desc(), Poll.week.desc())
                ).scalars().first()
            )
            if not poll:
                flash("No polls yet.", "warning")
                return redirect(url_for("poll.dashboard"))

        ballots = (
            s.execute(
                select(Ballot)
                .where(Ballot.poll_id == poll.id, Ballot.submitted_at.isnot(None))
                .order_by(Ballot.id.asc())
            )
            .scalars()
            .all()
        )

        if not ballots:
            return render_template(
                "poll_results.html",
                poll=poll,
                top_rows=[],
                others=[],
                logo_map=logo_map,
                submitters=[],
                stats={
                    "deviant_ballots": [],
                    "most_different_pair": None,
                    "pair_differences": [],
                    "team_consistency": [],
                },
                voter_grid=[]
            )

        # --- the rest of your existing results() logic stays the same below ---
        # (unchanged code from your current results() starting at "ballot_full = (...)" all the way to the render_template)
        # TIP: paste your existing block here without modification.
        # ----- BEGIN unchanged block -----
        from sqlalchemy.orm import joinedload
        ballot_full = (
            s.execute(
                select(Ballot)
                .options(joinedload(Ballot.items), joinedload(Ballot.user))
                .where(Ballot.id.in_([b.id for b in ballots]))
                .order_by(Ballot.id.asc())
            )
            .unique()
            .scalars()
            .all()
        )

        team_rows = s.execute(select(Team)).scalars().all()
        TEAM_NAME = {t.id: t.name for t in team_rows}

        from collections import defaultdict
        team_ranks_all = defaultdict(list)
        voter_maps = []
        submitters = []

        for b in ballot_full:
            voter_name = b.user.username if (b.user and b.user.username) else f"User {b.user_id}"
            submitters.append(voter_name)
            rmap = {it.team_id: it.rank for it in sorted(b.items, key=lambda x: x.rank)}
            voter_maps.append({"voter_name": voter_name, "ranks": rmap})
            for tid, rk in rmap.items():
                team_ranks_all[tid].append(rk)

        def points(rank: int) -> int:
            return max(0, (MAX_RANK + 1) - int(rank))

        agg = {}
        firsts = defaultdict(int)
        appearances = defaultdict(int)
        for vm in voter_maps:
            for tid, rk in vm["ranks"].items():
                agg.setdefault(tid, 0)
                agg[tid] += points(rk)
                appearances[tid] += 1
                if rk == 1:
                    firsts[tid] += 1

        rows = []
        for tid, pts in agg.items():
            rows.append({
                "team_id": tid,
                "team": TEAM_NAME.get(tid, f"Team {tid}"),
                "points": pts,
                "firsts": firsts.get(tid, 0),
                "appearances": appearances.get(tid, 0),
            })
        rows.sort(key=lambda r: (-r["points"], -r["firsts"], r["team"]))

        defaults_rows = s.execute(
            select(DefaultBallot)
            .where(or_(DefaultBallot.poll_id == poll.id, DefaultBallot.poll_id.is_(None)))
            .order_by(DefaultBallot.rank.asc())
        ).scalars().all()
        DEFAULT_BY_TEAM = {r.team_id: r.rank for r in defaults_rows}

        import math
        enriched = []
        for idx, r in enumerate(rows, start=1):
            tid = r["team_id"]
            ranks = team_ranks_all.get(tid, [])
            if ranks:
                mn = min(ranks); mx = max(ranks)
                mean = sum(ranks) / len(ranks)
                var = sum((rk - mean) ** 2 for rk in ranks) / len(ranks)
                stddev = math.sqrt(var)
            else:
                mn = mx = stddev = None

            default_rank = DEFAULT_BY_TEAM.get(tid)
            group_rank = idx
            delta = (default_rank - group_rank) if default_rank is not None else None

            enriched.append({
                **r,
                "group_rank": group_rank,
                "default_rank": default_rank,
                "delta_vs_default": delta,
                "min_rank": mn,
                "max_rank": mx,
                "stddev_rank": stddev,
            })

        top_rows = enriched[:MAX_RANK]
        others = [{"team": r["team"], "points": r["points"]} for r in enriched[MAX_RANK:] if r["points"] > 0]
        others.sort(key=lambda x: x["points"], reverse=True)

        UNRANKED = MAX_RANK + 1
        def footrule(vmap, cmap):
            all_ids = set(vmap.keys()) | set(cmap.keys())
            return sum(abs(vmap.get(t, UNRANKED) - cmap.get(t, UNRANKED)) for t in all_ids)

        consensus_map = {r["team_id"]: r["group_rank"] for r in top_rows}

        deviant_ballots = []
        for vm in voter_maps:
            dist = footrule(vm["ranks"], consensus_map)
            deviant_ballots.append({"voter_name": vm["voter_name"], "deviation": dist})
        deviant_ballots.sort(key=lambda x: x["deviation"], reverse=True)

        most_different_pair = None
        pair_differences = []
        best_dist = -1
        for i in range(len(voter_maps)):
            for j in range(i + 1, len(voter_maps)):
                A = voter_maps[i]; B = voter_maps[j]
                d = footrule(A["ranks"], B["ranks"])
                if d > best_dist:
                    best_dist = d
                    most_different_pair = {"a": A["voter_name"], "b": B["voter_name"], "distance": d}
                    diffs = []
                    union_ids = set(A["ranks"].keys()) | set(B["ranks"].keys())
                    for tid in union_ids:
                        ra = A["ranks"].get(tid, UNRANKED)
                        rb = B["ranks"].get(tid, UNRANKED)
                        diffs.append({
                            "team_id": tid,
                            "team": TEAM_NAME.get(tid, f"Team {tid}"),
                            "rank_a": ra if ra != UNRANKED else None,
                            "rank_b": rb if rb != UNRANKED else None,
                            "abs_diff": abs(ra - rb),
                        })
                    diffs.sort(key=lambda x: (-x["abs_diff"], x["team"]))
                    pair_differences = diffs[:10]

        MIN_APPS = 2
        team_consistency = [
            {
                "team_id": r["team_id"],
                "team": r["team"],
                "stddev": (r["stddev_rank"] if r["stddev_rank"] is not None else 0.0),
                "min_rank": r["min_rank"],
                "max_rank": r["max_rank"],
            }
            for r in enriched if r["appearances"] > MIN_APPS
        ]
        team_consistency.sort(key=lambda x: x["stddev"])
        team_volatile = sorted(team_consistency, key=lambda x: x["stddev"], reverse=True)

    return render_template(
        "poll_results.html",
        poll=poll,
        top_rows=top_rows,
        others=others,
        submitters=submitters,
        logo_map=logo_map,
        stats={
            "deviant_ballots": deviant_ballots,
            "most_different_pair": most_different_pair,
            "pair_differences": pair_differences,
            "team_consistency": team_consistency,
            "team_volatile": team_volatile,
        },
        voter_grid=voter_grid
    )
    # ----- END unchanged block -----


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


# --- helper: safe font load ---
def _load_font(size:int):
    # Try a bundled font first; fall back to default.
    try:
        font_path = os.path.join(current_app.static_folder, "fonts", "Inter-SemiBold.ttf")
        return ImageFont.truetype(font_path, size)
    except Exception:
        try:
            # DejaVu is often available on Heroku/Pillow builds
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

# --- helper: load & fit logo ---
def _load_team_logo(team_name:str, logo_map:dict, size:int=180) -> Image.Image:
    fname = logo_map.get(team_name)
    if fname:
        path = os.path.join(current_app.static_folder, "logos", fname)
    else:
        path = os.path.join(current_app.static_folder, "logos", "default.png")

    try:
        im = Image.open(path).convert("RGBA")
    except Exception:
        im = Image.open(os.path.join(current_app.static_folder, "logos", "default.png")).convert("RGBA")

    # fit within size x size preserving aspect
    im.thumbnail((size, size))
    # paste onto square canvas (to center)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ox = (size - im.width) // 2
    oy = (size - im.height) // 2
    canvas.paste(im, (ox, oy), im)
    return canvas

# --- main: render a shareable PNG of a ballot ---
@bp.get("/ballot/<int:ballot_id>/share.png")
@login_required
def share_ballot_png(ballot_id:int):
    with SessionLocal() as s:
        # load ballot, ensure owner or admin can view
        ballot = s.get(Ballot, ballot_id)
        if not ballot:
            abort(404)
        if ballot.user_id != current_user.id and not getattr(current_user, "is_admin", False):
            abort(403)

        poll = s.get(Poll, ballot.poll_id)
        user = s.get(User, ballot.user_id)

        # get items ordered by rank and join team names
        items = (
            s.execute(
                select(BallotItem)
                .where(BallotItem.ballot_id == ballot.id)
                .order_by(BallotItem.rank.asc())
            )
            .scalars()
            .all()
        )
        team_ids = [it.team_id for it in items]
        teams = {}
        if team_ids:
            for t in s.execute(select(Team).where(Team.id.in_(team_ids))).scalars().all():
                teams[t.id] = t.name

    # canvas config
    W, H = 1200, 1600                  # tall share card (mobile friendly)
    M = 48                              # outer margin
    GRID_W, GRID_H = W - 2*M, H - 420   # reserve ~420px for header/footer
    COLS, ROWS = 5, 5
    CELL_W = GRID_W // COLS
    CELL_H = GRID_H // ROWS

    # create background
    img = Image.new("RGB", (W, H), (12, 16, 26))  # dark panel
    draw = ImageDraw.Draw(img)

    # soft header panel
    header_h = 180
    draw.rounded_rectangle((M, M, W-M, M+header_h), radius=24, fill=(16, 20, 32))
    title_font = _load_font(52)
    sub_font   = _load_font(28)

    poll_title = poll.title if poll else "Poll"
    user_name  = user.username if user and user.username else f"User {ballot.user_id}"

    # title + subtitle
    draw.text((M+32, M+30), poll_title, fill=(234, 238, 247), font=title_font)
    draw.text((M+32, M+100), f"{user_name} • Ballot", fill=(168, 178, 198), font=sub_font)

    # grid background
    grid_top = M + header_h + 24
    draw.rounded_rectangle((M, grid_top, W-M, grid_top + GRID_H), radius=18, fill=(14, 18, 28), outline=(40, 48, 64))

    # render cells 1..25
    rank_font = _load_font(28)
    label_font = _load_font(26)

    for i in range(ROWS * COLS):
        r = i + 1
        # locate cell
        c_idx = i % COLS
        r_idx = i // COLS
        x0 = M + c_idx * CELL_W
        y0 = grid_top + r_idx * CELL_H
        x1 = x0 + CELL_W
        y1 = y0 + CELL_H

        # cell border
        draw.rectangle((x0, y0, x1, y1), outline=(40, 48, 64), width=1)

        # rank bubble
        bubble_r = 26
        bx = x0 + 20
        by = y0 + 18
        draw.ellipse((bx-bubble_r, by-bubble_r, bx+bubble_r, by+bubble_r), fill=(29, 36, 54))
        rw = draw.textlength(str(r), font=rank_font)
        draw.text((bx - rw/2, by - 18), str(r), fill=(200, 210, 230), font=rank_font)

        # logo + label if present
        if r <= len(items):
            team_name = teams.get(items[r-1].team_id, "—")
            logo = _load_team_logo(team_name, logo_map, size=160)

            # center logo
            lg_x = x0 + (CELL_W - logo.width) // 2
            lg_y = y0 + 20 + 40  # a bit lower than rank badge
            img.paste(logo, (lg_x, lg_y), logo)

            # team text (truncate if too long)
            label = team_name
            max_width = CELL_W - 24
            while draw.textlength(label, font=label_font) > max_width and len(label) > 3:
                label = label[:-2] + "…"
            tw = draw.textlength(label, font=label_font)
            draw.text((x0 + (CELL_W - tw)//2, y0 + CELL_H - 44), label, fill=(220, 226, 240), font=label_font)
        else:
            # empty placeholder
            dash_w = draw.textlength("—", font=label_font)
            draw.text((x0 + (CELL_W - dash_w)//2, y0 + CELL_H - 44), "—", fill=(90, 100, 120), font=label_font)

    # footer
    foot = "Generated with CLAAMP Polls"
    fw = draw.textlength(foot, font=sub_font)
    draw.text((W - M - fw, H - M - 8 - 28), foot, fill=(120, 132, 152), font=sub_font)

    # out
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=False, download_name="ballot.png")