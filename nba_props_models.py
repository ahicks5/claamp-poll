"""
Bridge module to access NBA props predictions from main app
Handles the separate database connection
"""
import sys
import os
from datetime import date
from typing import List, Dict

# Add nba-props to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'nba-props'))

from database import models as nba_models
from database.db import SessionLocal as NBASessionLocal


def get_todays_predictions() -> List[Dict]:
    """
    Get today's predictions from NBA props database

    Returns:
        List of prediction dicts with all relevant data
    """
    nba_db = NBASessionLocal()
    predictions = []

    try:
        today = date.today()

        # Query predictions with recommended picks
        predictions_query = (
            nba_db.query(nba_models.Prediction)
            .join(nba_models.Game)
            .filter(nba_models.Game.game_date == today)
            .filter(nba_models.Prediction.recommended_pick.isnot(None))
            .all()
        )

        for pred in predictions_query:
            # Load related data
            player = nba_db.query(nba_models.Player).get(pred.player_id)
            game = nba_db.query(nba_models.Game).get(pred.game_id)
            home_team = nba_db.query(nba_models.Team).get(game.home_team_id) if game else None
            away_team = nba_db.query(nba_models.Team).get(game.away_team_id) if game else None

            # Get prop line for odds (most recent)
            prop_line = (
                nba_db.query(nba_models.PropLine)
                .filter(
                    nba_models.PropLine.player_id == pred.player_id,
                    nba_models.PropLine.game_id == pred.game_id,
                    nba_models.PropLine.prop_type == pred.prop_type,
                    nba_models.PropLine.is_latest == True
                )
                .first()
            )

            # Determine odds based on pick direction
            if prop_line:
                if pred.recommended_pick and pred.recommended_pick.lower() == 'over':
                    odds = prop_line.over_odds or -110
                else:
                    odds = prop_line.under_odds or -110
            else:
                odds = -110  # Default

            predictions.append({
                'id': pred.id,
                'player_name': player.full_name if player else "Unknown",
                'game_description': f"{away_team.abbreviation} @ {home_team.abbreviation}" if (away_team and home_team) else "Unknown",
                'game_date': game.game_date if game else today,
                'prop_type': pred.prop_type,
                'predicted_value': pred.predicted_value,
                'line_value': pred.line_value,
                'edge': pred.edge,
                'confidence': pred.confidence_score,
                'recommended_pick': pred.recommended_pick,
                'odds': odds
            })

    finally:
        nba_db.close()

    return predictions


def get_prediction_by_id(prediction_id: int) -> Dict:
    """Get a single prediction by ID"""
    nba_db = NBASessionLocal()

    try:
        pred = nba_db.query(nba_models.Prediction).get(prediction_id)
        if not pred:
            return None

        player = nba_db.query(nba_models.Player).get(pred.player_id)
        game = nba_db.query(nba_models.Game).get(pred.game_id)
        home_team = nba_db.query(nba_models.Team).get(game.home_team_id) if game else None
        away_team = nba_db.query(nba_models.Team).get(game.away_team_id) if game else None

        return {
            'id': pred.id,
            'player_name': player.full_name if player else "Unknown",
            'game_description': f"{away_team.abbreviation} @ {home_team.abbreviation}" if (away_team and home_team) else "Unknown",
            'game_date': game.game_date if game else date.today(),
            'prop_type': pred.prop_type,
            'predicted_value': pred.predicted_value,
            'line_value': pred.line_value,
            'edge': pred.edge,
            'confidence': pred.confidence_score,
            'recommended_pick': pred.recommended_pick
        }

    finally:
        nba_db.close()


# For testing
if __name__ == "__main__":
    predictions = get_todays_predictions()
    print(f"Found {len(predictions)} predictions for today")
    for p in predictions[:5]:
        print(f"  {p['player_name']}: {p['prop_type']} {p['recommended_pick']} {p['line_value']} (edge: {p['edge']:.1f})")
