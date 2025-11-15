#!/usr/bin/env python3
# scripts/train_model.py
"""Train ML model for NBA player props predictions."""
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

from database import get_session, Player, Game, PlayerGameStats, PropLine
from services.feature_calculator import FeatureCalculator

# ML libraries
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
import xgboost as xgb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PropModelTrainer:
    """Train and evaluate NBA prop prediction models."""

    def __init__(self, prop_type: str = 'points'):
        self.session = get_session()
        self.feature_calc = FeatureCalculator(self.session)
        self.prop_type = prop_type
        self.model = None

    def prepare_training_data(
        self,
        start_date: datetime.date = None,
        end_date: datetime.date = None,
        min_games: int = 10
    ) -> pd.DataFrame:
        """
        Prepare training data from historical games and props.

        Args:
            start_date: Start date for training data
            end_date: End date for training data
            min_games: Minimum number of games player must have

        Returns:
            DataFrame with features and labels
        """
        logger.info(f"Preparing training data for {self.prop_type}...")

        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now().date()

        # Get all games with prop lines in date range
        games_with_props = self.session.query(
            Game, PropLine, PlayerGameStats
        ).join(
            PropLine, Game.id == PropLine.game_id
        ).join(
            PlayerGameStats,
            (PlayerGameStats.game_id == Game.id) &
            (PlayerGameStats.player_id == PropLine.player_id)
        ).filter(
            Game.game_date >= start_date,
            Game.game_date <= end_date,
            Game.status == 'final',
            PropLine.prop_type == self.prop_type
        ).all()

        logger.info(f"Found {len(games_with_props)} games with props and stats")

        training_data = []

        for game, prop, stats in games_with_props:
            # Get actual stat value
            actual_value = self.feature_calc._get_stat_value(stats, self.prop_type)

            if actual_value is None:
                continue

            # Binary label: 1 if over, 0 if under
            label = 1 if actual_value > prop.line_value else 0

            # Calculate features
            features = self.feature_calc.calculate_player_features(
                player_id=stats.player_id,
                game_date=game.game_date,
                prop_type=self.prop_type,
                lookback_games=20
            )

            if not features:
                continue

            # Add prop line features
            line_features = self.feature_calc.calculate_prop_line_features(
                player_id=stats.player_id,
                game_id=game.id,
                prop_type=self.prop_type,
                current_line=prop.line_value
            )
            features.update(line_features)

            # Add streak features
            streak_features = self.feature_calc.calculate_streak_features(
                player_id=stats.player_id,
                game_date=game.game_date,
                prop_type=self.prop_type
            )
            features.update(streak_features)

            # Add metadata
            features['player_id'] = stats.player_id
            features['game_id'] = game.id
            features['game_date'] = game.game_date
            features['prop_line'] = prop.line_value
            features['actual_value'] = actual_value
            features['label'] = label

            training_data.append(features)

        df = pd.DataFrame(training_data)

        logger.info(f"Prepared {len(df)} training samples")
        logger.info(f"Label distribution: Over={df['label'].sum()}, Under={(~df['label'].astype(bool)).sum()}")

        return df

    def train(
        self,
        df: pd.DataFrame,
        test_split: float = 0.2,
        save_model: bool = True
    ):
        """
        Train XGBoost model.

        Args:
            df: Training dataframe
            test_split: Fraction of data to use for testing
            save_model: Whether to save the trained model
        """
        logger.info("Training model...")

        # Remove metadata columns
        feature_cols = [col for col in df.columns if col not in [
            'player_id', 'game_id', 'game_date', 'label', 'actual_value', 'prop_line'
        ]]

        # Handle missing values
        df_features = df[feature_cols].fillna(0)

        # Split data (time-based split - use older games for training)
        df_sorted = df.sort_values('game_date')
        split_idx = int(len(df_sorted) * (1 - test_split))

        train_df = df_sorted.iloc[:split_idx]
        test_df = df_sorted.iloc[split_idx:]

        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df['label']

        X_test = test_df[feature_cols].fillna(0)
        y_test = test_df['label']

        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Test set: {len(X_test)} samples")

        # Train XGBoost model
        self.model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # Evaluate
        train_preds = self.model.predict(X_train)
        test_preds = self.model.predict(X_test)

        train_proba = self.model.predict_proba(X_train)[:, 1]
        test_proba = self.model.predict_proba(X_test)[:, 1]

        logger.info("\n" + "="*60)
        logger.info("MODEL PERFORMANCE")
        logger.info("="*60)
        logger.info(f"\nTraining Accuracy: {accuracy_score(y_train, train_preds):.4f}")
        logger.info(f"Training AUC: {roc_auc_score(y_train, train_proba):.4f}")
        logger.info(f"\nTest Accuracy: {accuracy_score(y_test, test_preds):.4f}")
        logger.info(f"Test AUC: {roc_auc_score(y_test, test_proba):.4f}")

        logger.info("\nTest Set Classification Report:")
        logger.info("\n" + classification_report(y_test, test_preds, target_names=['Under', 'Over']))

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info("\nTop 20 Most Important Features:")
        logger.info(feature_importance.head(20).to_string(index=False))

        # Analyze performance by edge size
        self._analyze_performance_by_edge(test_df, test_proba, feature_cols)

        # Save model
        if save_model:
            self._save_model(feature_cols)

        return self.model

    def _analyze_performance_by_edge(
        self,
        test_df: pd.DataFrame,
        predictions_proba: np.ndarray,
        feature_cols: List[str]
    ):
        """Analyze model performance based on prediction confidence."""
        logger.info("\n" + "="*60)
        logger.info("PERFORMANCE BY CONFIDENCE LEVEL")
        logger.info("="*60)

        test_df = test_df.copy()
        test_df['pred_proba'] = predictions_proba
        test_df['pred_label'] = (predictions_proba > 0.5).astype(int)
        test_df['correct'] = (test_df['pred_label'] == test_df['label']).astype(int)

        # Define confidence buckets
        confidence_buckets = [
            (0.5, 0.55, "Low Confidence"),
            (0.55, 0.6, "Medium-Low Confidence"),
            (0.6, 0.65, "Medium Confidence"),
            (0.65, 0.7, "Medium-High Confidence"),
            (0.7, 1.0, "High Confidence")
        ]

        for min_conf, max_conf, label in confidence_buckets:
            # For over predictions
            over_mask = (test_df['pred_proba'] >= min_conf) & (test_df['pred_proba'] < max_conf)
            # For under predictions
            under_mask = (test_df['pred_proba'] <= (1-min_conf)) & (test_df['pred_proba'] > (1-max_conf))

            mask = over_mask | under_mask
            subset = test_df[mask]

            if len(subset) > 0:
                accuracy = subset['correct'].mean()
                logger.info(f"\n{label} ({min_conf:.2f}-{max_conf:.2f}):")
                logger.info(f"  Samples: {len(subset)}")
                logger.info(f"  Accuracy: {accuracy:.4f}")
                logger.info(f"  ROI (betting $100 per pick): ${(accuracy - 0.5238) * len(subset) * 100:.2f}")

    def _save_model(self, feature_cols: List[str]):
        """Save trained model and feature list."""
        models_dir = os.path.join(PROJECT_ROOT, 'models')
        os.makedirs(models_dir, exist_ok=True)

        model_path = os.path.join(models_dir, f'{self.prop_type}_model.pkl')
        features_path = os.path.join(models_dir, f'{self.prop_type}_features.pkl')

        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)

        with open(features_path, 'wb') as f:
            pickle.dump(feature_cols, f)

        logger.info(f"\nModel saved to: {model_path}")
        logger.info(f"Features saved to: {features_path}")

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main training script."""
    import argparse

    parser = argparse.ArgumentParser(description='Train NBA props prediction model')
    parser.add_argument(
        '--prop-type',
        default='points',
        help='Type of prop to train on (points, rebounds, assists, etc.)'
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
    logger.info("NBA PROPS MODEL TRAINING")
    logger.info("="*60)
    logger.info(f"Prop Type: {args.prop_type}")
    logger.info(f"Training Period: Last {args.days_back} days")
    logger.info("")

    trainer = PropModelTrainer(prop_type=args.prop_type)

    try:
        # Prepare data
        start_date = datetime.now().date() - timedelta(days=args.days_back)
        df = trainer.prepare_training_data(start_date=start_date)

        if len(df) < 100:
            logger.error(f"Not enough training data ({len(df)} samples). Need at least 100.")
            return

        # Train model
        trainer.train(df, test_split=args.test_split)

        logger.info("\n" + "="*60)
        logger.info("[OK] Training complete!")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        trainer.close()


if __name__ == "__main__":
    main()
