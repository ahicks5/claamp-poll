# models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import relationship
from db import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    pw_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Flask-Login helpers (simple properties)
    @property
    def is_authenticated(self): return True
    @property
    def is_active(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False, index=True)

class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    season = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    title = Column(String(128), nullable=False)
    is_open = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ballots = relationship("Ballot", back_populates="poll", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("season", "week", name="uq_poll_season_week"),
        Index("ix_poll_open_season_week", "is_open", "season", "week"),
    )

class Ballot(Base):
    __tablename__ = "ballots"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    poll = relationship("Poll", back_populates="ballots")
    user = relationship("User", backref="ballots")
    items = relationship("BallotItem", back_populates="ballot", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_ballot_poll_user"),)

class BallotItem(Base):
    __tablename__ = "ballot_items"
    id = Column(Integer, primary_key=True)
    ballot_id = Column(Integer, ForeignKey("ballots.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=False)  # 1..25
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True)
    ballot = relationship("Ballot", back_populates="items")
    team = relationship("Team")
    __table_args__ = (
        UniqueConstraint("ballot_id", "rank", name="uq_ballot_rank"),
        UniqueConstraint("ballot_id", "team_id", name="uq_ballot_team_unique"),
        Index("ix_ballot_items_rank", "rank"),
    )

class DefaultBallot(Base):
    __tablename__ = "default_ballots"

    id       = Column(Integer, primary_key=True)
    poll_id  = Column(Integer, ForeignKey("polls.id"), nullable=True)  # None = global default
    week_key = Column(String(32), nullable=True)  # e.g. "2025w10" or "Nov-07"
    rank     = Column(Integer, nullable=False)
    team_id  = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    team = relationship("Team")
    __table_args__ = (
        UniqueConstraint("poll_id", "week_key", "rank", name="uq_default_slot"),
    )

# ============================================================
# SPREADS SYSTEM MODELS
# ============================================================

class BovadaTeamMapping(Base):
    """Maps Bovada team names to our Team IDs"""
    __tablename__ = "bovada_team_mappings"

    id = Column(Integer, primary_key=True)
    bovada_name = Column(String(255), unique=True, nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    confidence = Column(String(20), nullable=True)  # 'exact', 'fuzzy', 'manual'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    team = relationship("Team")

class SpreadPoll(Base):
    """Weekly spread poll container - like Poll but for spreads"""
    __tablename__ = "spread_polls"

    id = Column(Integer, primary_key=True)
    season = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    title = Column(String(128), nullable=False)  # e.g. "Week 10 - Saturday Games"
    is_open = Column(Boolean, default=True, nullable=False)
    closes_at = Column(DateTime(timezone=True), nullable=True)  # When picks close
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    games = relationship("SpreadGame", back_populates="spread_poll", cascade="all, delete-orphan")
    picks = relationship("SpreadPick", back_populates="spread_poll", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("season", "week", name="uq_spread_poll_season_week"),
        Index("ix_spread_poll_open_season_week", "is_open", "season", "week"),
    )

class SpreadGame(Base):
    """Individual game with spread from Bovada"""
    __tablename__ = "spread_games"

    id = Column(Integer, primary_key=True)
    spread_poll_id = Column(Integer, ForeignKey("spread_polls.id", ondelete="CASCADE"), nullable=False, index=True)
    bovada_event_id = Column(String(128), nullable=True, index=True)  # Link back to Bovada

    home_team_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)

    # Spread values (from Bovada)
    home_spread = Column(String(20), nullable=True)  # e.g. "-3.5"
    away_spread = Column(String(20), nullable=True)  # e.g. "+3.5"

    game_time = Column(DateTime(timezone=True), nullable=True)  # Kickoff time
    game_day = Column(String(20), nullable=True)  # e.g. "Saturday" for grouping in UI

    # Game status
    status = Column(String(50), nullable=True)  # 'scheduled', 'in_progress', 'final'

    # Final scores (to determine winners)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    spread_poll = relationship("SpreadPoll", back_populates="games")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    picks = relationship("SpreadPick", back_populates="game", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_spread_game_teams", "home_team_id", "away_team_id"),
        Index("ix_spread_game_time", "game_time"),
    )

class SpreadPick(Base):
    """User's pick for a game"""
    __tablename__ = "spread_picks"

    id = Column(Integer, primary_key=True)
    spread_poll_id = Column(Integer, ForeignKey("spread_polls.id", ondelete="CASCADE"), nullable=False, index=True)
    spread_game_id = Column(Integer, ForeignKey("spread_games.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    picked_team_id = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    spread_value = Column(String(20), nullable=True)  # Store the spread at time of pick (e.g. "-3.5")

    picked_at = Column(DateTime(timezone=True), server_default=func.now())

    # Results (computed after game finishes)
    is_correct = Column(Boolean, nullable=True)  # NULL until game is final

    spread_poll = relationship("SpreadPoll", back_populates="picks")
    game = relationship("SpreadGame", back_populates="picks")
    user = relationship("User", backref="spread_picks")
    picked_team = relationship("Team")

    __table_args__ = (
        UniqueConstraint("spread_poll_id", "spread_game_id", "user_id", name="uq_spread_pick_user_game"),
        Index("ix_spread_pick_user_poll", "user_id", "spread_poll_id"),
    )

