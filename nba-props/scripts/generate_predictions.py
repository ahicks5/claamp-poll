#!/usr/bin/env python3
# scripts/generate_predictions.py
"""Generate predictions for today's NBA props using trained model."""
import sys
import os
import logging
import pickle
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Player, Game, PropLine, Prediction
from services.feature_calculator import FeatureCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PredictionGenerator:
    """Generate predictions for upcoming games."""

    def __init__(self, prop_type: str = 'points', min_confidence: float = 0.60):
        self.session = get_session()
        self.feature_calc = FeatureCalculator(self.session)
        self.prop_type = prop_type
        self.min_confidence = min_confidence
        self.model = None
        self.feature_cols = None

        self._load_model()

    def _load_model(self):
        """Load trained model and feature list."""
        models_dir = os.path.join(PROJECT_ROOT, 'models')
        model_path = os.path.join(models_dir, f'{self.prop_type}_model.pkl')
        features_path = os.path.join(models_dir, f'{self.prop_type}_features.pkl')

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found: {model_path}. "
                f"Run train_model.py first to train the model."
            )

        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        with open(features_path, 'rb') as f:
            self.feature_cols = pickle.load(f)

        logger.info(f"Loaded model for {self.prop_type} with {len(self.feature_cols)} features")

    def generate_predictions_for_today(self) -> pd.DataFrame:
        """
        Generate predictions for all props available today.

        Returns:
            DataFrame with predictions and recommendations
        """
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

                # Add prop line features
                line_features = self.feature_calc.calculate_prop_line_features(
                    player_id=prop.player_id,
                    game_id=game.id,
                    prop_type=self.prop_type,
                    current_line=prop.line_value
                )
                features.update(line_features)

                # Add streak features
                streak_features = self.feature_calc.calculate_streak_features(
                    player_id=prop.player_id,
                    game_date=game.game_date,
                    prop_type=self.prop_type
                )
                features.update(streak_features)

                # Prepare features for model
                feature_vector = []
                for col in self.feature_cols:
                    feature_vector.append(features.get(col, 0))

                # Make prediction
                pred_proba = self.model.predict_proba([feature_vector])[0]
                over_prob = pred_proba[1]
                under_prob = pred_proba[0]

                # Determine recommendation
                confidence = max(over_prob, under_prob)

                if over_prob > self.min_confidence:
                    recommendation = 'OVER'
                elif under_prob > self.min_confidence:
                    recommendation = 'UNDER'
                else:
                    recommendation = 'NO PLAY'

                # Predicted value
                predicted_value = features.get(f'{self.prop_type}_avg_last_10', prop.line_value)

                # Edge (difference from line)
                edge = predicted_value - prop.line_value

                predictions.append({
                    'player_name': player.full_name,
                    'player_id': prop.player_id,
                    'game_id': game.id,
                    'prop_type': self.prop_type,
                    'line': prop.line_value,
                    'predicted_value': predicted_value,
                    'over_prob': over_prob,
                    'under_prob': under_prob,
                    'confidence': confidence,
                    'recommendation': recommendation,
                    'edge': edge,
                    'sportsbook': prop.sportsbook,
                    # Key factors for review
                    'last_10_avg': features.get(f'{self.prop_type}_avg_last_10', 0),
                    'over_streak': streak_features.get('over_streak', 0),
                    'under_streak': streak_features.get('under_streak', 0),
                    'hit_rate_last_5': streak_features.get('hit_rate_last_5', 0),
                    'sharp_movement': line_features.get('sharp_movement', 0),
                    'is_sharp_movement': line_features.get('is_sharp_movement', 0),
                    'minutes_avg': features.get('minutes_avg', 0)
                })

            except Exception as e:
                logger.error(f"Error generating prediction for {player.full_name}: {e}")
                continue

        df = pd.DataFrame(predictions)

        if len(df) > 0:
            # Sort by confidence (highest first)
            df = df.sort_values('confidence', ascending=False)

        return df

    def save_predictions_to_db(self, predictions_df: pd.DataFrame):
        """Save predictions to database."""
        logger.info("Saving predictions to database...")

        saved_count = 0

        for _, row in predictions_df.iterrows():
            if row['recommendation'] == 'NO PLAY':
                continue

            prediction = Prediction(
                player_id=row['player_id'],
                game_id=row['game_id'],
                prop_type=row['prop_type'],
                predicted_value=row['predicted_value'],
                line_value=row['line'],
                model_version='xgboost_v1',
                confidence_score=row['confidence'],
                recommended_pick=row['recommendation'].lower(),
                edge=row['edge'],
                features_json=None  # Could store features here if needed
            )

            self.session.add(prediction)
            saved_count += 1

        self.session.commit()
        logger.info(f"Saved {saved_count} predictions to database")

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
            logger.info("\nNo plays meet the minimum confidence threshold")
            return

        logger.info(f"\nFound {len(plays)} recommended plays (min confidence: {self.min_confidence:.0%})")

        # Group by confidence level
        high_conf = plays[plays['confidence'] >= 0.70]
        med_conf = plays[(plays['confidence'] >= 0.65) & (plays['confidence'] < 0.70)]
        low_conf = plays[(plays['confidence'] >= self.min_confidence) & (plays['confidence'] < 0.65)]

        for conf_level, subset, label in [
            (0.70, high_conf, "HIGH CONFIDENCE PLAYS"),
            (0.65, med_conf, "MEDIUM CONFIDENCE PLAYS"),
            (self.min_confidence, low_conf, "LOW CONFIDENCE PLAYS")
        ]:
            if len(subset) == 0:
                continue

            logger.info(f"\n{label} ({len(subset)} plays)")
            logger.info("-"*100)

            for _, row in subset.iterrows():
                logger.info(f"\n{row['player_name']:25s} | {row['recommendation']:6s} {row['line']:.1f}")
                logger.info(f"  Confidence: {row['confidence']:.1%} | Predicted: {row['predicted_value']:.1f} | Edge: {row['edge']:+.1f}")
                logger.info(f"  Last 10 Avg: {row['last_10_avg']:.1f} | Minutes: {row['minutes_avg']:.1f}")

                # Show streak info
                if row['over_streak'] > 0:
                    logger.info(f"  Streak: {int(row['over_streak'])} consecutive OVERS")
                elif row['under_streak'] > 0:
                    logger.info(f"  Streak: {int(row['under_streak'])} consecutive UNDERS")

                logger.info(f"  Hit Rate (last 5): {row['hit_rate_last_5']:.1%}")

                # Flag sharp movements
                if row['is_sharp_movement']:
                    logger.info(f"  [!] SHARP LINE MOVEMENT: {row['sharp_movement']:.1f} point move - Vegas Trap?")

                logger.info(f"  Sportsbook: {row['sportsbook']}")

        # Summary statistics
        logger.info("\n" + "="*100)
        logger.info("SUMMARY")
        logger.info("="*100)
        logger.info(f"Total Recommended Plays: {len(plays)}")
        logger.info(f"  OVER: {len(plays[plays['recommendation'] == 'OVER'])}")
        logger.info(f"  UNDER: {len(plays[plays['recommendation'] == 'UNDER'])}")
        logger.info(f"Average Confidence: {plays['confidence'].mean():.1%}")
        logger.info(f"Average Edge: {plays['edge'].abs().mean():.2f} points")
        sharp_plays = plays[plays['is_sharp_movement'] == 1]
        if len(sharp_plays) > 0:
            logger.info(f"Plays with Sharp Line Movement: {len(sharp_plays)} (Vegas traps - BEWARE!)")

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main prediction generation script."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate predictions for NBA props')
    parser.add_argument(
        '--prop-type',
        default='points',
        help='Type of prop to predict (points, rebounds, assists, etc.)'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.60,
        help='Minimum confidence to recommend a play (0.0-1.0)'
    )
    parser.add_argument(
        '--save-to-db',
        action='store_true',
        help='Save predictions to database'
    )

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("NBA PROPS PREDICTION GENERATOR")
    logger.info("="*60)

    generator = PredictionGenerator(
        prop_type=args.prop_type,
        min_confidence=args.min_confidence
    )

    try:
        # Generate predictions
        predictions = generator.generate_predictions_for_today()

        # Display
        generator.display_predictions(predictions)

        # Save to database if requested
        if args.save_to_db and len(predictions) > 0:
            generator.save_predictions_to_db(predictions)

        logger.info("\n[OK] Prediction generation complete!")

    except FileNotFoundError as e:
        logger.error(f"\n{e}")
        logger.error("Train a model first using: python scripts/train_model.py")
    except Exception as e:
        logger.error(f"Prediction generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        generator.close()


if __name__ == "__main__":
    main()
