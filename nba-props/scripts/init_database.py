#!/usr/bin/env python3
# scripts/init_database.py
"""Initialize the NBA props database and populate reference data."""
import sys
import os
import logging

# Add parent directory to path so we can import our modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import init_db, get_session, Team, Player
from services.nba_api_client import NBAAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def populate_teams(session, nba_client):
    """Populate teams table with all NBA teams."""
    logger.info("Populating teams...")

    teams_data = nba_client.get_all_teams()

    for team_data in teams_data:
        # Check if team already exists
        existing = session.query(Team).filter_by(nba_team_id=team_data['id']).first()

        if existing:
            logger.debug(f"Team {team_data['abbreviation']} already exists, skipping")
            continue

        # Create new team
        team = Team(
            nba_team_id=team_data['id'],
            name=team_data['full_name'],
            abbreviation=team_data['abbreviation'],
            city=team_data['city'],
        )
        session.add(team)

    session.commit()
    logger.info(f"Teams populated: {session.query(Team).count()} teams in database")


def populate_players(session, nba_client, fetch_details=False):
    """
    Populate players table with all active NBA players.

    Args:
        fetch_details: If True, fetch detailed info (position, team, etc.) - SLOW!
                       If False, just load basic player names and IDs - FAST!
    """
    logger.info("Populating active players...")
    if not fetch_details:
        logger.info("(Skipping detailed player info for speed - this is OK!)")

    players_data = nba_client.get_all_active_players()
    players_added = 0

    for i, player_data in enumerate(players_data):
        # Check if player already exists
        existing = session.query(Player).filter_by(nba_player_id=player_data['id']).first()

        if existing:
            logger.debug(f"Player {player_data['full_name']} already exists, skipping")
            continue

        # Only fetch detailed info if requested (this is SLOW and often times out)
        player_info = None
        team = None

        if fetch_details:
            try:
                player_info = nba_client.get_player_info(player_data['id'])

                # Find team by abbreviation if available
                if player_info and 'TEAM_ABBREVIATION' in player_info:
                    team_abbr = player_info.get('TEAM_ABBREVIATION')
                    if team_abbr:
                        team = session.query(Team).filter_by(abbreviation=team_abbr).first()
            except Exception as e:
                logger.warning(f"Could not fetch details for {player_data['full_name']}: {e}")
                player_info = None

        # Create new player with basic info
        player = Player(
            nba_player_id=player_data['id'],
            full_name=player_data['full_name'],
            first_name=player_data.get('first_name'),
            last_name=player_data.get('last_name'),
            team_id=team.id if team else None,
            is_active=True,
        )

        # Add additional info if available
        if player_info:
            player.position = player_info.get('POSITION')
            player.jersey_number = player_info.get('JERSEY')
            player.height = player_info.get('HEIGHT')
            player.weight = player_info.get('WEIGHT')

        session.add(player)
        players_added += 1

        # Progress indicator every 100 players
        if (i + 1) % 100 == 0:
            logger.info(f"  Processed {i + 1}/{len(players_data)} players...")

        # Commit every 50 players to avoid holding too much in memory
        if len(session.new) >= 50:
            session.commit()
            logger.debug(f"Committed batch of players...")

    session.commit()
    logger.info(f"Players populated: {session.query(Player).count()} players in database")
    logger.info(f"  New players added: {players_added}")


def main():
    """Initialize database and populate reference data."""
    import argparse

    parser = argparse.ArgumentParser(description='Initialize NBA props database')
    parser.add_argument(
        '--fetch-details',
        action='store_true',
        help='Fetch detailed player info (position, team, etc.) - SLOW and may timeout'
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("NBA Props Database Initialization")
    logger.info("=" * 60)

    # Initialize database schema
    logger.info("\nStep 1: Creating database tables...")
    init_db()

    # Initialize API client
    logger.info("\nStep 2: Initializing NBA API client...")
    nba_client = NBAAPIClient()

    # Get database session
    session = get_session()

    try:
        # Populate teams
        logger.info("\nStep 3: Populating teams...")
        populate_teams(session, nba_client)

        # Populate players
        logger.info("\nStep 4: Populating players...")
        if args.fetch_details:
            logger.info("(This may take several minutes due to API rate limiting and timeouts...)")
        else:
            logger.info("(Fast mode - loading names only, ~10 seconds)")

        populate_players(session, nba_client, fetch_details=args.fetch_details)

        logger.info("\n" + "=" * 60)
        logger.info("[OK] Database initialization complete!")
        logger.info("=" * 60)
        logger.info(f"\nDatabase stats:")
        logger.info(f"  Teams: {session.query(Team).count()}")
        logger.info(f"  Players: {session.query(Player).count()}")

        if not args.fetch_details:
            logger.info("\nNote: Player details (position, team, etc.) were skipped for speed.")
            logger.info("This is fine - the system will work without them!")
            logger.info("To fetch details later, run: python scripts/init_database.py --fetch-details")

    except Exception as e:
        logger.error(f"\n[ERROR] Error during initialization: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
