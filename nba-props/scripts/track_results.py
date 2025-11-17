#!/usr/bin/env python3
# scripts/track_results.py
"""
Automatically track prediction results after games complete.

This script:
1. Finds completed games with predictions
2. Checks actual player stats against predictions
3. Records results (win/loss) in the Result table
4. Calculates accuracy and profit/loss

Run this daily after games finish (e.g., 3 AM)
"""
import sys
import os
import logging
from datetime import datetime, timedelta, timezone

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Prediction, Result, Player, Game, PlayerGameStats
from sqlalchemy import Integer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ResultsTracker:
    """Track prediction results and calculate accuracy."""

    def __init__(self):
        self.session = get_session()
        self.results_recorded = 0
        self.wins = 0
        self.losses = 0

    def track_recent_results(self, days_back: int = 7):
        """
        Track results for predictions from the last N days.

        Args:
            days_back: Number of days to look back
        """
        logger.info("=" * 60)
        logger.info(f"TRACKING PREDICTION RESULTS (last {days_back} days)")
        logger.info("=" * 60)

        # Get date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days_back)

        # Find predictions that don't have results yet
        predictions = self.session.query(Prediction).join(Game).outerjoin(Result).filter(
            Game.game_date >= start_date,
            Game.game_date <= end_date,
            Game.status == 'final',  # Only completed games
            Result.id == None  # No result recorded yet
        ).all()

        logger.info(f"Found {len(predictions)} predictions without results\n")

        for prediction in predictions:
            try:
                self._record_result(prediction)
            except Exception as e:
                logger.error(f"Error recording result for prediction {prediction.id}: {e}")
                continue

        self.session.commit()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("TRACKING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Results recorded: {self.results_recorded}")
        logger.info(f"Wins: {self.wins} ({self.wins/self.results_recorded*100:.1f}%)" if self.results_recorded > 0 else "Wins: 0")
        logger.info(f"Losses: {self.losses} ({self.losses/self.results_recorded*100:.1f}%)" if self.results_recorded > 0 else "Losses: 0")
        logger.info("")

        # Show overall accuracy
        self._show_overall_accuracy()

        # Return count of results recorded
        return self.results_recorded

    def _record_result(self, prediction: Prediction):
        """Record the result of a single prediction."""
        # Get the player's actual stats for this game
        stats = self.session.query(PlayerGameStats).filter(
            PlayerGameStats.player_id == prediction.player_id,
            PlayerGameStats.game_id == prediction.game_id
        ).first()

        if not stats:
            logger.warning(f"No stats found for prediction {prediction.id} (game not updated yet?)")
            return

        # Get actual value based on prop type
        actual_value = self._get_actual_value(stats, prediction.prop_type)

        if actual_value is None:
            logger.warning(f"Could not get actual value for {prediction.prop_type}")
            return

        # Determine if prediction was correct
        was_correct = self._check_if_correct(
            prediction.recommended_pick,
            prediction.line_value,
            actual_value
        )

        # Calculate profit/loss (assuming -110 American odds, 1 unit bet)
        if was_correct:
            profit_loss = 0.91  # Win $0.91 per $1 bet at -110 odds
            self.wins += 1
        else:
            profit_loss = -1.0  # Lose $1
            self.losses += 1

        # Create result record
        result = Result(
            prediction_id=prediction.id,
            actual_value=actual_value,
            was_correct=was_correct,
            bet_amount=1.0,
            profit_loss=profit_loss
        )

        self.session.add(result)
        self.results_recorded += 1

        # Log
        player = self.session.query(Player).get(prediction.player_id)
        game = self.session.query(Game).get(prediction.game_id)

        status = "✓ WIN" if was_correct else "✗ LOSS"
        logger.info(f"{status} | {player.full_name:25s} {prediction.prop_type:8s} "
                   f"Line: {prediction.line_value:5.1f} | Actual: {actual_value:5.1f} | "
                   f"Pick: {prediction.recommended_pick:6s} | {game.game_date}")

    def _check_if_correct(self, pick: str, line: float, actual: float) -> bool:
        """Check if a prediction was correct."""
        if pick == 'OVER':
            return actual > line
        elif pick == 'UNDER':
            return actual < line
        else:
            # NO PLAY - don't count
            return None

    def _get_actual_value(self, stats: PlayerGameStats, prop_type: str) -> float:
        """Get the actual stat value from player stats."""
        if prop_type == 'points':
            return stats.points
        elif prop_type == 'rebounds':
            return stats.rebounds
        elif prop_type == 'assists':
            return stats.assists
        elif prop_type == 'steals':
            return stats.steals
        elif prop_type == 'blocks':
            return stats.blocks
        elif prop_type == 'threes':
            return stats.three_pointers_made
        elif prop_type == 'pts_reb_ast':
            return (stats.points or 0) + (stats.rebounds or 0) + (stats.assists or 0)
        elif prop_type == 'pts_reb':
            return (stats.points or 0) + (stats.rebounds or 0)
        elif prop_type == 'pts_ast':
            return (stats.points or 0) + (stats.assists or 0)
        elif prop_type == 'reb_ast':
            return (stats.rebounds or 0) + (stats.assists or 0)
        else:
            return None

    def _show_overall_accuracy(self):
        """Show overall prediction accuracy."""
        # Get all results
        all_results = self.session.query(Result).filter(
            Result.was_correct != None
        ).all()

        if not all_results:
            logger.info("No results tracked yet")
            return

        total = len(all_results)
        wins = sum(1 for r in all_results if r.was_correct)
        losses = total - wins

        accuracy = (wins / total * 100) if total > 0 else 0
        total_profit = sum(r.profit_loss for r in all_results if r.profit_loss is not None)

        logger.info("\n" + "=" * 60)
        logger.info("OVERALL ACCURACY")
        logger.info("=" * 60)
        logger.info(f"Total predictions tracked: {total}")
        logger.info(f"Wins: {wins} ({accuracy:.1f}%)")
        logger.info(f"Losses: {losses} ({100-accuracy:.1f}%)")
        logger.info(f"Total profit/loss: ${total_profit:+.2f} units")
        logger.info(f"ROI: {(total_profit/total*100):+.2f}%" if total > 0 else "ROI: N/A")
        logger.info("")

        # Break down by prop type
        from sqlalchemy import func
        by_prop_type = self.session.query(
            Prediction.prop_type,
            func.count(Result.id).label('count'),
            func.sum(Result.was_correct.cast(Integer)).label('wins')
        ).join(Result).group_by(Prediction.prop_type).all()

        if by_prop_type:
            logger.info("Accuracy by prop type:")
            for prop_type, count, wins in by_prop_type:
                acc = (wins / count * 100) if count > 0 else 0
                logger.info(f"  {prop_type:12s}: {wins}/{count} ({acc:.1f}%)")

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Track prediction results after games complete'
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=7,
        help='Number of days to look back (default: 7)'
    )

    args = parser.parse_args()

    tracker = ResultsTracker()

    try:
        tracker.track_recent_results(days_back=args.days_back)
        logger.info("\n[OK] Results tracking complete!")
    except KeyboardInterrupt:
        logger.info("\n\nTracking interrupted by user")
    except Exception as e:
        logger.error(f"\nTracking failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        tracker.close()


if __name__ == "__main__":
    main()
