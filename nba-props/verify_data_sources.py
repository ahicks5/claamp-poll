#!/usr/bin/env python3
"""
NBA Props Data Verification Protocol
Tests all data sources needed for predictions:
1. Player info (name, team)
2. Game-by-game stats (points, rebounds, assists, etc.)
3. Season stats and averages
4. Team/opponent tracking
5. Historical data availability
"""
import sys
import os
from datetime import date, timedelta
from tabulate import tabulate

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import SessionLocal
from database.models import Team, Player, Game, PlayerGameStats
from services.nba_api_client import NBAAPIClient


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_1_database_setup():
    """Test 1: Verify database is initialized"""
    print_section("TEST 1: Database Setup")

    db = SessionLocal()
    try:
        teams_count = db.query(Team).count()
        players_count = db.query(Player).count()

        print(f"\n✓ Teams in database: {teams_count}")
        print(f"✓ Players in database: {players_count}")

        if teams_count == 30:
            print("  ✅ All 30 NBA teams loaded")
        else:
            print(f"  ⚠️  Expected 30 teams, found {teams_count}")

        if players_count > 400:
            print(f"  ✅ Active players loaded ({players_count} players)")
        else:
            print(f"  ⚠️  Low player count: {players_count}")

        return teams_count == 30 and players_count > 400

    finally:
        db.close()


def test_2_player_info():
    """Test 2: Verify we can get player info (name, team)"""
    print_section("TEST 2: Player Information")

    db = SessionLocal()
    try:
        # Get a few well-known players
        test_names = ["LeBron James", "Stephen Curry", "Kevin Durant", "Giannis"]

        print("\nLooking up test players:")
        found_players = []

        for name in test_names:
            # Search for player (partial match)
            player = db.query(Player).filter(
                Player.full_name.like(f"%{name}%")
            ).first()

            if player:
                team = db.query(Team).get(player.team_id) if player.team_id else None
                team_name = team.abbreviation if team else "No Team"

                print(f"  ✓ {player.full_name} ({team_name})")
                print(f"    NBA ID: {player.nba_player_id}")
                print(f"    Position: {player.position or 'N/A'}")

                found_players.append({
                    'id': player.id,
                    'nba_id': player.nba_player_id,
                    'name': player.full_name,
                    'team': team_name
                })
            else:
                print(f"  ❌ Could not find: {name}")

        success = len(found_players) >= 2
        if success:
            print(f"\n  ✅ Player lookup working ({len(found_players)}/{len(test_names)} found)")
        else:
            print(f"\n  ⚠️  Only found {len(found_players)}/{len(test_names)} players")

        return success, found_players

    finally:
        db.close()


def test_3_fetch_player_stats():
    """Test 3: Fetch game-by-game stats from NBA API"""
    print_section("TEST 3: Fetch Player Game Stats (Live API)")

    nba_client = NBAAPIClient()
    db = SessionLocal()

    try:
        # Get LeBron James as test case
        player = db.query(Player).filter(
            Player.full_name.like("%LeBron James%")
        ).first()

        if not player:
            print("  ❌ Could not find test player (LeBron James)")
            return False

        print(f"\nFetching stats for: {player.full_name}")
        print(f"NBA Player ID: {player.nba_player_id}")

        # Fetch this season's game log
        current_season = "2024-25"
        print(f"Season: {current_season}")

        game_log = nba_client.get_player_game_log(
            player_id=player.nba_player_id,
            season=current_season
        )

        if not game_log or len(game_log) == 0:
            print(f"\n  ⚠️  No games found for {current_season} season")
            print("     This might be off-season or early season")

            # Try last season
            last_season = "2023-24"
            print(f"\n  Trying {last_season} season instead...")
            game_log = nba_client.get_player_game_log(
                player_id=player.nba_player_id,
                season=last_season
            )

        if game_log and len(game_log) > 0:
            print(f"\n✓ Found {len(game_log)} games")

            # Show last 5 games
            print("\nLast 5 games:")
            recent_games = game_log[:5]

            table_data = []
            for game in recent_games:
                matchup = game.get('matchup', 'N/A')
                pts = game.get('points', 0)
                reb = game.get('rebounds', 0)
                ast = game.get('assists', 0)
                min_played = game.get('minutes', 'N/A')

                table_data.append([
                    game.get('game_date', 'N/A'),
                    matchup,
                    min_played,
                    pts,
                    reb,
                    ast
                ])

            print(tabulate(
                table_data,
                headers=['Date', 'Matchup', 'MIN', 'PTS', 'REB', 'AST'],
                tablefmt='simple'
            ))

            # Calculate season averages
            total_pts = sum(g.get('points', 0) for g in game_log)
            total_reb = sum(g.get('rebounds', 0) for g in game_log)
            total_ast = sum(g.get('assists', 0) for g in game_log)
            games_played = len(game_log)

            print(f"\nSeason Averages ({games_played} games):")
            print(f"  Points: {total_pts / games_played:.1f}")
            print(f"  Rebounds: {total_reb / games_played:.1f}")
            print(f"  Assists: {total_ast / games_played:.1f}")

            print("\n  ✅ Game-by-game stats working!")
            return True
        else:
            print("\n  ❌ Could not fetch game stats")
            return False

    finally:
        db.close()


def test_4_opponent_tracking():
    """Test 4: Verify we can track opponents"""
    print_section("TEST 4: Opponent Tracking")

    nba_client = NBAAPIClient()
    db = SessionLocal()

    try:
        # Get a player
        player = db.query(Player).filter(
            Player.full_name.like("%Stephen Curry%")
        ).first()

        if not player:
            print("  ❌ Could not find test player")
            return False

        print(f"\nPlayer: {player.full_name}")

        # Fetch game log
        game_log = nba_client.get_player_game_log(
            player_id=player.nba_player_id,
            season="2023-24"  # Use last full season
        )

        if not game_log or len(game_log) == 0:
            print("  ⚠️  No game data available")
            return False

        # Analyze opponents
        print(f"\nFound {len(game_log)} games")
        print("\nOpponent breakdown (showing first 10 games):")

        table_data = []
        for game in game_log[:10]:
            matchup = game.get('matchup', 'N/A')
            # Parse opponent from matchup (e.g., "GSW vs. LAL" or "GSW @ LAL")
            if 'vs.' in matchup:
                opponent = matchup.split('vs.')[1].strip()
                location = 'Home'
            elif '@' in matchup:
                opponent = matchup.split('@')[1].strip()
                location = 'Away'
            else:
                opponent = 'N/A'
                location = 'N/A'

            pts = game.get('points', 0)

            table_data.append([
                game.get('game_date', 'N/A'),
                location,
                opponent,
                pts
            ])

        print(tabulate(
            table_data,
            headers=['Date', 'Location', 'Opponent', 'PTS'],
            tablefmt='simple'
        ))

        print("\n  ✅ Opponent tracking working!")
        return True

    finally:
        db.close()


def test_5_all_stat_types():
    """Test 5: Verify all stat types are available"""
    print_section("TEST 5: All Stat Types")

    nba_client = NBAAPIClient()
    db = SessionLocal()

    try:
        player = db.query(Player).filter(
            Player.full_name.like("%Giannis%")
        ).first()

        if not player:
            print("  ❌ Could not find test player")
            return False

        print(f"\nPlayer: {player.full_name}")

        game_log = nba_client.get_player_game_log(
            player_id=player.nba_player_id,
            season="2023-24"
        )

        if not game_log or len(game_log) == 0:
            print("  ⚠️  No game data")
            return False

        # Get first game and check all stat fields
        sample_game = game_log[0]

        print("\nSample game stats available:")

        stat_fields = [
            ('points', 'Points'),
            ('rebounds', 'Rebounds'),
            ('assists', 'Assists'),
            ('steals', 'Steals'),
            ('blocks', 'Blocks'),
            ('turnovers', 'Turnovers'),
            ('field_goals_made', 'FG Made'),
            ('field_goals_attempted', 'FG Attempted'),
            ('three_pointers_made', '3PT Made'),
            ('three_pointers_attempted', '3PT Attempted'),
            ('free_throws_made', 'FT Made'),
            ('free_throws_attempted', 'FT Attempted'),
            ('minutes', 'Minutes'),
            ('plus_minus', '+/-')
        ]

        available_stats = []
        missing_stats = []

        for field, label in stat_fields:
            value = sample_game.get(field)
            if value is not None:
                print(f"  ✓ {label}: {value}")
                available_stats.append(label)
            else:
                print(f"  ❌ {label}: Missing")
                missing_stats.append(label)

        print(f"\n  Available: {len(available_stats)}/{len(stat_fields)} stat types")

        success = len(available_stats) >= 10
        if success:
            print("  ✅ Sufficient stats available for predictions")
        else:
            print("  ⚠️  Some stats missing")

        return success

    finally:
        db.close()


def test_6_historical_data():
    """Test 6: Check how much historical data we can access"""
    print_section("TEST 6: Historical Data Availability")

    nba_client = NBAAPIClient()
    db = SessionLocal()

    try:
        player = db.query(Player).filter(
            Player.full_name.like("%Kevin Durant%")
        ).first()

        if not player:
            print("  ❌ Could not find test player")
            return False

        print(f"\nPlayer: {player.full_name}")

        # Try to fetch multiple seasons
        seasons_to_test = [
            "2024-25",  # Current
            "2023-24",  # Last
            "2022-23",  # 2 years ago
        ]

        season_data = {}

        for season in seasons_to_test:
            print(f"\nFetching {season}...")
            game_log = nba_client.get_player_game_log(
                player_id=player.nba_player_id,
                season=season
            )

            games_count = len(game_log) if game_log else 0
            season_data[season] = games_count

            if games_count > 0:
                print(f"  ✓ {games_count} games available")
            else:
                print(f"  - No games (might be off-season)")

        total_games = sum(season_data.values())
        print(f"\n✓ Total historical games accessible: {total_games}")

        if total_games > 100:
            print("  ✅ Excellent - sufficient training data!")
        elif total_games > 50:
            print("  ✅ Good - adequate training data")
        else:
            print("  ⚠️  Limited data available")

        return total_games > 50

    finally:
        db.close()


def test_7_database_storage():
    """Test 7: Verify we can store stats in database"""
    print_section("TEST 7: Database Storage")

    db = SessionLocal()

    try:
        # Check if we have any games/stats in database
        games_count = db.query(Game).count()
        stats_count = db.query(PlayerGameStats).count()

        print(f"\nCurrent database state:")
        print(f"  Games stored: {games_count}")
        print(f"  Player game stats stored: {stats_count}")

        if games_count > 0 and stats_count > 0:
            # Show sample data
            sample_stat = db.query(PlayerGameStats).first()

            if sample_stat:
                player = db.query(Player).get(sample_stat.player_id)
                game = db.query(Game).get(sample_stat.game_id)

                print(f"\nSample stored stat:")
                print(f"  Player: {player.full_name if player else 'N/A'}")
                print(f"  Game: {game.game_date if game else 'N/A'}")
                print(f"  Points: {sample_stat.points}")
                print(f"  Rebounds: {sample_stat.rebounds}")
                print(f"  Assists: {sample_stat.assists}")

            print("\n  ✅ Database storage working!")
            return True
        else:
            print("\n  ℹ️  Database is empty - this is normal for fresh setup")
            print("     Run daily_workflow.py to populate")
            return None  # Not a failure, just empty

    finally:
        db.close()


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*70)
    print("  NBA PROPS DATA VERIFICATION PROTOCOL")
    print("  Testing all data sources for predictions")
    print("="*70)

    results = {}

    # Run tests
    print("\n🧪 Starting tests...\n")

    results['Database Setup'] = test_1_database_setup()

    success, found_players = test_2_player_info()
    results['Player Info'] = success

    results['Fetch Stats'] = test_3_fetch_player_stats()
    results['Opponent Tracking'] = test_4_opponent_tracking()
    results['All Stat Types'] = test_5_all_stat_types()
    results['Historical Data'] = test_6_historical_data()
    results['Database Storage'] = test_7_database_storage()

    # Summary
    print_section("TEST SUMMARY")

    print("\nResults:")
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "ℹ️  N/A"

        print(f"  {status} - {test_name}")

    # Overall verdict
    passes = sum(1 for r in results.values() if r is True)
    fails = sum(1 for r in results.values() if r is False)
    total = len([r for r in results.values() if r is not None])

    print(f"\nOverall: {passes}/{total} tests passed")

    if fails == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nNext steps:")
        print("  1. Run: python scripts/daily_workflow.py")
        print("  2. This will collect today's games and generate predictions")
        print("  3. Check the web app dashboard to see plays")
    elif fails <= 2:
        print("\n⚠️  MOSTLY WORKING - Minor issues detected")
        print("   System should still work for predictions")
    else:
        print("\n❌ MULTIPLE FAILURES")
        print("   Check the errors above and fix before proceeding")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    # Install tabulate if not present
    try:
        import tabulate
    except ImportError:
        print("Installing tabulate for better output formatting...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "-q", "tabulate"])
        import tabulate

    run_all_tests()
