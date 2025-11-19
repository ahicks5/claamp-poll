#!/usr/bin/env python3
# scripts/reset_database.py
"""
Reset the database by dropping all tables and recreating the schema.

WARNING: This will DELETE ALL DATA in the database!

Usage:
    python scripts/reset_database.py                    # Will ask for confirmation
    python scripts/reset_database.py --force            # Skip confirmation
"""
import sys
import os

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from sqlalchemy import text


def reset_database(force=False):
    """Drop all tables and recreate schema."""
    from database import engine

    print("="*60)
    print("DATABASE RESET")
    print("="*60)
    print(f"Database: {str(engine.url)[:50]}...")
    print("")

    if not force:
        print("WARNING: This will DELETE ALL DATA in the database!")
        print("")
        response = input("Are you sure you want to continue? (type 'yes' to confirm): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return False

    print("\nDropping all tables...")

    try:
        with engine.connect() as conn:
            # Drop all tables by dropping and recreating the schema
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()

        print("✓ All tables dropped successfully")
        print("")
        print("Now run: python nba-props/scripts/heroku_init.py --full")
        print("  to recreate tables and load teams/players")
        return True

    except Exception as e:
        print(f"✗ Error resetting database: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main script."""
    import argparse

    parser = argparse.ArgumentParser(description='Reset NBA props database')
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    success = reset_database(force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
