"""
TakeFreePoints.com - Strategy Service
Automatically generate bet journal entries from NBA predictions based on strategy criteria
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba-props'))

from datetime import datetime, date, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# Main app models
from models import Strategy, BetJournal, BankrollHistory, User
from db import SessionLocal
from sqlalchemy import func

# NBA props predictions (from separate database via bridge)
from nba_props_models import get_todays_predictions

# Betting utilities
from utils.betting import (
    calculate_bet_size,
    calculate_to_win,
    estimate_win_probability_from_edge
)


class StrategyService:
    """Service for applying betting strategies to predictions"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_current_bankroll(self, user_id: int, strategy_id: int) -> float:
        """
        Get current bankroll from most recent bankroll snapshot

        Returns strategy's initial bankroll if no history exists
        """
        latest_snapshot = (
            self.db.query(BankrollHistory)
            .filter(
                BankrollHistory.user_id == user_id,
                BankrollHistory.strategy_id == strategy_id
            )
            .order_by(BankrollHistory.timestamp.desc())
            .first()
        )

        if latest_snapshot:
            return latest_snapshot.bankroll

        # No history? Use initial bankroll from strategy
        strategy = self.db.query(Strategy).get(strategy_id)
        return strategy.initial_bankroll if strategy else 100.0

    def filter_predictions_by_strategy(
        self,
        predictions: List[Dict],
        strategy: Strategy
    ) -> List[Dict]:
        """
        Filter predictions based on strategy criteria

        Args:
            predictions: List of prediction dicts from NBA props
            strategy: Strategy model with filtering criteria

        Returns:
            Filtered list of predictions that meet strategy criteria
        """
        filtered = []

        for pred in predictions:
            # Check minimum edge
            if pred.get('edge') and abs(pred['edge']) < strategy.min_edge:
                continue

            # Check minimum confidence (if strategy specifies it)
            if strategy.min_confidence:
                if not pred.get('confidence') or pred['confidence'] < strategy.min_confidence:
                    continue

            # Check prop type filter
            if strategy.prop_types:
                allowed_types = [pt.strip() for pt in strategy.prop_types.split(',')]
                if pred.get('prop_type') not in allowed_types:
                    continue

            # Must have a recommended pick
            if not pred.get('recommended_pick'):
                continue

            filtered.append(pred)

        return filtered

    def calculate_daily_exposure(
        self,
        user_id: int,
        strategy_id: int,
        game_date: date
    ) -> float:
        """Calculate total $ at risk for a given day"""
        total_staked = (
            self.db.query(func.sum(BetJournal.stake))
            .filter(
                BetJournal.user_id == user_id,
                BetJournal.strategy_id == strategy_id,
                BetJournal.game_date == game_date,
                BetJournal.status != 'cancelled'
            )
            .scalar()
        )
        return total_staked or 0.0

    def create_bet_from_prediction(
        self,
        prediction: Dict,
        strategy: Strategy,
        user_id: int,
        bankroll: float
    ) -> Optional[BetJournal]:
        """
        Create a BetJournal entry from a prediction

        Args:
            prediction: Prediction dict from NBA props
            strategy: Strategy to apply
            user_id: User ID
            bankroll: Current bankroll

        Returns:
            BetJournal entry or None if bet shouldn't be placed
        """
        # Extract prediction data
        predicted_value = prediction.get('predicted_value')
        line_value = prediction.get('line_value')
        recommended_pick = prediction.get('recommended_pick')
        prop_type = prediction.get('prop_type')
        edge = prediction.get('edge')
        confidence = prediction.get('confidence')
        odds = prediction.get('odds', -110)  # Default to -110 if not provided

        if not all([predicted_value, line_value, recommended_pick, prop_type]):
            return None

        # Estimate win probability from edge
        win_prob = estimate_win_probability_from_edge(
            predicted_value,
            line_value,
            recommended_pick
        )

        # Calculate bet size
        try:
            stake = calculate_bet_size(
                bankroll=bankroll,
                strategy_type=strategy.bet_sizing_method,
                win_probability=win_prob,
                american_odds=odds,
                kelly_fraction=strategy.kelly_fraction,
                flat_amount=strategy.flat_bet_amount,
                percentage=strategy.percentage_of_bankroll,
                max_bet=strategy.max_bet_amount
            )
        except Exception as e:
            print(f"Error calculating bet size: {e}")
            return None

        # Don't create bet if stake is too small (< $0.50)
        if stake < 0.50:
            return None

        # Calculate potential profit
        to_win = calculate_to_win(stake, odds)

        # Create bet journal entry
        bet = BetJournal(
            user_id=user_id,
            strategy_id=strategy.id,
            prediction_id=prediction.get('id'),  # Link to NBA predictions
            game_date=prediction.get('game_date', date.today()),
            sport=strategy.sport,
            player_name=prediction.get('player_name'),
            game_description=prediction.get('game_description'),
            prop_type=prop_type,
            line_value=line_value,
            pick=recommended_pick,
            predicted_value=predicted_value,
            edge=edge,
            confidence=confidence,
            odds=odds,
            stake=stake,
            to_win=to_win,
            status='pending',
            placed_at=datetime.now(timezone.utc)
        )

        return bet

    def apply_strategy_to_todays_predictions(
        self,
        user_id: int,
        strategy_id: int
    ) -> Dict:
        """
        Apply strategy to today's NBA predictions and create bet journal entries

        Args:
            user_id: User ID
            strategy_id: Strategy ID to apply

        Returns:
            Summary dict with counts and total stake
        """
        # Load strategy
        strategy = self.db.query(Strategy).get(strategy_id)
        if not strategy or not strategy.is_active:
            return {"error": "Strategy not found or inactive"}

        # Get current bankroll
        bankroll = self.get_current_bankroll(user_id, strategy_id)

        # Get today's predictions from NBA props database (via bridge module)
        predictions = get_todays_predictions()

        # Filter predictions by strategy criteria
        filtered_predictions = self.filter_predictions_by_strategy(predictions, strategy)

        # Check daily limits
        today_date = date.today()
        existing_bets_count = (
            self.db.query(BetJournal)
            .filter(
                BetJournal.user_id == user_id,
                BetJournal.strategy_id == strategy_id,
                BetJournal.game_date == today_date
            )
            .count()
        )

        if strategy.max_daily_bets and existing_bets_count >= strategy.max_daily_bets:
            return {
                "error": f"Daily bet limit reached ({strategy.max_daily_bets})",
                "predictions_found": len(predictions),
                "predictions_filtered": len(filtered_predictions),
                "bets_created": 0
            }

        # Check daily exposure
        current_exposure = self.calculate_daily_exposure(user_id, strategy_id, today_date)

        # Create bets
        bets_created = []
        total_stake = 0.0

        for pred in filtered_predictions:
            # Check if we've hit daily limits
            if strategy.max_daily_bets and len(bets_created) >= (strategy.max_daily_bets - existing_bets_count):
                break

            # Create bet
            bet = self.create_bet_from_prediction(pred, strategy, user_id, bankroll)
            if not bet:
                continue

            # Check daily exposure limit
            if strategy.max_daily_exposure:
                if current_exposure + total_stake + bet.stake > strategy.max_daily_exposure:
                    break

            # Add to database
            self.db.add(bet)
            bets_created.append(bet)
            total_stake += bet.stake

            # Update bankroll for next bet calculation (Kelly adjusts based on current bankroll)
            bankroll -= bet.stake

        # Commit all bets
        if bets_created:
            self.db.commit()

            # Create bankroll snapshot after placing bets
            new_bankroll = self.get_current_bankroll(user_id, strategy_id) - total_stake
            snapshot = BankrollHistory(
                user_id=user_id,
                strategy_id=strategy_id,
                bankroll=new_bankroll,
                event_type="bets_placed",
                note=f"Placed {len(bets_created)} bets, ${total_stake:.2f} staked"
            )
            self.db.add(snapshot)
            self.db.commit()

        return {
            "predictions_found": len(predictions),
            "predictions_filtered": len(filtered_predictions),
            "bets_created": len(bets_created),
            "total_stake": round(total_stake, 2),
            "bankroll_remaining": round(bankroll, 2)
        }


# CLI for testing
if __name__ == "__main__":
    print("🏀 TakeFreePoints Strategy Service Test")
    print("=" * 50)

    db = SessionLocal()

    try:
        # Get admin user and their strategy
        user = db.query(User).filter(User.username == "ahicks5").first()
        if not user:
            print("❌ Admin user not found. Run init_database.py first.")
            sys.exit(1)

        strategy = db.query(Strategy).filter(Strategy.user_id == user.id).first()
        if not strategy:
            print("❌ No strategy found. Run init_database.py first.")
            sys.exit(1)

        print(f"\nUser: {user.username}")
        print(f"Strategy: {strategy.name}")
        print(f"Min edge: {strategy.min_edge}")

        # Apply strategy
        service = StrategyService(db)
        result = service.apply_strategy_to_todays_predictions(user.id, strategy.id)

        print(f"\nResults:")
        print(f"  Predictions found: {result.get('predictions_found', 0)}")
        print(f"  Predictions filtered: {result.get('predictions_filtered', 0)}")
        print(f"  Bets created: {result.get('bets_created', 0)}")
        print(f"  Total stake: ${result.get('total_stake', 0):.2f}")
        print(f"  Bankroll remaining: ${result.get('bankroll_remaining', 0):.2f}")

    finally:
        db.close()

    print("=" * 50)
