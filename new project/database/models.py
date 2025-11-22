"""
Simple NBA Props Database Models
Only what we need: Teams, Players, Games, PropLines
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Date, Index, func
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Team(Base):
    """NBA Teams"""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    nba_team_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    abbreviation = Column(String(10), nullable=False, index=True)
    city = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    players = relationship("Player", back_populates="team")


class Player(Base):
    """NBA Players"""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    nba_player_id = Column(Integer, unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    position = Column(String(10))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    team = relationship("Team", back_populates="players")
    prop_lines = relationship("PropLine", back_populates="player")


class Game(Base):
    """NBA Games"""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    nba_game_id = Column(String(64), unique=True, nullable=False, index=True)
    game_date = Column(Date, nullable=False, index=True)
    season = Column(String(10), nullable=False)

    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    status = Column(String(20), default="scheduled")  # scheduled, final, postponed
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    prop_lines = relationship("PropLine", back_populates="game")


class PropLine(Base):
    """Betting Lines for Player Props"""
    __tablename__ = "prop_lines"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)

    prop_type = Column(String(50), nullable=False, index=True)  # points, rebounds, assists, etc.
    line_value = Column(Float, nullable=False)  # The O/U number

    over_odds = Column(Integer)  # American odds (e.g., -110)
    under_odds = Column(Integer)

    sportsbook = Column(String(50), nullable=False)
    is_latest = Column(Boolean, default=True, nullable=False)
    fetched_at = Column(DateTime, server_default=func.now(), index=True)

    # Relationships
    player = relationship("Player", back_populates="prop_lines")
    game = relationship("Game", back_populates="prop_lines")

    __table_args__ = (
        Index("ix_prop_lines_player_game_type", "player_id", "game_id", "prop_type"),
    )
