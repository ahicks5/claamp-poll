#!/usr/bin/env python3
# scripts/daily_workflow.py
"""
ONE-COMMAND DAILY WORKFLOW
Run this once per day to get fresh predictions.

This script:
1. Collects today's prop lines from The Odds API
2. Generates predictions using your trained model
3. Exports predictions to JSON for website display
4. Stores predictions in database
"""
import sys
import os
import logging
from datetime import datetime, timezone
import json

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session
from services.odds_api_client import OddsAPIClient
from services.nba_api_client import NBAAPIClient

# Configure logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'daily_workflow.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyWorkflow:
    """Orchestrates the daily workflow."""

    def __init__(self):
        self.session = get_session()
        self.odds_client = OddsAPIClient()
        self.nba_client = NBAAPIClient()
        self.export_dir = os.path.join(PROJECT_ROOT, 'exports')
        os.makedirs(self.export_dir, exist_ok=True)

    def run(self, save_to_db=True, export_json=True):
        """
        Run the complete daily workflow.

        Args:
            save_to_db: Whether to save predictions to database
            export_json: Whether to export predictions to JSON file
        """
        print("=" * 60)
        print("NBA PROPS - DAILY WORKFLOW")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("")

        try:
            # Step 1: Collect today's prop lines
            print("[1/3] Collecting today's prop lines...")
            props_collected = self._collect_todays_props()
            print(f"      Collected {props_collected} prop lines")
            print("")

            # Step 2: Generate predictions
            print("[2/3] Generating predictions...")
            predictions = self._generate_predictions(save_to_db=save_to_db)
            print(f"      Generated {len(predictions)} predictions")
            print("")

            # Step 3: Export for website
            if export_json:
                print("[3/3] Exporting predictions for website...")
                export_path = self._export_predictions(predictions)
                print(f"      Exported to: {export_path}")
                print("")

            # Summary
            print("=" * 60)
            print("DAILY WORKFLOW COMPLETE!")
            print("=" * 60)
            print(f"Prop lines collected: {props_collected}")
            print(f"Predictions generated: {len(predictions)}")
            print(f"API requests used: ~{self.odds_client.requests_used}")
            print("")

            # Show top predictions
            if predictions:
                print("TOP PREDICTIONS (Highest Confidence):")
                print("-" * 60)
                sorted_preds = sorted(
                    predictions,
                    key=lambda x: abs(x['edge']),
                    reverse=True
                )[:10]

                for pred in sorted_preds:
                    print(f"{pred['player_name']:25s} {pred['prop_type']:8s} "
                          f"Line: {pred['line']:5.1f}  Pred: {pred['prediction']:5.1f}  "
                          f"{pred['recommendation']:8s} (Edge: {pred['edge']:+.1f})")
                print("")

            print("Next steps:")
            print("  - Check exports/predictions.json for website data")
            print("  - View predictions: python scripts/query_data.py predictions")
            print("  - Train model (weekly): python scripts/train_model_no_odds.py")
            print("")

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _collect_todays_props(self):
        """Collect today's prop lines from The Odds API."""
        from scripts.collect_daily_data import DailyDataCollector

        collector = DailyDataCollector(
            self.odds_client,
            self.nba_client,
            self.session
        )

        # Collect for today only
        stats = collector.collect_daily_data(days_ahead=1)
        return stats.get('props_added', 0)

    def _generate_predictions(self, save_to_db=True):
        """Generate predictions using the regression model."""
        from scripts.generate_predictions_regression import PredictionGenerator

        # Check if model exists
        model_path = os.path.join(PROJECT_ROOT, 'models', 'points_regression_model.pkl')
        if not os.path.exists(model_path):
            logger.warning("Model not found! Train a model first:")
            logger.warning("  python scripts/train_model_no_odds.py --prop-type points")
            return []

        generator = PredictionGenerator('points')
        predictions = generator.generate_predictions(
            min_edge=1.5,  # Lower threshold to see more predictions
            save_to_db=save_to_db
        )

        return predictions

    def _export_predictions(self, predictions):
        """Export predictions to JSON file for website consumption."""
        export_data = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_predictions': len(predictions),
            'predictions': predictions
        }

        # Export to JSON file
        export_path = os.path.join(self.export_dir, 'predictions.json')
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        # Also export a simplified version for quick display
        simplified = {
            'updated': datetime.now(timezone.utc).isoformat(),
            'count': len(predictions),
            'plays': [
                {
                    'player': pred['player_name'],
                    'stat': pred['prop_type'],
                    'line': pred['line'],
                    'prediction': pred['prediction'],
                    'play': pred['recommendation'],
                    'edge': pred['edge'],
                    'game': pred.get('game_info', 'TBD'),
                    'time': pred.get('game_time', 'TBD')
                }
                for pred in predictions
                if pred['recommendation'] in ['OVER', 'UNDER']  # Only show plays, not NO PLAY
            ]
        }

        simplified_path = os.path.join(self.export_dir, 'plays.json')
        with open(simplified_path, 'w') as f:
            json.dump(simplified, f, indent=2)

        logger.info(f"Also exported simplified plays to: {simplified_path}")

        return export_path

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run daily NBA props workflow'
    )
    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Skip saving predictions to database'
    )
    parser.add_argument(
        '--no-export',
        action='store_true',
        help='Skip exporting predictions to JSON'
    )

    args = parser.parse_args()

    workflow = DailyWorkflow()

    try:
        workflow.run(
            save_to_db=not args.no_db,
            export_json=not args.no_export
        )
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
    except Exception as e:
        print(f"\n\nWorkflow failed: {e}")
        sys.exit(1)
    finally:
        workflow.close()


if __name__ == "__main__":
    main()
