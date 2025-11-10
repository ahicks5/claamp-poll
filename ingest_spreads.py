"""
Recurring script to ingest NCAA football spreads from Bovada.
Run this hourly via Heroku Scheduler or cron.

This script:
1. Fetches current week's NCAA football games from Bovada
2. Maps team names to our database teams
3. Creates/updates SpreadPoll for current week
4. Creates/updates SpreadGame records with latest spreads
5. Includes Friday and Saturday games
6. Converts times from UTC to Eastern Time
7. Stops updating spreads for games that have started
"""

from __future__ import annotations
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal
from models import Team, SpreadPoll, SpreadGame, BovadaTeamMapping
from utils.bovada_team_mapper import map_bovada_team
from utils.scrape_bovada import fetch_events_for_sport, fetch_event_node_by_link, extract_key_markets

SPORT = "football/college-football"

# Season/Week configuration
# You can adjust these or make them dynamic based on current date
CURRENT_SEASON = 2025
CURRENT_WEEK = 11  # Adjust this weekly

# Timezone for display (Eastern Time)
ET = pytz.timezone('America/New_York')


def utc_to_et(dt_utc: Optional[datetime]) -> Optional[datetime]:
    """Convert UTC datetime to Eastern Time by subtracting 5 hours
    (EST is UTC-5 in November)"""
    if not dt_utc:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    # Subtract 5 hours for Eastern Time and make timezone-naive
    et_time = dt_utc - timedelta(hours=5)
    return et_time.replace(tzinfo=None)


def get_day_of_week(dt: Optional[datetime]) -> Optional[str]:
    """Get day of week from datetime (in ET)"""
    if not dt:
        return None
    # Convert to ET first
    dt_et = utc_to_et(dt)
    return dt_et.strftime("%A") if dt_et else None


def is_weekend_game(dt: Optional[datetime]) -> bool:
    """Check if datetime is Friday 11/14 or Saturday 11/15"""
    if not dt:
        return False
    dt_et = utc_to_et(dt)
    if not dt_et:
        return False
    # Check if it's November 14 or 15
    return (dt_et.month == 11 and dt_et.day in (14, 15))


def game_has_started(game_time: Optional[datetime]) -> bool:
    """Check if game has already started (handles both naive and aware datetimes)"""
    if not game_time:
        return False
    # Get current time in UTC and convert to ET (naive)
    now_utc = datetime.now(timezone.utc)
    now_et = utc_to_et(now_utc)

    # Handle timezone-aware game_time from old data
    if game_time.tzinfo is not None:
        # Convert to naive ET time
        game_time = utc_to_et(game_time)

    return now_et >= game_time


def get_or_create_spread_poll(session: Session, season: int, week: int) -> SpreadPoll:
    """Get or create the SpreadPoll for this week"""
    poll = session.execute(
        select(SpreadPoll)
        .where(SpreadPoll.season == season, SpreadPoll.week == week)
    ).scalar_one_or_none()

    if poll is None:
        # Create new poll
        poll = SpreadPoll(
            season=season,
            week=week,
            title=f"Week {week} - Weekend Games",
            is_open=True,
            closes_at=None  # Can be set manually or calculated
        )
        session.add(poll)
        session.flush()
        print(f"[+] Created new SpreadPoll: Season {season}, Week {week}")
    else:
        print(f"[✓] Found existing SpreadPoll: Season {season}, Week {week}")

    return poll


def upsert_spread_game(
    session: Session,
    poll: SpreadPoll,
    bovada_event_id: str,
    home_team: Team,
    away_team: Team,
    home_spread: Optional[str],
    away_spread: Optional[str],
    game_time: Optional[datetime],
    game_day: Optional[str],
    status: Optional[str],
) -> SpreadGame:
    """Create or update a SpreadGame"""

    # Check if game already exists by bovada_event_id OR by team matchup
    existing = None

    if bovada_event_id:
        existing = session.execute(
            select(SpreadGame)
            .where(
                SpreadGame.spread_poll_id == poll.id,
                SpreadGame.bovada_event_id == bovada_event_id
            )
        ).scalar_one_or_none()

    if not existing:
        # Try to find by team matchup (in case bovada_event_id changed)
        existing = session.execute(
            select(SpreadGame)
            .where(
                SpreadGame.spread_poll_id == poll.id,
                SpreadGame.home_team_id == home_team.id,
                SpreadGame.away_team_id == away_team.id
            )
        ).scalar_one_or_none()

    if existing:
        # Update existing game, but DON'T update spreads if game has started
        has_started = game_has_started(existing.game_time)

        existing.bovada_event_id = bovada_event_id
        existing.game_time = game_time
        existing.game_day = game_day
        existing.status = status or 'scheduled'

        # Only update spreads if game hasn't started yet
        if not has_started:
            existing.home_spread = home_spread
            existing.away_spread = away_spread

        game = existing
        action = "updated" if not has_started else "updated (no spread change)"
    else:
        # Create new game
        game = SpreadGame(
            spread_poll_id=poll.id,
            bovada_event_id=bovada_event_id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            home_spread=home_spread,
            away_spread=away_spread,
            game_time=game_time,
            game_day=game_day,
            status=status or 'scheduled',
        )
        session.add(game)
        action = "created"

    return game, action


def run_ingestion():
    """Main ingestion function"""
    session = SessionLocal()

    try:
        print(f"\n{'='*60}")
        print(f"Starting Bovada Spreads Ingestion")
        print(f"Season: {CURRENT_SEASON}, Week: {CURRENT_WEEK}")
        print(f"{'='*60}\n")

        # Get or create the SpreadPoll for this week
        poll = get_or_create_spread_poll(session, CURRENT_SEASON, CURRENT_WEEK)

        # Fetch events from Bovada
        print(f"[→] Fetching events from Bovada ({SPORT})...")
        events_df = fetch_events_for_sport(SPORT, live_only=False)

        if events_df.empty:
            print("[!] No events found from Bovada")
            session.commit()
            return

        print(f"[✓] Found {len(events_df)} total events from Bovada")

        # Filter to Friday and Saturday games only
        events_df['day_of_week'] = events_df['start_time_utc'].apply(get_day_of_week)
        events_df['is_weekend'] = events_df['start_time_utc'].apply(is_weekend_game)
        weekend_events = events_df[events_df['is_weekend'] == True]

        print(f"[✓] Filtered to {len(weekend_events)} weekend games (Friday & Saturday)")

        created_count = 0
        updated_count = 0
        skipped_count = 0
        unmapped_teams = set()

        # Process each weekend event
        for idx, row in weekend_events.iterrows():
            bovada_event_id = str(row.get('event_id', ''))
            home_team_name = row.get('home_team')
            away_team_name = row.get('away_team')
            game_time_utc = row.get('start_time_utc')
            # Convert to Eastern Time for storage and display
            game_time = utc_to_et(game_time_utc)
            game_day = row.get('day_of_week', 'Saturday')
            status = row.get('status', 'scheduled')

            if not home_team_name or not away_team_name:
                print(f"[!] Skipping event {bovada_event_id}: missing team names")
                skipped_count += 1
                continue

            # Map teams
            home_team_result = map_bovada_team(home_team_name, session)
            away_team_result = map_bovada_team(away_team_name, session)

            if not home_team_result:
                print(f"[!] Could not map home team: '{home_team_name}'")
                unmapped_teams.add(home_team_name)
                skipped_count += 1
                continue

            if not away_team_result:
                print(f"[!] Could not map away team: '{away_team_name}'")
                unmapped_teams.add(away_team_name)
                skipped_count += 1
                continue

            home_team, home_confidence = home_team_result
            away_team, away_confidence = away_team_result

            # Fetch detailed markets (spread)
            link = row.get('link')
            home_spread = None
            away_spread = None

            if link:
                try:
                    event_node = fetch_event_node_by_link(link)
                    if event_node:
                        markets = extract_key_markets(
                            ev_node=event_node,
                            home_id=str(row.get('home_competitor_id', '')),
                            away_id=str(row.get('away_competitor_id', '')),
                            home_name=home_team_name,
                            away_name=away_team_name,
                        )
                        home_spread = markets.get('home_spread')
                        away_spread = markets.get('away_spread')
                except Exception as e:
                    print(f"[!] Error fetching markets for {bovada_event_id}: {e}")

            # Convert spread to string if numeric
            if home_spread is not None:
                home_spread = str(home_spread)
            if away_spread is not None:
                away_spread = str(away_spread)

            # Create or update the game
            game, action = upsert_spread_game(
                session=session,
                poll=poll,
                bovada_event_id=bovada_event_id,
                home_team=home_team,
                away_team=away_team,
                home_spread=home_spread,
                away_spread=away_spread,
                game_time=game_time,
                game_day=game_day,
                status=status,
            )

            if action == "created":
                created_count += 1
                print(f"[+] Created: {away_team.name} @ {home_team.name} (Spread: {home_spread})")
            else:
                updated_count += 1
                print(f"[↻] Updated: {away_team.name} @ {home_team.name} (Spread: {home_spread})")

        # Commit all changes
        session.commit()

        print(f"\n{'='*60}")
        print(f"Ingestion Complete!")
        print(f"  Created: {created_count}")
        print(f"  Updated: {updated_count}")
        print(f"  Skipped: {skipped_count}")
        if unmapped_teams:
            print(f"\n[!] Unmapped teams ({len(unmapped_teams)}):")
            for team in sorted(unmapped_teams):
                print(f"    - {team}")
        print(f"{'='*60}\n")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    run_ingestion()
