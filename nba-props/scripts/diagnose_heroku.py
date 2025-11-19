#!/usr/bin/env python3
# scripts/diagnose_heroku.py
"""
Diagnostic script for troubleshooting Heroku deployment issues.

Tests:
1. Environment variables
2. Database connectivity (PostgreSQL/MySQL/SQLite)
3. NBA API connectivity
4. Odds API connectivity
5. Network/DNS resolution
6. File system access

Usage:
    python scripts/diagnose_heroku.py
    python scripts/diagnose_heroku.py --verbose
"""
import sys
import os
import time
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_environment():
    """Check environment variables."""
    logger.info("="*60)
    logger.info("1. ENVIRONMENT VARIABLES")
    logger.info("="*60)

    env_vars = {
        'NBA_DATABASE_URL': os.getenv('NBA_DATABASE_URL'),
        'ODDS_API_KEY': os.getenv('ODDS_API_KEY'),
        'NBA_API_TIMEOUT': os.getenv('NBA_API_TIMEOUT', '90'),
        'NBA_API_MAX_RETRIES': os.getenv('NBA_API_MAX_RETRIES', '2'),
        'DYNO': os.getenv('DYNO'),  # Heroku-specific
        'PORT': os.getenv('PORT'),  # Heroku-specific
    }

    all_set = True
    for key, value in env_vars.items():
        if value:
            # Mask sensitive values
            if 'KEY' in key or 'URL' in key:
                display_value = value[:20] + '...' if len(value) > 20 else value
            else:
                display_value = value
            logger.info(f"  ✓ {key}: {display_value}")
        else:
            logger.warning(f"  ✗ {key}: NOT SET")
            if key in ['NBA_DATABASE_URL', 'ODDS_API_KEY']:
                all_set = False

    # Detect environment
    if os.getenv('DYNO'):
        logger.info(f"\n  Environment: Heroku (Dyno: {os.getenv('DYNO')})")
    else:
        logger.info(f"\n  Environment: Local Development")

    return all_set


def test_database():
    """Test database connectivity."""
    logger.info("\n" + "="*60)
    logger.info("2. DATABASE CONNECTION")
    logger.info("="*60)

    db_url = os.getenv('NBA_DATABASE_URL', 'Not set')
    logger.info(f"  Database URL: {db_url[:50]}...")

    # Determine database type
    if db_url.startswith('postgresql://') or db_url.startswith('postgres://'):
        db_type = "PostgreSQL"
    elif db_url.startswith('mysql://'):
        db_type = "MySQL"
    elif db_url.startswith('sqlite://'):
        db_type = "SQLite"
    else:
        db_type = "Unknown"

    logger.info(f"  Database Type: {db_type}")

    try:
        from database import engine, get_session
        from sqlalchemy import text

        # Test connection
        start_time = time.time()
        with engine.connect() as conn:
            # Simple test query that works on all databases
            conn.execute(text("SELECT 1"))
        connect_time = time.time() - start_time

        logger.info(f"  ✓ Connection successful ({connect_time:.2f}s)")

        # Test session
        session = get_session()
        from database import Player, Team, Game

        teams_count = session.query(Team).count()
        players_count = session.query(Player).count()
        games_count = session.query(Game).count()

        logger.info(f"  ✓ Query successful")
        logger.info(f"    - Teams: {teams_count}")
        logger.info(f"    - Players: {players_count}")
        logger.info(f"    - Games: {games_count}")

        session.close()
        return True

    except Exception as e:
        logger.error(f"  ✗ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nba_api():
    """Test NBA API connectivity."""
    logger.info("\n" + "="*60)
    logger.info("3. NBA API CONNECTION")
    logger.info("="*60)

    timeout = os.getenv('NBA_API_TIMEOUT', '90')
    max_retries = os.getenv('NBA_API_MAX_RETRIES', '2')
    logger.info(f"  Timeout: {timeout}s")
    logger.info(f"  Max Retries: {max_retries}")

    try:
        from services.nba_api_client import NBAAPIClient
        client = NBAAPIClient()

        # Test 1: Get teams (static data, should be fast)
        logger.info("\n  Test 1: Fetching teams...")
        start_time = time.time()
        teams = client.get_all_teams()
        elapsed = time.time() - start_time
        logger.info(f"  ✓ Teams fetched: {len(teams)} teams ({elapsed:.2f}s)")

        # Test 2: Get players (static data, should be fast)
        logger.info("\n  Test 2: Fetching active players...")
        start_time = time.time()
        players = client.get_all_active_players()
        elapsed = time.time() - start_time
        logger.info(f"  ✓ Players fetched: {len(players)} players ({elapsed:.2f}s)")

        # Test 3: Get today's games (API endpoint)
        logger.info("\n  Test 3: Fetching today's games...")
        start_time = time.time()
        try:
            games = client.get_todays_games()
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Games fetched: {len(games)} games ({elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.warning(f"  ⚠ Games fetch failed after {elapsed:.2f}s: {e}")
            logger.warning(f"    This is often a timeout issue on Heroku")

        return True

    except Exception as e:
        logger.error(f"  ✗ NBA API test failed: {e}")
        logger.error(f"\n  Troubleshooting:")
        logger.error(f"    1. Increase NBA_API_TIMEOUT (currently: {timeout}s)")
        logger.error(f"    2. Check if Heroku can reach stats.nba.com")
        logger.error(f"    3. Try running: heroku run python scripts/test_nba_api.py")
        import traceback
        traceback.print_exc()
        return False


def test_odds_api():
    """Test Odds API connectivity."""
    logger.info("\n" + "="*60)
    logger.info("4. ODDS API CONNECTION")
    logger.info("="*60)

    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        logger.warning("  ✗ ODDS_API_KEY not set, skipping test")
        return False

    logger.info(f"  API Key: {api_key[:10]}...")

    try:
        import requests

        # Test API with a simple endpoint
        url = "https://api.the-odds-api.com/v4/sports"
        params = {
            'apiKey': api_key
        }

        logger.info(f"  Testing: {url}")
        start_time = time.time()
        response = requests.get(url, params=params, timeout=30)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            logger.info(f"  ✓ Odds API connection successful ({elapsed:.2f}s)")
            logger.info(f"  ✓ Found {len(data)} sports")

            # Check for NBA
            nba_sports = [s for s in data if 'basketball' in s.get('group', '').lower()]
            if nba_sports:
                logger.info(f"  ✓ NBA basketball available")

            # Check remaining requests
            remaining = response.headers.get('x-requests-remaining')
            if remaining:
                logger.info(f"  Remaining API calls: {remaining}")

            return True
        else:
            logger.error(f"  ✗ API returned status {response.status_code}")
            logger.error(f"    Response: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"  ✗ Odds API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_network():
    """Test general network connectivity."""
    logger.info("\n" + "="*60)
    logger.info("5. NETWORK CONNECTIVITY")
    logger.info("="*60)

    test_urls = [
        ('stats.nba.com', 'https://stats.nba.com'),
        ('The Odds API', 'https://api.the-odds-api.com'),
        ('Google DNS', 'https://www.google.com'),
    ]

    import requests
    all_passed = True

    for name, url in test_urls:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start_time
            logger.info(f"  ✓ {name}: {response.status_code} ({elapsed:.2f}s)")
        except Exception as e:
            logger.error(f"  ✗ {name}: {e}")
            all_passed = False

    return all_passed


def test_filesystem():
    """Test file system access."""
    logger.info("\n" + "="*60)
    logger.info("6. FILE SYSTEM ACCESS")
    logger.info("="*60)

    # Check key directories
    directories = [
        ('Project Root', PROJECT_ROOT),
        ('Models Directory', os.path.join(PROJECT_ROOT, 'models')),
        ('Exports Directory', os.path.join(PROJECT_ROOT, 'exports')),
        ('Logs Directory', os.path.join(PROJECT_ROOT, 'logs')),
    ]

    all_exist = True
    for name, path in directories:
        if os.path.exists(path):
            writable = os.access(path, os.W_OK)
            status = "writable" if writable else "read-only"
            logger.info(f"  ✓ {name}: exists ({status})")
        else:
            logger.warning(f"  ✗ {name}: does not exist")
            logger.info(f"    Path: {path}")
            all_exist = False

    # Try to create a test file
    try:
        test_file = os.path.join(PROJECT_ROOT, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info(f"  ✓ Write test: successful")
    except Exception as e:
        logger.error(f"  ✗ Write test: failed ({e})")
        all_exist = False

    return all_exist


def main():
    """Run all diagnostic tests."""
    import argparse

    parser = argparse.ArgumentParser(description='Diagnose Heroku deployment issues')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("\n" + "="*60)
    logger.info("HEROKU DIAGNOSTIC SCRIPT")
    logger.info("="*60)
    logger.info(f"Started: {datetime.now()}")
    logger.info("")

    results = {
        'Environment': test_environment(),
        'Database': test_database(),
        'NBA API': test_nba_api(),
        'Odds API': test_odds_api(),
        'Network': test_network(),
        'File System': test_filesystem(),
    }

    # Summary
    logger.info("\n" + "="*60)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("="*60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {status:8s} {test_name}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    logger.info(f"\nPassed: {passed_count}/{total_count}")

    if all(results.values()):
        logger.info("\n[SUCCESS] All diagnostic tests passed!")
        logger.info("Your Heroku environment is configured correctly.")
        return 0
    else:
        logger.warning("\n[WARNING] Some diagnostic tests failed.")
        logger.warning("Review the errors above and fix configuration issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
