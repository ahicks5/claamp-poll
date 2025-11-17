#!/usr/bin/env python3
"""Test the API endpoints to see actual errors"""
import sys
import os

# Add nba-props to path (same as routes.py does)
NBA_PROPS_DIR = os.path.join(os.path.dirname(__file__), 'nba-props')
sys.path.insert(0, NBA_PROPS_DIR)

print(f"NBA_PROPS_DIR: {NBA_PROPS_DIR}")
print(f"Path exists: {os.path.exists(NBA_PROPS_DIR)}")
print(f"sys.path[0]: {sys.path[0]}")
print()

try:
    print("Testing imports...")
    from database import get_session, Prediction, Result, Player, Game
    print("✓ Imports successful")

    session = get_session()
    print("✓ Session created")

    # Test query
    pred_count = session.query(Prediction).count()
    print(f"✓ Predictions in DB: {pred_count}")

    result_count = session.query(Result).count()
    print(f"✓ Results in DB: {result_count}")

    # Test relationship
    pred = session.query(Prediction).first()
    if pred:
        print(f"✓ Found prediction ID: {pred.id}")
        print(f"  Has result: {pred.result}")

    # Test the actual query from api_stats
    correct_results = session.query(Result).filter(Result.was_correct == True).count()
    print(f"✓ Correct results: {correct_results}")

    session.close()
    print("\n✅ All tests passed!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
