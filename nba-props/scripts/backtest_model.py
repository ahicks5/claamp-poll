#!/usr/bin/env python3
# scripts/backtest_model.py
"""Backtest the ML model on historical data to measure profitability."""
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

from database import get_session, Game, PlayerGameStats, PropLine
from services.feature_calculator import FeatureCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelBacktester:
    """Backtest model performance on historical data."""

    def __init__(self, prop_type: str = 'points'):
        self.session = get_session()
        self.feature_calc = FeatureCalculator(self.session)
        self.prop_type = prop_type
        self.model = None
        self.feature_cols = None

        self._load_model()

    def _load_model(self):
        """Load trained model."""
        models_dir = os.path.join(PROJECT_ROOT, 'models')
        model_path = os.path.join(models_dir, f'{self.prop_type}_model.pkl')
        features_path = os.path.join(models_dir, f'{self.prop_type}_features.pkl')

        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        with open(features_path, 'rb') as f:
            self.feature_cols = pickle.load(f)

    def backtest(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        min_confidence: float = 0.60,
        unit_size: float = 100.0
    ) -> pd.DataFrame:
        """
        Run backtest on historical period.

        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            min_confidence: Minimum confidence to make a bet
            unit_size: Bet size in dollars

        Returns:
            DataFrame with all bets and results
        """
        logger.info(f"Running backtest from {start_date} to {end_date}")
        logger.info(f"Minimum confidence: {min_confidence:.0%}, Unit size: ${unit_size}")

        # Get all completed games with props in the period
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

        logger.info(f"Found {len(games_with_props)} props to backtest")

        bets = []

        for game, prop, stats in games_with_props:
            # Calculate features
            features = self.feature_calc.calculate_player_features(
                player_id=stats.player_id,
                game_date=game.game_date,
                prop_type=self.prop_type,
                lookback_games=20
            )

            if not features:
                continue

            # Add line features
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

            # Prepare for model
            feature_vector = [features.get(col, 0) for col in self.feature_cols]

            # Make prediction
            pred_proba = self.model.predict_proba([feature_vector])[0]
            over_prob = pred_proba[1]
            under_prob = pred_proba[0]

            confidence = max(over_prob, under_prob)

            # Only bet if above threshold
            if confidence < min_confidence:
                continue

            # Determine bet
            if over_prob > under_prob:
                bet_type = 'OVER'
                bet_prob = over_prob
            else:
                bet_type = 'UNDER'
                bet_prob = under_prob

            # Get actual result
            actual_value = self.feature_calc._get_stat_value(stats, self.prop_type)

            if actual_value is None:
                continue

            # Determine if won
            if bet_type == 'OVER':
                won = actual_value > prop.line_value
            else:
                won = actual_value < prop.line_value

            # Calculate profit/loss (assuming -110 odds)
            if won:
                profit = unit_size * (100/110)  # Win $100 on a $110 bet
            else:
                profit = -unit_size

            bets.append({
                'game_date': game.game_date,
                'player_id': stats.player_id,
                'bet_type': bet_type,
                'line': prop.line_value,
                'actual': actual_value,
                'confidence': confidence,
                'won': won,
                'profit': profit,
                'over_streak': streak_features.get('over_streak', 0),
                'under_streak': streak_features.get('under_streak', 0),
                'sharp_movement': line_features.get('is_sharp_movement', 0)
            })

        df = pd.DataFrame(bets)
        return df

    def analyze_results(self, results_df: pd.DataFrame, unit_size: float = 100.0):
        """Analyze and display backtest results."""
        if len(results_df) == 0:
            logger.info("No bets made in backtest period")
            return

        logger.info("\n" + "="*80)
        logger.info("BACKTEST RESULTS")
        logger.info("="*80)

        total_bets = len(results_df)
        wins = results_df['won'].sum()
        losses = total_bets - wins
        win_rate = wins / total_bets if total_bets > 0 else 0

        total_profit = results_df['profit'].sum()
        avg_profit = results_df['profit'].mean()

        # ROI calculation
        total_wagered = total_bets * unit_size
        roi = (total_profit / total_wagered) * 100 if total_wagered > 0 else 0

        logger.info(f"\nOverall Performance:")
        logger.info(f"  Total Bets: {total_bets}")
        logger.info(f"  Wins: {wins} ({win_rate:.1%})")
        logger.info(f"  Losses: {losses}")
        logger.info(f"  Total Profit: ${total_profit:.2f}")
        logger.info(f"  Average Profit/Bet: ${avg_profit:.2f}")
        logger.info(f"  ROI: {roi:.2%}")

        # Break-even analysis (need 52.38% to break even at -110 odds)
        logger.info(f"\n  Break-even win rate at -110 odds: 52.38%")
        if win_rate >= 0.5238:
            logger.info(f"  [OK] You are profitable! ({win_rate:.1%} > 52.38%)")
        else:
            logger.info(f"  [WARNING] Below break-even ({win_rate:.1%} < 52.38%)")

        # Performance by confidence level
        logger.info("\nPerformance by Confidence Level:")
        confidence_buckets = [
            (0.6, 0.65, "60-65%"),
            (0.65, 0.7, "65-70%"),
            (0.7, 0.75, "70-75%"),
            (0.75, 1.0, "75%+")
        ]

        for min_conf, max_conf, label in confidence_buckets:
            subset = results_df[
                (results_df['confidence'] >= min_conf) &
                (results_df['confidence'] < max_conf)
            ]

            if len(subset) > 0:
                subset_wins = subset['won'].sum()
                subset_win_rate = subset_wins / len(subset)
                subset_profit = subset['profit'].sum()
                subset_roi = (subset_profit / (len(subset) * unit_size)) * 100

                logger.info(f"  {label}: {len(subset)} bets, {subset_win_rate:.1%} win rate, "
                          f"${subset_profit:.2f} profit, {subset_roi:.1%} ROI")

        # Performance over time
        logger.info("\nMonthly Performance:")
        results_df['year_month'] = pd.to_datetime(results_df['game_date']).dt.to_period('M')
        monthly = results_df.groupby('year_month').agg({
            'won': ['sum', 'count'],
            'profit': 'sum'
        })

        for period, row in monthly.iterrows():
            month_bets = row[('won', 'count')]
            month_wins = row[('won', 'sum')]
            month_profit = row[('profit', 'sum')]
            month_win_rate = month_wins / month_bets if month_bets > 0 else 0
            month_roi = (month_profit / (month_bets * unit_size)) * 100

            logger.info(f"  {period}: {month_bets} bets, {month_win_rate:.1%} win rate, "
                       f"${month_profit:.2f} profit, {month_roi:.1%} ROI")

        # Streaks analysis
        logger.info("\nStreak Performance (when model catches streaks):")
        with_over_streak = results_df[results_df['over_streak'] >= 3]
        with_under_streak = results_df[results_df['under_streak'] >= 3]

        if len(with_over_streak) > 0:
            over_streak_win_rate = with_over_streak['won'].sum() / len(with_over_streak)
            logger.info(f"  Bets on players with 3+ over streak: {len(with_over_streak)} bets, "
                       f"{over_streak_win_rate:.1%} win rate")

        if len(with_under_streak) > 0:
            under_streak_win_rate = with_under_streak['won'].sum() / len(with_under_streak)
            logger.info(f"  Bets on players with 3+ under streak: {len(with_under_streak)} bets, "
                       f"{under_streak_win_rate:.1%} win rate")

        # Sharp movement analysis (Vegas traps)
        sharp_moves = results_df[results_df['sharp_movement'] == 1]
        if len(sharp_moves) > 0:
            sharp_win_rate = sharp_moves['won'].sum() / len(sharp_moves)
            sharp_profit = sharp_moves['profit'].sum()
            logger.info(f"\nSharp Line Movement Bets (Vegas Traps):")
            logger.info(f"  Total bets: {len(sharp_moves)}")
            logger.info(f"  Win rate: {sharp_win_rate:.1%}")
            logger.info(f"  Profit: ${sharp_profit:.2f}")
            if sharp_win_rate < 0.50:
                logger.info(f"  [!] Sharp movements are losing - model catching Vegas traps well!")

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main backtesting script."""
    import argparse

    parser = argparse.ArgumentParser(description='Backtest NBA props model')
    parser.add_argument(
        '--prop-type',
        default='points',
        help='Type of prop to backtest'
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=30,
        help='Number of days to backtest'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.60,
        help='Minimum confidence to bet'
    )
    parser.add_argument(
        '--unit-size',
        type=float,
        default=100.0,
        help='Bet size in dollars'
    )

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("NBA PROPS MODEL BACKTESTING")
    logger.info("="*60)

    backtester = ModelBacktester(prop_type=args.prop_type)

    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=args.days_back)

        # Run backtest
        results = backtester.backtest(
            start_date=start_date,
            end_date=end_date,
            min_confidence=args.min_confidence,
            unit_size=args.unit_size
        )

        # Analyze results
        backtester.analyze_results(results, unit_size=args.unit_size)

        logger.info("\n[OK] Backtesting complete!")

    except Exception as e:
        logger.error(f"Backtesting failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        backtester.close()


if __name__ == "__main__":
    main()
