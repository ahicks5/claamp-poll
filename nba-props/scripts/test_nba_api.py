#!/usr/bin/env python3
"""Test NBA API connectivity on Heroku."""
import sys
import os
import time

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

print("=" * 60)
print("NBA API CONNECTION TEST")
print("=" * 60)
print()

# Test 1: Import nba_api
print("[1/5] Testing nba_api import...")
try:
    from nba_api.stats.static import teams, players
    from nba_api.stats.endpoints import scoreboardv2
    print("✓ nba_api imported successfully")
except Exception as e:
    print(f"✗ Failed to import nba_api: {e}")
    sys.exit(1)

print()

# Test 2: Get teams (static data, should work)
print("[2/5] Testing teams.get_teams() [static data]...")
try:
    start = time.time()
    all_teams = teams.get_teams()
    elapsed = time.time() - start
    print(f"✓ Got {len(all_teams)} teams in {elapsed:.2f}s")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

print()

# Test 3: Get active players (static data, should work)
print("[3/5] Testing players.get_active_players() [static data]...")
try:
    start = time.time()
    active_players = players.get_active_players()
    elapsed = time.time() - start
    print(f"✓ Got {len(active_players)} players in {elapsed:.2f}s")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

print()

# Test 4: API endpoint with custom timeout and headers
print("[4/5] Testing ScoreboardV2 endpoint [API call]...")
print("This is where timeouts usually happen on Heroku...")
try:
    from datetime import datetime

    # Configure NBA API with longer timeout
    import nba_api.stats.endpoints.scoreboardv2 as sb
    from nba_api.stats.library.http import NBAStatsHTTP

    # Set timeout to 60 seconds
    NBAStatsHTTP.timeout = 60

    start = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    board = scoreboardv2.ScoreboardV2(
        game_date=today,
        timeout=60
    )
    elapsed = time.time() - start

    df = board.get_data_frames()[0]
    print(f"✓ Got scoreboard in {elapsed:.2f}s ({len(df)} games)")

except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("DIAGNOSIS:")
    print("  - This timeout usually means NBA.com is blocking Heroku's IP")
    print("  - Or network connectivity issues on Heroku")
    sys.exit(1)

print()

# Test 5: Player game log (most likely to timeout)
print("[5/5] Testing PlayerGameLog endpoint [API call]...")
print("Testing with a popular player (LeBron James)...")
try:
    from nba_api.stats.endpoints import playergamelog

    # LeBron James ID: 2544
    start = time.time()
    gamelog = playergamelog.PlayerGameLog(
        player_id=2544,
        season="2023-24",
        timeout=60
    )
    elapsed = time.time() - start

    df = gamelog.get_data_frames()[0]
    print(f"✓ Got game log in {elapsed:.2f}s ({len(df)} games)")

except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("DIAGNOSIS:")
    print("  - NBA API is blocking or rate-limiting Heroku's IP address")
    print("  - This endpoint requires authentication or has stricter limits")

print()
print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print()
print("If tests 1-3 passed but 4-5 failed:")
print("  → NBA API is blocking Heroku's IP for dynamic endpoints")
print("  → Solution: Use only Odds API for live data")
print()
print("If all tests passed:")
print("  → NBA API works on Heroku!")
print("  → The backfill script should work")
