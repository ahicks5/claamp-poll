"""
NBA Props routes - Player prop predictions dashboard
Available to all logged-in users (not group-specific)
"""
from flask import render_template, jsonify, request
from flask_login import login_required
from datetime import datetime, date
import json
import os
import sys

# Add nba-props directory to path for database access
NBA_PROPS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'nba-props')
sys.path.insert(0, NBA_PROPS_DIR)

from . import bp


@bp.route("/")
@login_required
def dashboard():
    """Main NBA Props dashboard - shows today's predictions."""
    return render_template("nba_props_dashboard.html")


@bp.route("/api/predictions")
@login_required
def api_predictions():
    """
    API endpoint to get today's predictions.

    Query parameters:
        - prop_type: Filter by prop type (points, rebounds, assists)
        - min_edge: Minimum edge to show (default: 1.5)
        - play_only: Only show OVER/UNDER (exclude NO PLAY) (default: true)
    """
    try:
        # Try to read from JSON export first (fastest)
        export_path = os.path.join(NBA_PROPS_DIR, 'exports', 'plays.json')

        if os.path.exists(export_path):
            with open(export_path, 'r') as f:
                data = json.load(f)

            # Apply filters from query params
            prop_type = request.args.get('prop_type')
            min_edge = float(request.args.get('min_edge', 0))
            play_only = request.args.get('play_only', 'true').lower() == 'true'

            plays = data.get('plays', [])

            # Filter by prop type
            if prop_type:
                plays = [p for p in plays if p['stat'] == prop_type]

            # Filter by minimum edge
            if min_edge > 0:
                plays = [p for p in plays if abs(p['edge']) >= min_edge]

            # Filter to only plays (not NO PLAY)
            if play_only:
                plays = [p for p in plays if p['play'] in ['OVER', 'UNDER']]

            return jsonify({
                'success': True,
                'updated': data.get('updated'),
                'count': len(plays),
                'plays': plays
            })

        # If JSON doesn't exist, try database
        try:
            from database import get_session, Prediction, Player, Game, Team
            from sqlalchemy import and_

            session = get_session()

            # Get today's predictions
            today = date.today()
            query = session.query(Prediction).join(Player).join(Game)
            query = query.filter(Game.game_date == today)

            # Apply filters
            prop_type = request.args.get('prop_type')
            if prop_type:
                query = query.filter(Prediction.prop_type == prop_type)

            predictions = query.all()

            # Format for response
            plays = []
            for pred in predictions:
                edge = pred.predicted_value - pred.line_value

                # Apply minimum edge filter
                min_edge = float(request.args.get('min_edge', 0))
                if abs(edge) < min_edge:
                    continue

                # Apply play_only filter
                play_only = request.args.get('play_only', 'true').lower() == 'true'
                if play_only and pred.recommendation not in ['OVER', 'UNDER']:
                    continue

                plays.append({
                    'player': pred.player.full_name,
                    'stat': pred.prop_type,
                    'line': float(pred.line_value),
                    'prediction': float(pred.predicted_value),
                    'play': pred.recommendation,
                    'edge': float(edge),
                    'game': f"{pred.game.away_team.abbreviation} @ {pred.game.home_team.abbreviation}",
                    'time': pred.game.game_time or 'TBD'
                })

            session.close()

            return jsonify({
                'success': True,
                'updated': datetime.now().isoformat(),
                'count': len(plays),
                'plays': plays
            })

        except Exception as db_error:
            return jsonify({
                'success': False,
                'error': 'No predictions available',
                'message': 'Run daily workflow to generate predictions: python nba-props/scripts/daily_workflow.py'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route("/api/stats")
@login_required
def api_stats():
    """Get statistics about the prediction model."""
    try:
        from database import get_session
        from database import Prediction, Result, PropLine, Player

        session = get_session()

        # Get counts
        total_predictions = session.query(Prediction).count()
        total_props = session.query(PropLine).count()
        total_players = session.query(Player).count()

        # Get results (if any)
        total_results = session.query(Result).count()
        correct_results = session.query(Result).filter(Result.is_correct == True).count()

        accuracy = (correct_results / total_results * 100) if total_results > 0 else None

        # Get today's prediction count
        today = date.today()
        from database import Game
        today_predictions = session.query(Prediction).join(Game).filter(
            Game.game_date == today
        ).count()

        session.close()

        return jsonify({
            'success': True,
            'stats': {
                'total_predictions': total_predictions,
                'today_predictions': today_predictions,
                'total_props_collected': total_props,
                'total_players': total_players,
                'total_results': total_results,
                'correct_results': correct_results,
                'accuracy': round(accuracy, 2) if accuracy else None
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
