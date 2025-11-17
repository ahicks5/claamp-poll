#!/usr/bin/env python3
# scripts/daily_workflow.py
"""
ONE-COMMAND DAILY WORKFLOW
Run this once per day to get fresh predictions.

This script:
1. Updates player stats for recently completed games
2. Collects today's prop lines from The Odds API
3. Generates predictions using your trained model (with contrarian logic)
4. Exports predictions to JSON for website display
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

from database import get_session, Game, PropLine
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
            # Step 1: Update completed games with player stats
            print("[1/4] Updating completed games with player stats...")
            stats_updated = self._update_completed_games()
            print(f"      Updated {stats_updated} game stats")
            print("")

            # Step 2: Collect today's prop lines
            print("[2/4] Collecting today's prop lines...")
            props_collected = self._collect_todays_props()
            print(f"      Collected {props_collected} prop lines")
            print("")

            # Step 3: Generate predictions
            print("[3/4] Generating predictions...")
            predictions = self._generate_predictions(save_to_db=save_to_db)
            print(f"      Generated {len(predictions)} predictions")
            print("")

            # Step 4: Export for website
            if export_json:
                print("[4/4] Exporting predictions for website...")
                export_path = self._export_predictions(predictions)
                print(f"      Exported to: {export_path}")
                print("")

            # Summary
            print("=" * 60)
            print("DAILY WORKFLOW COMPLETE!")
            print("=" * 60)
            print(f"Player stats updated: {stats_updated}")
            print(f"Prop lines collected: {props_collected}")
            print(f"Predictions generated: {len(predictions)}")
            print(f"API requests used: ~{self.odds_client.requests_used}")
            print("")

            # Show top predictions
            if predictions:
                print("TOP PREDICTIONS (Highest Edge):")
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
            print("  - Track results: python scripts/track_results.py")
            print("  - View predictions: python scripts/query_data.py predictions")
            print("  - Train model (weekly): python scripts/train_model_no_odds.py")
            print("")

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _update_completed_games(self):
        """Update player stats for completed games."""
        from scripts.collect_daily_data import DailyDataCollector

        collector = DailyDataCollector()

        # Update completed games from the last 2 days
        collector.update_completed_games()

        # Count how many stats we have
        from database import PlayerGameStats
        from datetime import timedelta

        recent_date = datetime.now().date() - timedelta(days=2)
        stats_count = self.session.query(PlayerGameStats).join(Game).filter(
            Game.game_date >= recent_date,
            Game.status == 'final'
        ).count()

        return stats_count

    def _collect_todays_props(self):
        """Collect today's prop lines from The Odds API."""
        from scripts.collect_daily_data import DailyDataCollector

        collector = DailyDataCollector()

        # Collect for today only
        collector.run(days_ahead=1)

        # Count props from database
        today = datetime.now().date()
        props_count = self.session.query(PropLine).join(Game).filter(
            Game.game_date == today
        ).count()

        return props_count

    def _generate_predictions(self, save_to_db=True):
        """Generate predictions using the regression model."""
        from scripts.generate_predictions_regression import RegressionPredictionGenerator

        # Check if model exists
        model_path = os.path.join(PROJECT_ROOT, 'models', 'points_regression_model.pkl')
        if not os.path.exists(model_path):
            logger.warning("Model not found! Train a model first:")
            logger.warning("  python scripts/train_model_no_odds.py --prop-type points")
            return []

        try:
            generator = RegressionPredictionGenerator('points', min_edge=1.5)

            # Generate predictions DataFrame
            predictions_df = generator.generate_predictions_for_today()

            # Convert to list of dicts for compatibility with export
            predictions = []
            if not predictions_df.empty:
                for _, row in predictions_df.iterrows():
                    # Get game info
                    game = self.session.query(Game).get(row['game_id'])
                    if game:
                        game_info = f"{game.away_team.abbreviation} @ {game.home_team.abbreviation}"
                        # Convert game_time to string if it's a datetime/time object
                        if game.game_time:
                            game_time = str(game.game_time)
                        else:
                            game_time = 'TBD'
                    else:
                        game_info = 'TBD'
                        game_time = 'TBD'

                    predictions.append({
                        'player_name': row['player_name'],
                        'prop_type': row['prop_type'],
                        'line': float(row['line']),
                        'prediction': float(row['predicted_value']),
                        'edge': float(row['edge']),
                        'recommendation': row['recommendation'],
                        'game_info': game_info,
                        'game_time': game_time
                    })

            return predictions

        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return []

    def _export_predictions(self, predictions):
        """Export predictions to JSON file for website consumption."""
        # Deduplicate predictions - keep only one per player/prop_type with highest absolute edge
        unique_predictions = {}
        for pred in predictions:
            key = (pred['player_name'], pred['prop_type'])
            if key not in unique_predictions or abs(pred['edge']) > abs(unique_predictions[key]['edge']):
                unique_predictions[key] = pred

        # Convert back to list
        deduped_predictions = list(unique_predictions.values())

        # Sort by absolute edge (highest first)
        deduped_predictions.sort(key=lambda x: abs(x['edge']), reverse=True)

        export_data = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_predictions': len(deduped_predictions),
            'predictions': deduped_predictions
        }

        # Export to JSON file
        export_path = os.path.join(self.export_dir, 'predictions.json')
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        # Also export a simplified version for quick display
        simplified = {
            'updated': datetime.now(timezone.utc).isoformat(),
            'count': 0,  # Will be set after filtering
            'plays': []
        }

        # Filter to only plays (OVER/UNDER) and convert format
        plays = [
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
            for pred in deduped_predictions
            if pred['recommendation'] in ['OVER', 'UNDER']  # Only show plays, not NO PLAY
        ]

        simplified['plays'] = plays
        simplified['count'] = len(plays)

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
