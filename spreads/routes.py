# spreads/routes.py
from __future__ import annotations

from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import pytz

from flask_login import login_required, current_user
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import SpreadPoll, SpreadGame, SpreadPick, Team, User
from utils.logo_map import logo_map

from . import bp


# -------------------------
# Helper Functions
# -------------------------

def require_admin():
    """Ensure current user is admin"""
    if not (current_user.is_authenticated and getattr(current_user, "is_admin", False)):
        abort(403)


def game_is_locked(game_time):
    """Check if game is locked (started or within 5 minutes of start)
    Handles both timezone-aware and timezone-naive datetimes"""
    if not game_time:
        return False
    # Get current time in UTC and convert to ET (naive, -5 hours for EST)
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc - timedelta(hours=5)
    now_et = now_et.replace(tzinfo=None)

    # Handle timezone-aware game_time from old data
    if game_time.tzinfo is not None:
        # Convert to naive ET time (subtract 5 hours from UTC)
        game_time = game_time.astimezone(timezone.utc) - timedelta(hours=5)
        game_time = game_time.replace(tzinfo=None)

    # Lock picks 5 minutes before game starts
    lock_time = game_time - timedelta(minutes=5)
    return now_et >= lock_time


def is_valid_weekend_game(game_time):
    """Check if game is scheduled for Nov 14 or 15, 2024"""
    if not game_time:
        return False

    # Handle timezone-aware datetimes
    if game_time.tzinfo is not None:
        game_time = game_time.astimezone(timezone.utc) - timedelta(hours=5)
        game_time = game_time.replace(tzinfo=None)

    # Check if it's November 14 or 15
    return game_time.month == 11 and game_time.day in (14, 15)


def get_latest_open_poll(session):
    """Get the most recent open SpreadPoll"""
    return session.execute(
        select(SpreadPoll)
        .where(SpreadPoll.is_open == True)
        .order_by(SpreadPoll.season.desc(), SpreadPoll.week.desc())
    ).scalar_one_or_none()


def get_latest_poll(session):
    """Get the most recent SpreadPoll (open or closed)"""
    return session.execute(
        select(SpreadPoll)
        .order_by(SpreadPoll.season.desc(), SpreadPoll.week.desc())
    ).scalar_one_or_none()


# -------------------------
# Routes
# -------------------------

@bp.get("/")
@login_required
def dashboard():
    """Spreads dashboard - list of all spread polls"""
    session = SessionLocal()
    try:
        polls = session.execute(
            select(SpreadPoll)
            .order_by(SpreadPoll.season.desc(), SpreadPoll.week.desc())
        ).scalars().all()

        # Get user's pick counts for each poll
        poll_data = []
        for poll in polls:
            # Count games in this poll
            game_count = session.execute(
                select(func.count(SpreadGame.id))
                .where(SpreadGame.spread_poll_id == poll.id)
            ).scalar()

            # Count user's picks
            user_pick_count = 0
            if current_user.is_authenticated:
                user_pick_count = session.execute(
                    select(func.count(SpreadPick.id))
                    .where(
                        SpreadPick.spread_poll_id == poll.id,
                        SpreadPick.user_id == current_user.id
                    )
                ).scalar()

            poll_data.append({
                'poll': poll,
                'game_count': game_count,
                'user_pick_count': user_pick_count,
            })

        return render_template(
            "spreads_dashboard.html",
            poll_data=poll_data,
            logo_map=logo_map
        )
    finally:
        session.close()


@bp.get("/vote")
@login_required
def vote_latest():
    """Redirect to vote page for latest open poll"""
    session = SessionLocal()
    try:
        poll = get_latest_open_poll(session)
        if not poll:
            flash("No open spread polls available.", "warning")
            return redirect(url_for("spreads.dashboard"))
        return redirect(url_for("spreads.vote", season=poll.season, week=poll.week))
    finally:
        session.close()


@bp.get("/week/<int:season>/<int:week>")
@login_required
def vote(season: int, week: int):
    """Vote page for a specific week's spread poll"""
    session = SessionLocal()
    try:
        poll = session.execute(
            select(SpreadPoll)
            .where(SpreadPoll.season == season, SpreadPoll.week == week)
        ).scalar_one_or_none()

        if not poll:
            flash(f"No spread poll found for Season {season}, Week {week}.", "danger")
            return redirect(url_for("spreads.dashboard"))

        # Load games with teams
        games = session.execute(
            select(SpreadGame)
            .options(
                joinedload(SpreadGame.home_team),
                joinedload(SpreadGame.away_team)
            )
            .where(SpreadGame.spread_poll_id == poll.id)
            .order_by(SpreadGame.game_time.asc())
        ).unique().scalars().all()

        # Filter to only Nov 14-15 games with valid spreads
        games = [
            game for game in games
            if is_valid_weekend_game(game.game_time)
            and game.home_spread and game.home_spread != 'N/A'
            and game.away_spread and game.away_spread != 'N/A'
        ]

        # Load user's existing picks
        user_picks = {}
        if current_user.is_authenticated:
            picks = session.execute(
                select(SpreadPick)
                .where(
                    SpreadPick.spread_poll_id == poll.id,
                    SpreadPick.user_id == current_user.id
                )
            ).scalars().all()

            user_picks = {pick.spread_game_id: pick for pick in picks}

        # Group games by day
        games_by_day = defaultdict(list)
        for game in games:
            day = game.game_day or "Saturday"
            games_by_day[day].append(game)

        return render_template(
            "spreads_vote.html",
            poll=poll,
            games_by_day=games_by_day,
            user_picks=user_picks,
            logo_map=logo_map,
            game_is_locked=game_is_locked,
            now_utc=datetime.now(timezone.utc)
        )
    finally:
        session.close()


@bp.post("/vote")
@login_required
def submit_vote():
    """Submit picks for a spread poll"""
    session = SessionLocal()
    try:
        poll_id = request.form.get("poll_id", type=int)
        if not poll_id:
            flash("Invalid poll.", "danger")
            return redirect(url_for("spreads.dashboard"))

        poll = session.get(SpreadPoll, poll_id)
        if not poll:
            flash("Poll not found.", "danger")
            return redirect(url_for("spreads.dashboard"))

        if not poll.is_open:
            flash("This poll is closed.", "warning")
            return redirect(url_for("spreads.results", season=poll.season, week=poll.week))

        # Get all games for this poll
        games = session.execute(
            select(SpreadGame)
            .where(SpreadGame.spread_poll_id == poll_id)
        ).scalars().all()

        # Process picks
        picks_saved = 0
        skipped_locked = 0
        for game in games:
            # Skip games that have started or are about to start (5 min buffer)
            if game_is_locked(game.game_time):
                skipped_locked += 1
                continue

            # Form field: pick_game_{game.id} = team_id
            picked_team_id = request.form.get(f"pick_game_{game.id}", type=int)

            if not picked_team_id:
                # User didn't pick this game - delete any existing pick
                session.execute(
                    select(SpreadPick)
                    .where(
                        SpreadPick.spread_poll_id == poll_id,
                        SpreadPick.spread_game_id == game.id,
                        SpreadPick.user_id == current_user.id
                    )
                ).scalar_one_or_none()
                # If exists, delete it
                existing = session.execute(
                    select(SpreadPick)
                    .where(
                        SpreadPick.spread_poll_id == poll_id,
                        SpreadPick.spread_game_id == game.id,
                        SpreadPick.user_id == current_user.id
                    )
                ).scalar_one_or_none()
                if existing:
                    session.delete(existing)
                continue

            # Validate picked team is in this game
            if picked_team_id not in (game.home_team_id, game.away_team_id):
                flash(f"Invalid pick for game {game.id}.", "danger")
                continue

            # Determine spread value for this pick
            if picked_team_id == game.home_team_id:
                spread_value = game.home_spread
            else:
                spread_value = game.away_spread

            # Check if pick already exists
            existing = session.execute(
                select(SpreadPick)
                .where(
                    SpreadPick.spread_poll_id == poll_id,
                    SpreadPick.spread_game_id == game.id,
                    SpreadPick.user_id == current_user.id
                )
            ).scalar_one_or_none()

            if existing:
                # Update existing pick
                existing.picked_team_id = picked_team_id
                existing.spread_value = spread_value
                existing.picked_at = datetime.now(timezone.utc)
            else:
                # Create new pick
                pick = SpreadPick(
                    spread_poll_id=poll_id,
                    spread_game_id=game.id,
                    user_id=current_user.id,
                    picked_team_id=picked_team_id,
                    spread_value=spread_value
                )
                session.add(pick)

            picks_saved += 1

        session.commit()

        # Show message about locked games if any
        message = f"Picks saved! ({picks_saved} games)"
        if skipped_locked > 0:
            message += f" • {skipped_locked} game(s) locked (already started)"
        flash(message, "success")

        return redirect(url_for("spreads.dashboard"))

    except Exception as e:
        session.rollback()
        flash(f"Error saving picks: {e}", "danger")
        return redirect(url_for("spreads.dashboard"))
    finally:
        session.close()


@bp.get("/week/<int:season>/<int:week>/results")
@login_required
def results(season: int, week: int):
    """Results page for a specific week"""
    session = SessionLocal()
    try:
        poll = session.execute(
            select(SpreadPoll)
            .where(SpreadPoll.season == season, SpreadPoll.week == week)
        ).scalar_one_or_none()

        if not poll:
            flash(f"No spread poll found for Season {season}, Week {week}.", "danger")
            return redirect(url_for("spreads.dashboard"))

        # Load games with picks
        games = session.execute(
            select(SpreadGame)
            .options(
                joinedload(SpreadGame.home_team),
                joinedload(SpreadGame.away_team),
                joinedload(SpreadGame.picks).joinedload(SpreadPick.user)
            )
            .where(SpreadGame.spread_poll_id == poll.id)
            .order_by(SpreadGame.game_time.asc())
        ).unique().scalars().all()

        # Filter to only Nov 14-15 games with valid spreads
        games = [
            game for game in games
            if is_valid_weekend_game(game.game_time)
            and game.home_spread and game.home_spread != 'N/A'
            and game.away_spread and game.away_spread != 'N/A'
        ]

        # Calculate user records
        user_records = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'pending': 0})

        for game in games:
            for pick in game.picks:
                if pick.is_correct is None:
                    user_records[pick.user_id]['pending'] += 1
                elif pick.is_correct:
                    user_records[pick.user_id]['correct'] += 1
                else:
                    user_records[pick.user_id]['incorrect'] += 1

        # Get users
        users = session.execute(select(User)).scalars().all()
        user_map = {u.id: u for u in users}

        # Build leaderboard
        leaderboard = []
        for user_id, record in user_records.items():
            user = user_map.get(user_id)
            if user:
                total = record['correct'] + record['incorrect']
                pct = (record['correct'] / total * 100) if total > 0 else 0
                leaderboard.append({
                    'user': user,
                    'correct': record['correct'],
                    'incorrect': record['incorrect'],
                    'pending': record['pending'],
                    'total': total,
                    'pct': pct
                })

        # Sort by correct picks, then by percentage
        leaderboard.sort(key=lambda x: (x['correct'], x['pct']), reverse=True)

        # Group games by day
        games_by_day = defaultdict(list)
        for game in games:
            day = game.game_day or "Saturday"
            games_by_day[day].append(game)

        return render_template(
            "spreads_results.html",
            poll=poll,
            games_by_day=games_by_day,
            leaderboard=leaderboard,
            logo_map=logo_map
        )
    finally:
        session.close()


@bp.get("/stats")
@login_required
def stats():
    """Overall statistics and leaderboards"""
    session = SessionLocal()
    try:
        # Get all users
        users = session.execute(select(User)).scalars().all()

        # Calculate overall stats for each user
        user_stats = []
        for user in users:
            # Total picks
            total_picks = session.execute(
                select(func.count(SpreadPick.id))
                .where(SpreadPick.user_id == user.id)
            ).scalar()

            # Correct picks
            correct_picks = session.execute(
                select(func.count(SpreadPick.id))
                .where(
                    SpreadPick.user_id == user.id,
                    SpreadPick.is_correct == True
                )
            ).scalar()

            # Incorrect picks
            incorrect_picks = session.execute(
                select(func.count(SpreadPick.id))
                .where(
                    SpreadPick.user_id == user.id,
                    SpreadPick.is_correct == False
                )
            ).scalar()

            # Pending picks
            pending_picks = session.execute(
                select(func.count(SpreadPick.id))
                .where(
                    SpreadPick.user_id == user.id,
                    SpreadPick.is_correct.is_(None)
                )
            ).scalar()

            graded_total = correct_picks + incorrect_picks
            pct = (correct_picks / graded_total * 100) if graded_total > 0 else 0

            if total_picks > 0:  # Only include users who have made picks
                user_stats.append({
                    'user': user,
                    'total_picks': total_picks,
                    'correct': correct_picks,
                    'incorrect': incorrect_picks,
                    'pending': pending_picks,
                    'graded_total': graded_total,
                    'pct': pct
                })

        # Sort by correct picks descending
        user_stats.sort(key=lambda x: (x['correct'], x['pct']), reverse=True)

        # Get all polls for weekly breakdown
        polls = session.execute(
            select(SpreadPoll)
            .order_by(SpreadPoll.season.desc(), SpreadPoll.week.desc())
        ).scalars().all()

        return render_template(
            "spreads_stats.html",
            user_stats=user_stats,
            polls=polls
        )
    finally:
        session.close()


@bp.get("/admin")
@login_required
def admin_panel():
    """Admin panel for spread polls"""
    require_admin()
    session = SessionLocal()
    try:
        polls = session.execute(
            select(SpreadPoll)
            .order_by(SpreadPoll.season.desc(), SpreadPoll.week.desc())
        ).scalars().all()

        # Get game counts for each poll
        poll_data = []
        for poll in polls:
            game_count = session.execute(
                select(func.count(SpreadGame.id))
                .where(SpreadGame.spread_poll_id == poll.id)
            ).scalar()

            pick_count = session.execute(
                select(func.count(SpreadPick.id))
                .where(SpreadPick.spread_poll_id == poll.id)
            ).scalar()

            poll_data.append({
                'poll': poll,
                'game_count': game_count,
                'pick_count': pick_count
            })

        return render_template(
            "spreads_admin.html",
            poll_data=poll_data
        )
    finally:
        session.close()


@bp.post("/admin/poll/<int:poll_id>/close")
@login_required
def close_poll(poll_id: int):
    """Close a spread poll"""
    require_admin()
    session = SessionLocal()
    try:
        poll = session.get(SpreadPoll, poll_id)
        if not poll:
            flash("Poll not found.", "danger")
            return redirect(url_for("spreads.admin_panel"))

        poll.is_open = False
        session.commit()
        flash(f"Closed {poll.title}.", "success")
        return redirect(url_for("spreads.admin_panel"))
    finally:
        session.close()


@bp.post("/admin/poll/<int:poll_id>/open")
@login_required
def open_poll(poll_id: int):
    """Re-open a spread poll"""
    require_admin()
    session = SessionLocal()
    try:
        poll = session.get(SpreadPoll, poll_id)
        if not poll:
            flash("Poll not found.", "danger")
            return redirect(url_for("spreads.admin_panel"))

        poll.is_open = True
        session.commit()
        flash(f"Opened {poll.title}.", "success")
        return redirect(url_for("spreads.admin_panel"))
    finally:
        session.close()
