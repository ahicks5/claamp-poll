#!/usr/bin/env python3
# api/predictions_api.py
"""
Simple API endpoint to serve NBA props predictions to the website.

Run this alongside your main web server:
    python nba-props/api/predictions_api.py

Then your web server can fetch predictions from:
    http://localhost:5001/api/predictions
"""
import sys
import os
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Prediction, Player, Game, PropLine, Team

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    """
    Get today's predictions.

    Query parameters:
        - prop_type: Filter by prop type (points, rebounds, assists)
        - min_edge: Minimum edge to show (default: 0)
        - recommendation: Filter by recommendation (OVER, UNDER)
        - limit: Max number of predictions to return
    """
    try:
        session = get_session()

        # Get query parameters
        prop_type = request.args.get('prop_type')
        min_edge = float(request.args.get('min_edge', 0))
        recommendation = request.args.get('recommendation')
        limit = int(request.args.get('limit', 100))

        # Build query for today's predictions
        today = datetime.now(timezone.utc).date()
        query = session.query(Prediction).join(Player).join(Game)

        # Filter by date (predictions for games happening today)
        query = query.filter(Game.game_date == today)

        # Apply filters
        if prop_type:
            query = query.filter(Prediction.prop_type == prop_type)

        if recommendation:
            query = query.filter(Prediction.recommendation == recommendation.upper())

        # Order by edge (absolute value)
        predictions = query.all()

        # Filter by min_edge and sort
        filtered_predictions = [
            p for p in predictions
            if abs(p.predicted_value - p.line_value) >= min_edge
        ]

        sorted_predictions = sorted(
            filtered_predictions,
            key=lambda x: abs(x.predicted_value - x.line_value),
            reverse=True
        )[:limit]

        # Format predictions for API response
        result = []
        for pred in sorted_predictions:
            edge = pred.predicted_value - pred.line_value

            result.append({
                'id': pred.id,
                'player': {
                    'id': pred.player.id,
                    'name': pred.player.full_name,
                    'team': pred.player.team.abbreviation if pred.player.team else None
                },
                'game': {
                    'id': pred.game.id,
                    'home_team': pred.game.home_team.name,
                    'away_team': pred.game.away_team.name,
                    'game_date': pred.game.game_date.isoformat(),
                    'game_time': pred.game.game_time
                },
                'prop_type': pred.prop_type,
                'line': float(pred.line_value),
                'prediction': float(pred.predicted_value),
                'edge': float(edge),
                'recommendation': pred.recommendation,
                'confidence': float(pred.confidence) if pred.confidence else None,
                'created_at': pred.created_at.isoformat()
            })

        session.close()

        return jsonify({
            'success': True,
            'count': len(result),
            'predictions': result,
            'generated_at': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/predictions/export', methods=['GET'])
def get_predictions_export():
    """
    Get predictions from the exported JSON file.
    This is faster than querying the database.
    """
    try:
        export_path = os.path.join(PROJECT_ROOT, 'exports', 'plays.json')

        if not os.path.exists(export_path):
            return jsonify({
                'success': False,
                'error': 'No predictions available. Run daily workflow first.'
            }), 404

        with open(export_path, 'r') as f:
            data = json.load(f)

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/predictions/stats', methods=['GET'])
def get_prediction_stats():
    """Get statistics about predictions (accuracy, ROI, etc.)."""
    try:
        session = get_session()

        # Get predictions from last 30 days with results
        from database import Result

        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        results = session.query(Result).filter(
            Result.created_at >= thirty_days_ago
        ).all()

        if not results:
            return jsonify({
                'success': True,
                'message': 'No results available yet',
                'stats': None
            })

        # Calculate stats
        total = len(results)
        correct = sum(1 for r in results if r.is_correct)
        accuracy = (correct / total * 100) if total > 0 else 0

        # Calculate by prop type
        by_prop_type = {}
        for result in results:
            prop_type = result.prop_type
            if prop_type not in by_prop_type:
                by_prop_type[prop_type] = {'total': 0, 'correct': 0}

            by_prop_type[prop_type]['total'] += 1
            if result.is_correct:
                by_prop_type[prop_type]['correct'] += 1

        # Calculate accuracy per prop type
        for prop_type, stats in by_prop_type.items():
            stats['accuracy'] = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0

        session.close()

        return jsonify({
            'success': True,
            'stats': {
                'total_predictions': total,
                'correct': correct,
                'accuracy': round(accuracy, 2),
                'by_prop_type': by_prop_type,
                'period': '30_days'
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/players', methods=['GET'])
def get_players():
    """Get list of players with recent predictions."""
    try:
        session = get_session()

        # Get players with predictions in last 7 days
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        players_with_preds = session.query(Player).join(Prediction).filter(
            Prediction.created_at >= seven_days_ago
        ).distinct().all()

        result = [
            {
                'id': player.id,
                'name': player.full_name,
                'team': player.team.abbreviation if player.team else None
            }
            for player in players_with_preds
        ]

        session.close()

        return jsonify({
            'success': True,
            'count': len(result),
            'players': result
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("NBA PROPS PREDICTION API")
    print("=" * 60)
    print("")
    print("API Endpoints:")
    print("  GET /api/health              - Health check")
    print("  GET /api/predictions         - Get today's predictions")
    print("  GET /api/predictions/export  - Get predictions from JSON export (fastest)")
    print("  GET /api/predictions/stats   - Get prediction accuracy stats")
    print("  GET /api/players             - Get players with recent predictions")
    print("")
    print("Examples:")
    print("  http://localhost:5001/api/predictions")
    print("  http://localhost:5001/api/predictions?prop_type=points&min_edge=2")
    print("  http://localhost:5001/api/predictions/export")
    print("")
    print("Starting server on http://localhost:5001")
    print("=" * 60)
    print("")

    app.run(host='0.0.0.0', port=5001, debug=True)
