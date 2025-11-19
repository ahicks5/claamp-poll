#!/usr/bin/env python3
"""Diagnostic script to check the state of the NBA props system."""
import sys
import os

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Player, Team, Game, PropLine, Prediction, Result, PlayerGameStats
from datetime import datetime, timedelta

def main():
    session = get_session()

    print("=" * 60)
    print("NBA PROPS SYSTEM DIAGNOSTIC")
    print("=" * 60)
    print()

    # Check teams
    team_count = session.query(Team).count()
    print(f"✓ Teams in database: {team_count}")

    # Check players
    player_count = session.query(Player).count()
    print(f"✓ Players in database: {player_count}")

    # Check games (last 30 days)
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    game_count = session.query(Game).filter(Game.game_date >= thirty_days_ago).count()
    print(f"✓ Games (last 30 days): {game_count}")

    # Check prop lines
    prop_count = session.query(PropLine).count()
    print(f"✓ Prop lines in database: {prop_count}")

    # Check predictions
    pred_count = session.query(Prediction).count()
    print(f"✓ Predictions in database: {pred_count}")

    # Check results
    result_count = session.query(Result).count()
    print(f"✓ Results tracked: {result_count}")

    # Check player game stats
    stats_count = session.query(PlayerGameStats).count()
    print(f"✓ Player game stats: {stats_count}")

    print()
    print("=" * 60)
    print("DIAGNOSIS:")
    print("=" * 60)

    if team_count == 0:
        print("❌ No teams found - database initialization didn't complete")
    elif team_count < 30:
        print(f"⚠️  Only {team_count} teams (should be 30)")
    else:
        print("✓ Teams loaded correctly")

    if player_count == 0:
        print("❌ No players found - database initialization didn't complete")
    elif player_count < 100:
        print(f"⚠️  Only {player_count} players (should be 400+)")
    else:
        print(f"✓ Players loaded correctly ({player_count} players)")

    if game_count == 0:
        print("❌ No recent games - need to run data collection")
        print("   → Run: python scripts/collect_daily_data.py")
    else:
        print(f"✓ Found {game_count} games from last 30 days")

    if prop_count == 0:
        print("❌ No prop lines - need to collect from Odds API")
        print("   → Requires ODDS_API_KEY environment variable")
        print("   → Run: python scripts/daily_workflow.py")
    else:
        print(f"✓ Found {prop_count} prop lines")

    if pred_count == 0:
        print("❌ No predictions - this is why your dashboard is empty!")
        print("   → Need to train model and generate predictions")
        print("   → Run: python scripts/daily_workflow.py")
    else:
        print(f"✓ Found {pred_count} predictions")

        # Show recent predictions
        recent = session.query(Prediction).join(Game).filter(
            Game.game_date >= thirty_days_ago
        ).limit(5).all()

        if recent:
            print(f"\n   Recent predictions:")
            for pred in recent:
                player = session.query(Player).get(pred.player_id)
                game = session.query(Game).get(pred.game_id)
                print(f"   - {player.full_name}: {pred.prop_type} {pred.recommended_pick} {pred.line_value} ({game.game_date})")

    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)

    if pred_count == 0:
        print("\nYour dashboard is empty because there are no predictions.")
        print("\nTo fix this, you need to:")
        print("1. Have historical game data (for model training)")
        print("2. Train a prediction model")
        print("3. Get today's prop lines from Odds API")
        print("4. Generate predictions")
        print("\nOR for testing:")
        print("→ Create sample predictions to test the dashboard")

    session.close()

if __name__ == "__main__":
    main()
