#!/usr/bin/env python3
# scripts/train_model_no_odds.py
"""Train ML model using only historical stats (no prop lines needed)."""
import sys
import os
import logging
import pickle
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Player, Game, PlayerGameStats
from services.feature_calculator import FeatureCalculator

# ML libraries
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StatsPredictorTrainer:
    """
    Train model to predict ACTUAL stat values (not just over/under).
    Can be used even without historical prop lines.
    """

    def __init__(self, prop_type: str = 'points'):
        self.session = get_session()
        self.feature_calc = FeatureCalculator(self.session)
        self.prop_type = prop_type
        self.model = None

    def prepare_training_data(
        self,
        start_date: datetime.date = None,
        end_date: datetime.date = None,
        min_games: int = 15
    ) -> pd.DataFrame:
        """
        Prepare training data from historical games (NO ODDS NEEDED).

        Args:
            start_date: Start date for training data
            end_date: End date for training data
            min_games: Minimum number of games player must have

        Returns:
            DataFrame with features and actual values
        """
        logger.info(f"Preparing training data for {self.prop_type} (stats-only mode)...")

        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now().date()

        # Get all completed games in date range
        games = self.session.query(Game).filter(
            Game.game_date >= start_date,
            Game.game_date <= end_date,
            Game.status == 'final'
        ).all()

        logger.info(f"Found {len(games)} completed games")

        training_data = []

        for game in games:
            # Get all player stats for this game
            player_stats_list = self.session.query(PlayerGameStats).filter(
                PlayerGameStats.game_id == game.id
            ).all()

            for stats in player_stats_list:
                # Get actual stat value (target)
                actual_value = self.feature_calc._get_stat_value(stats, self.prop_type)

                if actual_value is None or actual_value == 0:
                    continue

                # Calculate features (using data from BEFORE this game)
                features = self.feature_calc.calculate_player_features(
                    player_id=stats.player_id,
                    game_date=game.game_date,
                    prop_type=self.prop_type,
                    lookback_games=20
                )

                if not features:
                    continue

                # Check if player has enough history
                if features.get(f'{self.prop_type}_season_avg', 0) == 0:
                    continue

                # Add game context features
                player = self.session.query(Player).get(stats.player_id)
                if player:
                    # Is this a home game?
                    features['is_home'] = 1 if player.team_id == game.home_team_id else 0

                # Add metadata
                features['player_id'] = stats.player_id
                features['game_id'] = game.id
                features['game_date'] = game.game_date
                features['actual_value'] = actual_value
                features['target'] = actual_value  # What we're predicting

                training_data.append(features)

        df = pd.DataFrame(training_data)

        logger.info(f"Prepared {len(df)} training samples")
        logger.info(f"Target stats - Mean: {df['target'].mean():.2f}, Std: {df['target'].std():.2f}")

        return df

    def train(
        self,
        df: pd.DataFrame,
        test_split: float = 0.2,
        save_model: bool = True
    ):
        """
        Train regression model to predict actual stat values.

        Args:
            df: Training dataframe
            test_split: Fraction of data to use for testing
            save_model: Whether to save the trained model
        """
        logger.info("Training regression model...")

        # Remove metadata columns
        feature_cols = [col for col in df.columns if col not in [
            'player_id', 'game_id', 'game_date', 'target', 'actual_value'
        ]]

        # Handle missing values
        df_features = df[feature_cols].fillna(0)

        # Time-based split
        df_sorted = df.sort_values('game_date')
        split_idx = int(len(df_sorted) * (1 - test_split))

        train_df = df_sorted.iloc[:split_idx]
        test_df = df_sorted.iloc[split_idx:]

        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df['target']

        X_test = test_df[feature_cols].fillna(0)
        y_test = test_df['target']

        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Test set: {len(X_test)} samples")

        # Train XGBoost regressor
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )

        self.model.fit(X_train, y_train)

        # Evaluate
        train_preds = self.model.predict(X_train)
        test_preds = self.model.predict(X_test)

        train_mae = mean_absolute_error(y_train, train_preds)
        test_mae = mean_absolute_error(y_test, test_preds)

        train_rmse = np.sqrt(mean_squared_error(y_train, train_preds))
        test_rmse = np.sqrt(mean_squared_error(y_test, test_preds))

        logger.info("\n" + "="*60)
        logger.info("MODEL PERFORMANCE (Regression)")
        logger.info("="*60)
        logger.info(f"\nTraining MAE: {train_mae:.2f} {self.prop_type}")
        logger.info(f"Training RMSE: {train_rmse:.2f} {self.prop_type}")
        logger.info(f"\nTest MAE: {test_mae:.2f} {self.prop_type}")
        logger.info(f"Test RMSE: {test_rmse:.2f} {self.prop_type}")

        # Analyze predictions
        test_df = test_df.copy()
        test_df['predicted'] = test_preds
        test_df['error'] = test_df['predicted'] - test_df['target']
        test_df['abs_error'] = abs(test_df['error'])

        logger.info(f"\nPrediction Analysis:")
        logger.info(f"  Average actual {self.prop_type}: {test_df['target'].mean():.2f}")
        logger.info(f"  Average predicted {self.prop_type}: {test_df['predicted'].mean():.2f}")
        logger.info(f"  Median absolute error: {test_df['abs_error'].median():.2f}")
        logger.info(f"  % within 3 points: {(test_df['abs_error'] <= 3).mean()*100:.1f}%")
        logger.info(f"  % within 5 points: {(test_df['abs_error'] <= 5).mean()*100:.1f}%")

        # How this would perform as over/under (simulated)
        # Assume lines are set at player's recent average
        test_df['simulated_line'] = test_df[f'{self.prop_type}_avg_last_10'].fillna(
            test_df[f'{self.prop_type}_season_avg']
        )
        test_df['predicted_over'] = test_df['predicted'] > test_df['simulated_line']
        test_df['actual_over'] = test_df['target'] > test_df['simulated_line']
        test_df['correct'] = test_df['predicted_over'] == test_df['actual_over']

        accuracy = test_df['correct'].mean()
        logger.info(f"\nSimulated Over/Under Performance:")
        logger.info(f"  (Using recent avg as simulated line)")
        logger.info(f"  Accuracy: {accuracy:.1%}")
        logger.info(f"  Would be profitable: {'YES' if accuracy > 0.524 else 'NO'}")

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info("\nTop 15 Most Important Features:")
        logger.info(feature_importance.head(15).to_string(index=False))

        # Save model
        if save_model:
            self._save_model(feature_cols)

        return self.model

    def _save_model(self, feature_cols: list):
        """Save trained model and feature list."""
        models_dir = os.path.join(PROJECT_ROOT, 'models')
        os.makedirs(models_dir, exist_ok=True)

        model_path = os.path.join(models_dir, f'{self.prop_type}_regression_model.pkl')
        features_path = os.path.join(models_dir, f'{self.prop_type}_regression_features.pkl')

        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)

        with open(features_path, 'wb') as f:
            pickle.dump(feature_cols, f)

        logger.info(f"\nRegression model saved to: {model_path}")
        logger.info(f"Features saved to: {features_path}")

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main training script."""
    import argparse

    parser = argparse.ArgumentParser(description='Train regression model (no odds needed)')
    parser.add_argument(
        '--prop-type',
        default='points',
        help='Type of prop to train on'
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=365,
        help='Number of days of historical data to use'
    )
    parser.add_argument(
        '--test-split',
        type=float,
        default=0.2,
        help='Fraction of data to use for testing'
    )

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("NBA STATS REGRESSION MODEL TRAINING")
    logger.info("="*60)
    logger.info(f"Prop Type: {args.prop_type}")
    logger.info(f"Training Period: Last {args.days_back} days")
    logger.info(f"Mode: Regression (predicts actual values, not over/under)")
    logger.info("")

    trainer = StatsPredictorTrainer(prop_type=args.prop_type)

    try:
        # Prepare data
        start_date = datetime.now().date() - timedelta(days=args.days_back)
        df = trainer.prepare_training_data(start_date=start_date)

        if len(df) < 100:
            logger.error(f"Not enough training data ({len(df)} samples). Need at least 100.")
            logger.error("Run: python scripts/backfill_historical.py --season 2024-25")
            return

        # Train model
        trainer.train(df, test_split=args.test_split)

        logger.info("\n" + "="*60)
        logger.info("[OK] Training complete!")
        logger.info("="*60)
        logger.info("\nNote: This model predicts actual values.")
        logger.info("Once you have prop lines, use train_model.py for better results.")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        trainer.close()


if __name__ == "__main__":
    main()
