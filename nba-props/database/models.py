# database/models.py
"""SQLAlchemy models for NBA props prediction system."""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index, func, Text, Date
)
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime


class Team(Base):
    """NBA teams - reference data."""
    __tablename__ = "nba_teams"

    id = Column(Integer, primary_key=True)
    nba_team_id = Column(Integer, unique=True, nullable=False, index=True)  # Official NBA API ID
    name = Column(String(128), nullable=False)  # e.g., "Los Angeles Lakers"
    abbreviation = Column(String(10), nullable=False, index=True)  # e.g., "LAL"
    city = Column(String(128), nullable=True)
    conference = Column(String(10), nullable=True)  # "East" or "West"
    division = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    players = relationship("Player", back_populates="team")

    def __repr__(self):
        return f"<Team {self.abbreviation} - {self.name}>"


class Player(Base):
    """NBA players - reference data."""
    __tablename__ = "nba_players"

    id = Column(Integer, primary_key=True)
    nba_player_id = Column(Integer, unique=True, nullable=False, index=True)  # Official NBA API ID
    full_name = Column(String(128), nullable=False, index=True)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)

    team_id = Column(Integer, ForeignKey("nba_teams.id"), nullable=True, index=True)
    position = Column(String(10), nullable=True)  # e.g., "PG", "SG", "SF", "PF", "C"
    jersey_number = Column(String(10), nullable=True)
    height = Column(String(10), nullable=True)  # e.g., "6-6"
    weight = Column(String(10), nullable=True)  # e.g., "250"

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    team = relationship("Team", back_populates="players")
    game_stats = relationship("PlayerGameStats", back_populates="player")
    prop_lines = relationship("PropLine", back_populates="player")
    predictions = relationship("Prediction", back_populates="player")

    def __repr__(self):
        return f"<Player {self.full_name}>"


class Game(Base):
    """NBA games."""
    __tablename__ = "nba_games"

    id = Column(Integer, primary_key=True)
    nba_game_id = Column(String(20), unique=True, nullable=False, index=True)  # NBA API game ID

    game_date = Column(Date, nullable=False, index=True)
    game_time = Column(DateTime(timezone=True), nullable=True)
    season = Column(String(10), nullable=False, index=True)  # e.g., "2024-25"

    home_team_id = Column(Integer, ForeignKey("nba_teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("nba_teams.id"), nullable=False, index=True)

    # Game status
    status = Column(String(20), nullable=False, default="scheduled")  # scheduled, in_progress, final, postponed

    # Final scores
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)

    # Additional metadata
    arena = Column(String(128), nullable=True)
    attendance = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    player_stats = relationship("PlayerGameStats", back_populates="game", cascade="all, delete-orphan")
    prop_lines = relationship("PropLine", back_populates="game", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="game", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_nba_games_date_teams", "game_date", "home_team_id", "away_team_id"),
    )

    def __repr__(self):
        return f"<Game {self.nba_game_id}: {self.away_team_id}@{self.home_team_id} on {self.game_date}>"


class PlayerGameStats(Base):
    """Actual player performance in a specific game."""
    __tablename__ = "nba_player_game_stats"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("nba_players.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("nba_games.id"), nullable=False, index=True)

    # Playing time
    minutes = Column(Float, nullable=True)
    seconds_played = Column(Integer, nullable=True)

    # Scoring
    points = Column(Integer, nullable=True)
    field_goals_made = Column(Integer, nullable=True)
    field_goals_attempted = Column(Integer, nullable=True)
    three_pointers_made = Column(Integer, nullable=True)
    three_pointers_attempted = Column(Integer, nullable=True)
    free_throws_made = Column(Integer, nullable=True)
    free_throws_attempted = Column(Integer, nullable=True)

    # Rebounding
    rebounds = Column(Integer, nullable=True)
    offensive_rebounds = Column(Integer, nullable=True)
    defensive_rebounds = Column(Integer, nullable=True)

    # Playmaking
    assists = Column(Integer, nullable=True)
    turnovers = Column(Integer, nullable=True)

    # Defense
    steals = Column(Integer, nullable=True)
    blocks = Column(Integer, nullable=True)
    personal_fouls = Column(Integer, nullable=True)

    # Advanced
    plus_minus = Column(Integer, nullable=True)

    # Game context
    started = Column(Boolean, nullable=True)  # Did player start the game?
    dnp_reason = Column(String(128), nullable=True)  # Did Not Play reason (injury, rest, etc.)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    player = relationship("Player", back_populates="game_stats")
    game = relationship("Game", back_populates="player_stats")

    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="uq_player_game"),
        Index("ix_player_stats_player_game", "player_id", "game_id"),
    )

    def __repr__(self):
        return f"<PlayerGameStats {self.player_id} in game {self.game_id}: {self.points}pts/{self.rebounds}reb/{self.assists}ast>"


class PropLine(Base):
    """Betting lines for player props from sportsbooks."""
    __tablename__ = "nba_prop_lines"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("nba_players.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("nba_games.id"), nullable=False, index=True)

    # Prop details
    prop_type = Column(String(50), nullable=False, index=True)  # e.g., "points", "rebounds", "assists", "pts+reb+ast"
    line_value = Column(Float, nullable=False)  # The over/under number (e.g., 25.5 points)

    # Odds
    over_odds = Column(Integer, nullable=True)  # American odds (e.g., -110)
    under_odds = Column(Integer, nullable=True)

    # Sportsbook info
    sportsbook = Column(String(50), nullable=False, index=True)  # e.g., "draftkings", "fanduel"
    market_key = Column(String(128), nullable=True)  # Odds API market identifier

    # Metadata
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_latest = Column(Boolean, default=True, nullable=False)  # Track if this is the most recent line

    # Relationships
    player = relationship("Player", back_populates="prop_lines")
    game = relationship("Game", back_populates="prop_lines")

    __table_args__ = (
        Index("ix_prop_lines_player_game_type", "player_id", "game_id", "prop_type"),
        Index("ix_prop_lines_fetched", "fetched_at", "is_latest"),
    )

    def __repr__(self):
        return f"<PropLine {self.player_id} {self.prop_type} {self.line_value} ({self.sportsbook})>"


class Prediction(Base):
    """Our model's predictions for player props."""
    __tablename__ = "nba_predictions"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("nba_players.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("nba_games.id"), nullable=False, index=True)

    # Prediction details
    prop_type = Column(String(50), nullable=False, index=True)
    predicted_value = Column(Float, nullable=False)  # Our predicted stat (e.g., 27.3 points)
    line_value = Column(Float, nullable=True)  # The betting line at time of prediction

    # Model info
    model_version = Column(String(50), nullable=True)  # e.g., "v1.0", "xgboost_v2"
    confidence_score = Column(Float, nullable=True)  # 0-1 confidence

    # Recommendation
    recommended_pick = Column(String(10), nullable=True)  # "over", "under", or null if no pick
    edge = Column(Float, nullable=True)  # Predicted edge over the line (predicted - line)

    # Features used (for debugging)
    features_json = Column(Text, nullable=True)  # JSON string of features used

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    player = relationship("Player", back_populates="predictions")
    game = relationship("Game", back_populates="predictions")
    result = relationship("Result", back_populates="prediction", uselist=False)

    __table_args__ = (
        Index("ix_predictions_player_game_type", "player_id", "game_id", "prop_type"),
    )

    def __repr__(self):
        return f"<Prediction {self.player_id} {self.prop_type}: {self.predicted_value} ({self.recommended_pick})>"


class Result(Base):
    """Tracking accuracy of our predictions."""
    __tablename__ = "nba_results"

    id = Column(Integer, primary_key=True)
    prediction_id = Column(Integer, ForeignKey("nba_predictions.id"), nullable=False, unique=True, index=True)

    # Actual outcome
    actual_value = Column(Float, nullable=True)  # Actual stat achieved (e.g., 29 points)
    was_correct = Column(Boolean, nullable=True)  # Did our pick (over/under) win?

    # Profit/Loss tracking (if we were betting)
    bet_amount = Column(Float, nullable=True, default=1.0)  # Unit size
    profit_loss = Column(Float, nullable=True)  # Calculated profit/loss

    # Metadata
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    prediction = relationship("Prediction", back_populates="result")

    def __repr__(self):
        return f"<Result for prediction {self.prediction_id}: actual={self.actual_value}, correct={self.was_correct}>"
