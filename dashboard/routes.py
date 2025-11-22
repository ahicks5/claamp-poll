"""
TakeFreePoints.com - Dashboard Routes
Main betting dashboard with today's plays, performance tracking, and bet journal
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from sqlalchemy import func, desc

from db import SessionLocal
from models import Strategy, BetJournal, DailyPerformance, BankrollHistory
from services.strategy_service import StrategyService
from nba_props_models import get_todays_predictions

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@bp.route('/')
@login_required
def index():
    """Main dashboard - today's action"""
    db = SessionLocal()

    try:
        # Get user's active strategy
        strategy = db.query(Strategy).filter(
            Strategy.user_id == current_user.id,
            Strategy.is_active == True
        ).first()

        if not strategy:
            flash("No active strategy found. Please create one first.", "warning")
            return redirect(url_for('dashboard.strategies'))

        # Get current bankroll
        service = StrategyService(db)
        current_bankroll = service.get_current_bankroll(current_user.id, strategy.id)

        # Get today's bets
        today = date.today()
        todays_bets = (
            db.query(BetJournal)
            .filter(
                BetJournal.user_id == current_user.id,
                BetJournal.game_date == today
            )
            .all()
        )

        # Calculate today's stats
        pending_bets = [b for b in todays_bets if b.status == 'pending']
        won_bets = [b for b in todays_bets if b.status == 'won']
        lost_bets = [b for b in todays_bets if b.status == 'lost']

        total_staked_today = sum(b.stake for b in todays_bets)
        total_pnl_today = sum(b.profit_loss for b in todays_bets if b.profit_loss is not None)

        # Get available plays (predictions not yet bet on)
        all_predictions = get_todays_predictions()
        bet_prediction_ids = {b.prediction_id for b in todays_bets if b.prediction_id}
        available_plays = [p for p in all_predictions if p['id'] not in bet_prediction_ids]

        # Filter by strategy criteria
        from services.strategy_service import StrategyService
        service = StrategyService(db)
        recommended_plays = service.filter_predictions_by_strategy(available_plays, strategy)

        # Get recent performance (last 7 days)
        seven_days_ago = today - timedelta(days=7)
        recent_performance = (
            db.query(DailyPerformance)
            .filter(
                DailyPerformance.user_id == current_user.id,
                DailyPerformance.date >= seven_days_ago
            )
            .order_by(desc(DailyPerformance.date))
            .all()
        )

        # Calculate overall stats
        total_bets = db.query(func.count(BetJournal.id)).filter(
            BetJournal.user_id == current_user.id,
            BetJournal.status.in_(['won', 'lost'])
        ).scalar()

        total_won = db.query(func.count(BetJournal.id)).filter(
            BetJournal.user_id == current_user.id,
            BetJournal.status == 'won'
        ).scalar()

        win_rate = (total_won / total_bets * 100) if total_bets > 0 else 0

        total_profit = db.query(func.sum(BetJournal.profit_loss)).filter(
            BetJournal.user_id == current_user.id
        ).scalar() or 0

        return render_template(
            'dashboard/index.html',
            strategy=strategy,
            current_bankroll=current_bankroll,
            todays_bets=todays_bets,
            pending_count=len(pending_bets),
            won_count=len(won_bets),
            lost_count=len(lost_bets),
            total_staked_today=total_staked_today,
            total_pnl_today=total_pnl_today,
            recommended_plays=recommended_plays[:10],  # Top 10 plays
            recent_performance=recent_performance,
            win_rate=win_rate,
            total_profit=total_profit,
            total_bets=total_bets
        )

    finally:
        db.close()


@bp.route('/generate-bets', methods=['POST'])
@login_required
def generate_bets():
    """Auto-generate bet journal entries from today's predictions"""
    db = SessionLocal()

    try:
        strategy = db.query(Strategy).filter(
            Strategy.user_id == current_user.id,
            Strategy.is_active == True
        ).first()

        if not strategy:
            flash("No active strategy found.", "error")
            return redirect(url_for('dashboard.index'))

        service = StrategyService(db)
        result = service.apply_strategy_to_todays_predictions(current_user.id, strategy.id)

        if 'error' in result:
            flash(result['error'], "error")
        else:
            flash(
                f"✅ Created {result['bets_created']} bets with ${result['total_stake']:.2f} staked.",
                "success"
            )

        return redirect(url_for('dashboard.index'))

    finally:
        db.close()


@bp.route('/bet-journal')
@login_required
def bet_journal():
    """View all bets with filtering"""
    db = SessionLocal()

    try:
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        days_filter = int(request.args.get('days', 30))

        # Build query
        query = db.query(BetJournal).filter(BetJournal.user_id == current_user.id)

        if status_filter != 'all':
            query = query.filter(BetJournal.status == status_filter)

        if days_filter > 0:
            cutoff_date = date.today() - timedelta(days=days_filter)
            query = query.filter(BetJournal.game_date >= cutoff_date)

        bets = query.order_by(desc(BetJournal.game_date), desc(BetJournal.placed_at)).all()

        # Calculate summary stats
        total_staked = sum(b.stake for b in bets)
        total_pnl = sum(b.profit_loss for b in bets if b.profit_loss is not None)
        won = len([b for b in bets if b.status == 'won'])
        lost = len([b for b in bets if b.status == 'lost'])
        win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else 0
        roi = (total_pnl / total_staked * 100) if total_staked > 0 else 0

        return render_template(
            'dashboard/bet_journal.html',
            bets=bets,
            status_filter=status_filter,
            days_filter=days_filter,
            total_staked=total_staked,
            total_pnl=total_pnl,
            win_rate=win_rate,
            roi=roi,
            won_count=won,
            lost_count=lost
        )

    finally:
        db.close()


@bp.route('/performance')
@login_required
def performance():
    """Performance analytics with charts"""
    db = SessionLocal()

    try:
        # Get daily performance data for charts
        daily_perf = (
            db.query(DailyPerformance)
            .filter(DailyPerformance.user_id == current_user.id)
            .order_by(DailyPerformance.date)
            .all()
        )

        # Get bankroll history
        bankroll_history = (
            db.query(BankrollHistory)
            .filter(BankrollHistory.user_id == current_user.id)
            .order_by(BankrollHistory.timestamp)
            .all()
        )

        # Calculate cumulative P&L
        cumulative_pnl = []
        running_total = 0
        for perf in daily_perf:
            running_total += perf.net_profit_loss
            cumulative_pnl.append({
                'date': perf.date.isoformat(),
                'pnl': running_total
            })

        # Win rate by prop type
        prop_type_stats = (
            db.query(
                BetJournal.prop_type,
                func.count(BetJournal.id).label('total'),
                func.sum(func.case((BetJournal.status == 'won', 1), else_=0)).label('won')
            )
            .filter(
                BetJournal.user_id == current_user.id,
                BetJournal.status.in_(['won', 'lost'])
            )
            .group_by(BetJournal.prop_type)
            .all()
        )

        prop_stats = [
            {
                'prop_type': stat.prop_type,
                'total': stat.total,
                'won': stat.won,
                'win_rate': (stat.won / stat.total * 100) if stat.total > 0 else 0
            }
            for stat in prop_type_stats
        ]

        return render_template(
            'dashboard/performance.html',
            daily_perf=daily_perf,
            bankroll_history=bankroll_history,
            cumulative_pnl=cumulative_pnl,
            prop_stats=prop_stats
        )

    finally:
        db.close()


@bp.route('/strategies')
@login_required
def strategies():
    """Manage betting strategies"""
    db = SessionLocal()

    try:
        user_strategies = db.query(Strategy).filter(
            Strategy.user_id == current_user.id
        ).all()

        return render_template('dashboard/strategies.html', strategies=user_strategies)

    finally:
        db.close()


@bp.route('/api/todays-plays')
@login_required
def api_todays_plays():
    """API endpoint for today's recommended plays"""
    db = SessionLocal()

    try:
        strategy = db.query(Strategy).filter(
            Strategy.user_id == current_user.id,
            Strategy.is_active == True
        ).first()

        if not strategy:
            return jsonify({'error': 'No active strategy'}), 404

        # Get predictions and filter
        predictions = get_todays_predictions()
        service = StrategyService(db)
        recommended = service.filter_predictions_by_strategy(predictions, strategy)

        return jsonify({
            'plays': recommended[:20],  # Top 20
            'count': len(recommended)
        })

    finally:
        db.close()
