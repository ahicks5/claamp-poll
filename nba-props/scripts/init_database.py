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
    logger.info(f"✓ Teams populated: {session.query(Team).count()} teams in database")


def populate_players(session, nba_client):
    """Populate players table with all active NBA players."""
    logger.info("Populating active players...")

    players_data = nba_client.get_all_active_players()

    for player_data in players_data:
        # Check if player already exists
        existing = session.query(Player).filter_by(nba_player_id=player_data['id']).first()

        if existing:
            logger.debug(f"Player {player_data['full_name']} already exists, skipping")
            continue

        # Try to get additional player info
        player_info = nba_client.get_player_info(player_data['id'])

        # Find team by abbreviation if available
        team = None
        if player_info and 'TEAM_ABBREVIATION' in player_info:
            team_abbr = player_info.get('TEAM_ABBREVIATION')
            if team_abbr:
                team = session.query(Team).filter_by(abbreviation=team_abbr).first()

        # Create new player
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

        # Commit every 50 players to avoid holding too much in memory
        if len(session.new) >= 50:
            session.commit()
            logger.debug(f"Committed batch of players...")

    session.commit()
    logger.info(f"✓ Players populated: {session.query(Player).count()} players in database")


def main():
    """Initialize database and populate reference data."""
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

        # Populate players (this may take a while due to rate limiting)
        logger.info("\nStep 4: Populating players...")
        logger.info("(This may take several minutes due to API rate limiting...)")
        populate_players(session, nba_client)

        logger.info("\n" + "=" * 60)
        logger.info("✓ Database initialization complete!")
        logger.info("=" * 60)
        logger.info(f"\nDatabase stats:")
        logger.info(f"  Teams: {session.query(Team).count()}")
        logger.info(f"  Players: {session.query(Player).count()}")

    except Exception as e:
        logger.error(f"\n✗ Error during initialization: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
