#!/usr/bin/env python3
# scripts/heroku_init.py
"""
Initialize NBA props system on Heroku.

This script:
1. Tests database connection (PostgreSQL)
2. Creates all database tables
3. Tests NBA API connectivity
4. Optionally loads teams and players

Usage:
    python scripts/heroku_init.py                    # Just create tables
    python scripts/heroku_init.py --load-reference   # Also load teams/players
    python scripts/heroku_init.py --full             # Full init with test data
"""
import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_database_connection():
    """Test that we can connect to the database."""
    logger.info("="*60)
    logger.info("Testing Database Connection")
    logger.info("="*60)

    try:
        from database import get_session, Player
        session = get_session()

        # Try a simple query
        count = session.query(Player).count()
        logger.info(f"✓ Database connection successful!")
        logger.info(f"  Current players in DB: {count}")

        session.close()
        return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        logger.error("  Check your DATABASE_URL environment variable")
        return False


def create_tables():
    """Create all database tables."""
    logger.info("\n" + "="*60)
    logger.info("Creating Database Tables")
    logger.info("="*60)

    try:
        from database import init_db
        init_db()
        logger.info("✓ All tables created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nba_api():
    """Test NBA API connectivity."""
    logger.info("\n" + "="*60)
    logger.info("Testing NBA API Connection")
    logger.info("="*60)

    try:
        from services.nba_api_client import NBAAPIClient
        client = NBAAPIClient()

        # Test basic API call
        logger.info("Fetching NBA teams...")
        teams = client.get_all_teams()
        logger.info(f"✓ NBA API connection successful!")
        logger.info(f"  Found {len(teams)} teams")

        return True
    except Exception as e:
        logger.error(f"✗ NBA API connection failed: {e}")
        logger.error("  This might be a timeout issue - check NBA_API_TIMEOUT env var")
        return False


def load_teams():
    """Load all NBA teams into database."""
    logger.info("\n" + "="*60)
    logger.info("Loading NBA Teams")
    logger.info("="*60)

    try:
        from database import get_session, Team
        from services.nba_api_client import NBAAPIClient

        session = get_session()
        client = NBAAPIClient()

        teams_data = client.get_all_teams()

        loaded = 0
        skipped = 0

        for team_data in teams_data:
            # Check if team already exists
            existing = session.query(Team).filter_by(
                nba_team_id=team_data['id']
            ).first()

            if existing:
                skipped += 1
                continue

            team = Team(
                nba_team_id=team_data['id'],
                name=team_data['full_name'],
                abbreviation=team_data['abbreviation'],
                city=team_data.get('city', ''),
                conference=None,  # NBA API doesn't provide this in get_teams()
                division=None
            )
            session.add(team)
            loaded += 1

        session.commit()
        logger.info(f"✓ Loaded {loaded} teams (skipped {skipped} existing)")
        session.close()
        return True
    except Exception as e:
        logger.error(f"✗ Failed to load teams: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_players(limit: int = None):
    """Load active NBA players into database."""
    logger.info("\n" + "="*60)
    logger.info(f"Loading NBA Players{f' (limit: {limit})' if limit else ''}")
    logger.info("="*60)

    try:
        from database import get_session, Player, Team
        from services.nba_api_client import NBAAPIClient

        session = get_session()
        client = NBAAPIClient()

        # Get all active players
        players_data = client.get_all_active_players()

        if limit:
            players_data = players_data[:limit]

        loaded = 0
        skipped = 0

        logger.info(f"Processing {len(players_data)} players...")

        for i, player_data in enumerate(players_data):
            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i+1}/{len(players_data)}")

            # Check if player already exists
            existing = session.query(Player).filter_by(
                nba_player_id=player_data['id']
            ).first()

            if existing:
                skipped += 1
                continue

            # Create player record (without detailed info to avoid API calls)
            player = Player(
                nba_player_id=player_data['id'],
                full_name=player_data['full_name'],
                first_name=player_data.get('first_name', ''),
                last_name=player_data.get('last_name', ''),
                is_active=player_data.get('is_active', True),
                team_id=None,  # Will be updated later if needed
                position=None,
                jersey_number=None
            )
            session.add(player)
            loaded += 1

            # Commit in batches
            if loaded % 50 == 0:
                session.commit()

        session.commit()
        logger.info(f"✓ Loaded {loaded} players (skipped {skipped} existing)")
        session.close()
        return True
    except Exception as e:
        logger.error(f"✗ Failed to load players: {e}")
        import traceback
        traceback.print_exc()
        return False


def display_summary():
    """Display summary of database contents."""
    logger.info("\n" + "="*60)
    logger.info("Database Summary")
    logger.info("="*60)

    try:
        from database import get_session, Team, Player, Game, PropLine
        session = get_session()

        teams_count = session.query(Team).count()
        players_count = session.query(Player).count()
        games_count = session.query(Game).count()
        props_count = session.query(PropLine).count()

        logger.info(f"  Teams:        {teams_count:,}")
        logger.info(f"  Players:      {players_count:,}")
        logger.info(f"  Games:        {games_count:,}")
        logger.info(f"  Prop Lines:   {props_count:,}")

        session.close()
    except Exception as e:
        logger.error(f"Error getting summary: {e}")


def main():
    """Main initialization script."""
    import argparse

    parser = argparse.ArgumentParser(description='Initialize NBA props system on Heroku')
    parser.add_argument(
        '--load-reference',
        action='store_true',
        help='Load teams and players into database'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full initialization (create tables + load all reference data)'
    )
    parser.add_argument(
        '--player-limit',
        type=int,
        default=None,
        help='Limit number of players to load (for testing)'
    )
    parser.add_argument(
        '--skip-api-test',
        action='store_true',
        help='Skip NBA API connectivity test (faster)'
    )

    args = parser.parse_args()

    logger.info("\n" + "="*60)
    logger.info("HEROKU INITIALIZATION SCRIPT")
    logger.info("="*60)
    logger.info(f"Environment: {'Heroku' if os.getenv('DYNO') else 'Local'}")
    logger.info(f"Database URL: {os.getenv('NBA_DATABASE_URL', 'Not set')[:30]}...")
    logger.info(f"Started: {datetime.now()}")
    logger.info("")

    # Step 1: Test database connection
    if not test_database_connection():
        logger.error("\n[FAILED] Cannot proceed without database connection")
        sys.exit(1)

    # Step 2: Create tables
    if not create_tables():
        logger.error("\n[FAILED] Cannot proceed without database tables")
        sys.exit(1)

    # Step 3: Test NBA API (optional)
    if not args.skip_api_test:
        if not test_nba_api():
            logger.warning("\n[WARNING] NBA API test failed, but continuing...")
            logger.warning("  You may encounter issues when fetching data")

    # Step 4: Load reference data if requested
    if args.full or args.load_reference:
        logger.info("\n" + "="*60)
        logger.info("Loading Reference Data")
        logger.info("="*60)

        if not load_teams():
            logger.error("\n[FAILED] Could not load teams")
            sys.exit(1)

        if not load_players(limit=args.player_limit):
            logger.error("\n[FAILED] Could not load players")
            sys.exit(1)

    # Display summary
    display_summary()

    # Final message
    logger.info("\n" + "="*60)
    logger.info("[SUCCESS] Heroku initialization complete!")
    logger.info("="*60)
    logger.info("\nNext steps:")
    logger.info("  1. Run: python scripts/collect_daily_data.py")
    logger.info("  2. Train model: python scripts/train_model.py")
    logger.info("  3. Generate predictions: python scripts/generate_predictions.py")
    logger.info("")


if __name__ == "__main__":
    main()
