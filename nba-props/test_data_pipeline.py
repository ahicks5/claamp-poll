#!/usr/bin/env python3
"""
Quick test of NBA props data collection
Tests: games, odds, and predictions
"""
import sys
import os
from datetime import date, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import SessionLocal
from database.models import Team, Player, Game, PropLine, Prediction
from services.nba_api_client import NBAAPIClient
from services.odds_api_client import OddsAPIClient

def test_games():
    """Test fetching today's NBA games"""
    print("\n" + "="*60)
    print("🏀 TESTING: Fetch Today's Games")
    print("="*60)

    nba_client = NBAAPIClient()
    db = SessionLocal()

    try:
        today = date.today()
        print(f"\nFetching games for {today}...")

        # Fetch games from NBA API
        games_data = nba_client.get_games_for_date(today)
        print(f"✓ Found {len(games_data)} games from NBA API")

        if len(games_data) == 0:
            print("\n⚠️  No games today. Trying tomorrow...")
            tomorrow = today + timedelta(days=1)
            games_data = nba_client.get_games_for_date(tomorrow)
            print(f"✓ Found {len(games_data)} games for {tomorrow}")

        # Show game details
        for i, game in enumerate(games_data[:5], 1):
            print(f"\n  Game {i}:")
            print(f"    {game.get('away_team_name', 'Unknown')} @ {game.get('home_team_name', 'Unknown')}")
            print(f"    Date: {game.get('game_date')}")
            print(f"    Status: {game.get('status', 'Unknown')}")

        return len(games_data) > 0

    finally:
        db.close()


def test_odds():
    """Test fetching odds from The Odds API"""
    print("\n" + "="*60)
    print("💰 TESTING: Fetch Odds from The Odds API")
    print("="*60)

    odds_client = OddsAPIClient()

    try:
        print("\nFetching NBA player props odds...")

        # Test API connection
        props = odds_client.get_player_props(sport='basketball_nba', market='player_points')
        print(f"✓ Successfully connected to Odds API")
        print(f"✓ Found {len(props)} player props for POINTS")

        if len(props) > 0:
            # Show sample props
            print("\n  Sample props:")
            for i, prop in enumerate(props[:3], 1):
                player = prop.get('player_name', 'Unknown')
                line = prop.get('point', 'N/A')
                over_odds = prop.get('over_odds', 'N/A')
                under_odds = prop.get('under_odds', 'N/A')
                print(f"    {i}. {player}: O/U {line} (odds: {over_odds}/{under_odds})")

        return len(props) > 0

    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        print("\n⚠️  This might be due to:")
        print("   - Invalid/expired API key")
        print("   - No games available today")
        print("   - API rate limit reached")
        return False


def test_database_check():
    """Check what's currently in the database"""
    print("\n" + "="*60)
    print("📊 DATABASE STATUS")
    print("="*60)

    db = SessionLocal()

    try:
        teams = db.query(Team).count()
        players = db.query(Player).count()
        games = db.query(Game).count()
        props = db.query(PropLine).count()
        predictions = db.query(Prediction).count()

        print(f"\n  Teams: {teams}")
        print(f"  Players: {players}")
        print(f"  Games: {games}")
        print(f"  Prop Lines: {props}")
        print(f"  Predictions: {predictions}")

        # Check for recent data
        today = date.today()
        todays_games = db.query(Game).filter(Game.game_date == today).count()
        recent_props = db.query(PropLine).filter(PropLine.is_latest == True).count()

        print(f"\n  Today's games in DB: {todays_games}")
        print(f"  Latest prop lines in DB: {recent_props}")

    finally:
        db.close()


def main():
    print("\n" + "="*60)
    print("🧪 NBA PROPS DATA PIPELINE TEST")
    print("="*60)
    print("\nThis will test:")
    print("  1. Database status")
    print("  2. Fetching games from NBA API")
    print("  3. Fetching odds from The Odds API")
    print("\n")

    # Test 1: Database
    test_database_check()

    # Test 2: Games
    games_ok = test_games()

    # Test 3: Odds
    odds_ok = test_odds()

    # Summary
    print("\n" + "="*60)
    print("📋 TEST SUMMARY")
    print("="*60)
    print(f"\n  Database: ✓ Working")
    print(f"  NBA Games API: {'✓ Working' if games_ok else '❌ No games found'}")
    print(f"  Odds API: {'✓ Working' if odds_ok else '❌ Failed (check API key or no games)'}")

    if games_ok and odds_ok:
        print("\n✅ ALL SYSTEMS GO! Ready to collect data.")
        print("\nNext steps:")
        print("  1. Run: python scripts/daily_workflow.py")
        print("  2. This will collect games, odds, and generate predictions")
    elif games_ok:
        print("\n⚠️  Games API working, but Odds API failed.")
        print("   Check your ODDS_API_KEY in .env file")
    else:
        print("\n⚠️  No games available today.")
        print("   Try again on a game day!")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
