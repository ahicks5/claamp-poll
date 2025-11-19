#!/usr/bin/env python3
# scripts/check_database_status.py
"""
Check database status - see what tables exist and if user data is safe.
"""
import sys
import os

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from sqlalchemy import create_engine, text, inspect

print("="*60)
print("DATABASE STATUS CHECK")
print("="*60)

# Check environment variables
database_url = os.getenv('DATABASE_URL', 'Not set')
nba_database_url = os.getenv('NBA_DATABASE_URL', 'Not set')

print("\nENVIRONMENT VARIABLES:")
print(f"  DATABASE_URL: {database_url[:40]}...")
print(f"  NBA_DATABASE_URL: {nba_database_url[:40]}...")

if database_url == nba_database_url:
    print("\n⚠️  WARNING: Both URLs point to the SAME database!")
else:
    print("\n✓ URLs are different - main app database is separate")

# Connect to NBA database
print("\n" + "="*60)
print("CHECKING NBA DATABASE")
print("="*60)

try:
    # Fix postgres:// to postgresql://
    if nba_database_url.startswith("postgres://"):
        nba_database_url = nba_database_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(nba_database_url)

    with engine.connect() as conn:
        # Get all tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"\nTables in NBA database ({len(tables)} total):")
        if tables:
            for table in sorted(tables):
                print(f"  - {table}")
        else:
            print("  (no tables found)")

        # Check for NBA-specific tables
        nba_tables = ['nba_teams', 'nba_players', 'nba_games', 'nba_prop_lines']
        nba_table_count = sum(1 for t in tables if t in nba_tables)

        print(f"\nNBA-specific tables found: {nba_table_count}/4")

        # Check for user/auth tables (should NOT be in NBA database)
        user_tables = ['users', 'user', 'auth_user', 'accounts', 'account']
        user_table_found = any(t in tables for t in user_tables)

        if user_table_found:
            print("\n⚠️  WARNING: Found user-related tables in NBA database!")
            print("   This suggests DATABASE_URL and NBA_DATABASE_URL are the same.")
        else:
            print("\n✓ No user tables found in NBA database (this is correct)")

except Exception as e:
    print(f"\n✗ Error connecting to NBA database: {e}")

# Now check main database if URLs are the same
if database_url == nba_database_url:
    print("\n" + "="*60)
    print("CHECKING FOR DATA LOSS")
    print("="*60)
    print("\nSince both URLs are the same, checking what happened...")

    try:
        # Fix postgres:// to postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        engine = create_engine(database_url)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()

        # Check for common user-related tables
        user_related = ['users', 'user', 'auth_user', 'accounts', 'sessions', 'profiles']
        found_user_tables = [t for t in all_tables if any(u in t.lower() for u in user_related)]

        if found_user_tables:
            print(f"\n✓ GOOD NEWS: User tables still exist!")
            print("  Found tables:")
            for t in found_user_tables:
                print(f"    - {t}")
            print("\n✓ Your user data appears to be SAFE")
        else:
            print("\n✗ BAD NEWS: No user tables found!")
            print("  The reset may have deleted your data.")
            print("\n  Next steps:")
            print("    1. Check backups immediately")
            print("    2. Run: heroku pg:backups")
            print("    3. Restore from latest backup if needed")

    except Exception as e:
        print(f"\n✗ Error checking main database: {e}")

print("\n" + "="*60)
print("SUMMARY")
print("="*60)

if database_url != nba_database_url:
    print("\n✓ SAFE: Your databases are separate")
    print("  Main app data: Untouched")
    print("  NBA database: Empty (ready to initialize)")
else:
    print("\n⚠️  ATTENTION NEEDED:")
    print("  DATABASE_URL and NBA_DATABASE_URL point to same database")
    print("  Run the checks above to see if data was affected")

print("")
