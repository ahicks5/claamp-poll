# models.py
"""
TakeFreePoints.com - Data-driven sports betting models
Main database models for user management and betting strategy tracking
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Date, Text, Index, UniqueConstraint, func
from sqlalchemy.orm import relationship
from db import Base
from datetime import datetime, timezone


# ============================================================
# USER & AUTHENTICATION
# ============================================================

class User(Base):
    """User accounts for TakeFreePoints.com"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    pw_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    bet_journal_entries = relationship("BetJournal", back_populates="user", cascade="all, delete-orphan")

    # Flask-Login helpers
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User {self.username}>"


# ============================================================
# BETTING STRATEGY SYSTEM
# ============================================================

class Strategy(Base):
    """
    Betting strategies for systematic play selection
    Each strategy defines rules for which bets to take and how to size them
    """
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Strategy identity
    name = Column(String(128), nullable=False)  # e.g., "NBA Props - Conservative"
    description = Column(Text, nullable=True)

    # Sport & market filters
    sport = Column(String(50), nullable=False, default="NBA")  # NBA, NFL, MLB, etc.
    prop_types = Column(String(255), nullable=True)  # Comma-separated: "points,rebounds,assists"

    # Selection criteria
    min_edge = Column(Float, nullable=False, default=1.5)  # Minimum edge to trigger a bet (in stat units)
    min_confidence = Column(Float, nullable=True)  # Minimum model confidence (0-1)

    # Bankroll management
    initial_bankroll = Column(Float, nullable=False, default=100.0)  # Starting amount ($)
    bet_sizing_method = Column(String(50), nullable=False, default="kelly")  # "kelly", "flat", "percentage"
    kelly_fraction = Column(Float, nullable=True, default=0.25)  # Fractional Kelly (e.g., 0.25 = quarter Kelly)
    flat_bet_amount = Column(Float, nullable=True)  # For flat betting
    percentage_of_bankroll = Column(Float, nullable=True)  # For percentage betting (e.g., 0.02 = 2%)

    # Max exposure limits
    max_bet_amount = Column(Float, nullable=True)  # Hard cap on any single bet
    max_daily_bets = Column(Integer, nullable=True)  # Max bets per day
    max_daily_exposure = Column(Float, nullable=True)  # Max $ at risk per day

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="strategies")
    bets = relationship("BetJournal", back_populates="strategy")

    def __repr__(self):
        return f"<Strategy {self.name} - {self.sport}>"


# ============================================================
# BET TRACKING
# ============================================================

class BetJournal(Base):
    """
    Complete record of all bets placed
    Auto-created from daily predictions or manually entered
    """
    __tablename__ = "bet_journal"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)

    # Bet identification
    prediction_id = Column(Integer, nullable=True)  # Link to nba_predictions.id (if from NBA props)
    external_ref = Column(String(128), nullable=True)  # External bet ID (from sportsbook)

    # Game context
    game_date = Column(Date, nullable=False, index=True)
    sport = Column(String(50), nullable=False, default="NBA")
    player_name = Column(String(128), nullable=True)  # For player props
    game_description = Column(String(255), nullable=True)  # e.g., "LAL @ BOS"

    # Bet details
    prop_type = Column(String(50), nullable=False)  # "points", "rebounds", "assists", etc.
    line_value = Column(Float, nullable=False)  # The over/under line (e.g., 25.5)
    pick = Column(String(10), nullable=False)  # "over" or "under"

    # Prediction context
    predicted_value = Column(Float, nullable=True)  # Our model's prediction
    edge = Column(Float, nullable=True)  # Our edge (predicted - line)
    confidence = Column(Float, nullable=True)  # Model confidence (0-1)

    # Odds & sizing
    odds = Column(Integer, nullable=True)  # American odds (e.g., -110)
    stake = Column(Float, nullable=False)  # Amount wagered ($)
    to_win = Column(Float, nullable=True)  # Potential profit ($)

    # Bet status
    status = Column(String(20), nullable=False, default="pending")  # "pending", "won", "lost", "push", "cancelled"
    actual_value = Column(Float, nullable=True)  # Actual stat achieved (once game is final)

    # Results
    profit_loss = Column(Float, nullable=True)  # Actual P&L once settled ($)

    # Timestamps
    placed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="bet_journal_entries")
    strategy = relationship("Strategy", back_populates="bets")

    __table_args__ = (
        Index("ix_bet_journal_user_date", "user_id", "game_date"),
        Index("ix_bet_journal_status", "status"),
    )

    def __repr__(self):
        return f"<BetJournal {self.player_name} {self.prop_type} {self.pick} {self.line_value} - {self.status}>"


# ============================================================
# PERFORMANCE TRACKING
# ============================================================

class DailyPerformance(Base):
    """
    Aggregated daily performance metrics
    Calculated each day to track overall strategy performance
    """
    __tablename__ = "daily_performance"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)

    # Date
    date = Column(Date, nullable=False, index=True)

    # Bet counts
    bets_placed = Column(Integer, default=0, nullable=False)
    bets_won = Column(Integer, default=0, nullable=False)
    bets_lost = Column(Integer, default=0, nullable=False)
    bets_push = Column(Integer, default=0, nullable=False)
    bets_pending = Column(Integer, default=0, nullable=False)

    # Financial metrics
    total_staked = Column(Float, default=0.0, nullable=False)  # Total $ wagered
    total_won = Column(Float, default=0.0, nullable=False)  # Total $ won
    total_lost = Column(Float, default=0.0, nullable=False)  # Total $ lost
    net_profit_loss = Column(Float, default=0.0, nullable=False)  # Net P&L for the day

    # Performance metrics
    win_rate = Column(Float, nullable=True)  # Win rate (0-1)
    roi = Column(Float, nullable=True)  # Return on investment (P&L / total_staked)

    # Bankroll
    bankroll_start = Column(Float, nullable=True)  # Bankroll at start of day
    bankroll_end = Column(Float, nullable=True)  # Bankroll at end of day

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "strategy_id", "date", name="uq_daily_perf_user_strategy_date"),
        Index("ix_daily_perf_user_date", "user_id", "date"),
    )

    def __repr__(self):
        return f"<DailyPerformance {self.date}: {self.bets_won}W-{self.bets_lost}L, P&L: ${self.net_profit_loss:.2f}>"


class BankrollHistory(Base):
    """
    Historical bankroll snapshots for tracking growth over time
    Can be daily or after each bet
    """
    __tablename__ = "bankroll_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)

    # Snapshot
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    bankroll = Column(Float, nullable=False)  # Current bankroll ($)

    # Context
    event_type = Column(String(50), nullable=True)  # "bet_placed", "bet_settled", "daily_snapshot", "manual_adjustment"
    event_ref = Column(String(128), nullable=True)  # Reference to bet_journal.id or other event
    note = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_bankroll_history_user_time", "user_id", "timestamp"),
    )

    def __repr__(self):
        return f"<BankrollHistory {self.timestamp}: ${self.bankroll:.2f}>"
