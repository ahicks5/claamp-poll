#!/usr/bin/env python3
# scripts/generate_predictions_regression.py
"""Generate predictions using the regression model (stats-only)."""
import sys
import os
import logging
import pickle
from datetime import datetime
import pandas as pd

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Player, Game, PropLine
from services.feature_calculator import FeatureCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RegressionPredictionGenerator:
    """Generate predictions using regression model."""

    def __init__(self, prop_type: str = 'points', min_edge: float = 2.0):
        self.session = get_session()
        self.feature_calc = FeatureCalculator(self.session)
        self.prop_type = prop_type
        self.min_edge = min_edge  # Minimum predicted edge to recommend
        self.model = None
        self.feature_cols = None

        self._load_model()

    def _load_model(self):
        """Load trained regression model."""
        models_dir = os.path.join(PROJECT_ROOT, 'models')
        model_path = os.path.join(models_dir, f'{self.prop_type}_regression_model.pkl')
        features_path = os.path.join(models_dir, f'{self.prop_type}_regression_features.pkl')

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Regression model not found: {model_path}. "
                f"Run train_model_no_odds.py first to train the model."
            )

        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        with open(features_path, 'rb') as f:
            self.feature_cols = pickle.load(f)

        logger.info(f"Loaded regression model for {self.prop_type}")

    def generate_predictions_for_today(self) -> pd.DataFrame:
        """Generate predictions for today's props."""
        logger.info("Generating predictions for today's props...")

        today = datetime.now().date()

        # Get today's games with prop lines
        props = self.session.query(PropLine).join(Game).filter(
            Game.game_date == today,
            Game.status == 'scheduled',
            PropLine.prop_type == self.prop_type,
            PropLine.is_latest == True
        ).all()

        logger.info(f"Found {len(props)} props for {self.prop_type} today")

        predictions = []

        for prop in props:
            try:
                # Get player
                player = self.session.query(Player).get(prop.player_id)
                if not player:
                    continue

                # Get game
                game = self.session.query(Game).get(prop.game_id)
                if not game:
                    continue

                # Calculate features
                features = self.feature_calc.calculate_player_features(
                    player_id=prop.player_id,
                    game_date=game.game_date,
                    prop_type=self.prop_type,
                    lookback_games=20
                )

                if not features:
                    logger.warning(f"Could not calculate features for {player.full_name}")
                    continue

                # Add home/away
                features['is_home'] = 1 if player.team_id == game.home_team_id else 0

                # Prepare features for model
                feature_vector = []
                for col in self.feature_cols:
                    feature_vector.append(features.get(col, 0))

                # Make prediction (predicts actual value)
                predicted_value = self.model.predict([feature_vector])[0]

                # Calculate edge (how much over/under the line)
                edge = predicted_value - prop.line_value

                # Determine recommendation based on edge
                if edge >= self.min_edge:
                    recommendation = 'OVER'
                    confidence = min(0.5 + (edge / 20), 0.95)  # Rough confidence estimate
                elif edge <= -self.min_edge:
                    recommendation = 'UNDER'
                    confidence = min(0.5 + (abs(edge) / 20), 0.95)
                else:
                    recommendation = 'NO PLAY'
                    confidence = 0.5

                predictions.append({
                    'player_name': player.full_name,
                    'player_id': prop.player_id,
                    'game_id': game.id,
                    'prop_type': self.prop_type,
                    'line': prop.line_value,
                    'predicted_value': predicted_value,
                    'edge': edge,
                    'recommendation': recommendation,
                    'confidence': confidence,
                    'sportsbook': prop.sportsbook,
                    # Context
                    'last_10_avg': features.get(f'{self.prop_type}_avg_last_10', 0),
                    'season_avg': features.get(f'{self.prop_type}_season_avg', 0),
                    'minutes_avg': features.get('minutes_avg', 0),
                    'is_home': features.get('is_home', 0)
                })

            except Exception as e:
                logger.error(f"Error generating prediction for {player.full_name}: {e}")
                continue

        df = pd.DataFrame(predictions)

        if len(df) > 0:
            # Sort by absolute edge (highest first)
            df = df.sort_values('edge', key=abs, ascending=False)

        return df

    def display_predictions(self, predictions_df: pd.DataFrame):
        """Display predictions in a user-friendly format."""
        if len(predictions_df) == 0:
            logger.info("No predictions generated")
            return

        logger.info("\n" + "="*100)
        logger.info(f"PREDICTIONS FOR {self.prop_type.upper()} - {datetime.now().strftime('%Y-%m-%d')}")
        logger.info("="*100)

        # Only show plays we're recommending
        plays = predictions_df[predictions_df['recommendation'] != 'NO PLAY']

        if len(plays) == 0:
            logger.info(f"\nNo plays with edge >= {self.min_edge:.1f} points")
            logger.info(f"Try lowering --min-edge threshold")
            return

        logger.info(f"\nFound {len(plays)} recommended plays (min edge: {self.min_edge:.1f} points)")

        # Group by recommendation
        overs = plays[plays['recommendation'] == 'OVER'].sort_values('edge', ascending=False)
        unders = plays[plays['recommendation'] == 'UNDER'].sort_values('edge', ascending=True)

        if len(overs) > 0:
            logger.info(f"\nOVER PLAYS ({len(overs)} plays)")
            logger.info("-"*100)

            for _, row in overs.head(20).iterrows():
                home_away = "HOME" if row['is_home'] else "AWAY"
                logger.info(f"\n{row['player_name']:25s} | OVER {row['line']:.1f} ({home_away})")
                logger.info(f"  Predicted: {row['predicted_value']:.1f} | Edge: +{row['edge']:.1f} points")
                logger.info(f"  Last 10 Avg: {row['last_10_avg']:.1f} | Season Avg: {row['season_avg']:.1f} | Minutes: {row['minutes_avg']:.1f}")
                logger.info(f"  Sportsbook: {row['sportsbook']}")

        if len(unders) > 0:
            logger.info(f"\nUNDER PLAYS ({len(unders)} plays)")
            logger.info("-"*100)

            for _, row in unders.head(20).iterrows():
                home_away = "HOME" if row['is_home'] else "AWAY"
                logger.info(f"\n{row['player_name']:25s} | UNDER {row['line']:.1f} ({home_away})")
                logger.info(f"  Predicted: {row['predicted_value']:.1f} | Edge: {row['edge']:.1f} points")
                logger.info(f"  Last 10 Avg: {row['last_10_avg']:.1f} | Season Avg: {row['season_avg']:.1f} | Minutes: {row['minutes_avg']:.1f}")
                logger.info(f"  Sportsbook: {row['sportsbook']}")

        # Summary
        logger.info("\n" + "="*100)
        logger.info("SUMMARY")
        logger.info("="*100)
        logger.info(f"Total Recommended Plays: {len(plays)}")
        logger.info(f"  OVER: {len(overs)}")
        logger.info(f"  UNDER: {len(unders)}")
        logger.info(f"Average Edge: {plays['edge'].abs().mean():.2f} points")
        logger.info(f"Average Predicted Confidence: {plays['confidence'].mean():.1%}")
        logger.info(f"\nNote: Using regression model (stats-only). Confidence is estimated from edge size.")

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main prediction generation script."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate predictions using regression model')
    parser.add_argument(
        '--prop-type',
        default='points',
        help='Type of prop to predict'
    )
    parser.add_argument(
        '--min-edge',
        type=float,
        default=2.0,
        help='Minimum edge (in points) to recommend a play'
    )

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("NBA PROPS PREDICTION GENERATOR (Regression)")
    logger.info("="*60)

    generator = RegressionPredictionGenerator(
        prop_type=args.prop_type,
        min_edge=args.min_edge
    )

    try:
        # Generate predictions
        predictions = generator.generate_predictions_for_today()

        # Display
        generator.display_predictions(predictions)

        logger.info("\n[OK] Prediction generation complete!")

    except FileNotFoundError as e:
        logger.error(f"\n{e}")
        logger.error("Train a regression model first using: python scripts/train_model_no_odds.py")
    except Exception as e:
        logger.error(f"Prediction generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        generator.close()


if __name__ == "__main__":
    main()
