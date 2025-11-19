# database/db.py
"""Database connection and session management for NBA props system."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from dotenv import load_dotenv

# Load environment variables - try multiple locations
# 1. Try nba-props/.env (development)
nba_props_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
# 2. Try root .env (if running from root directory)
root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')

# Load both (later ones override earlier ones)
load_dotenv(root_env, override=False)  # Load root .env first
load_dotenv(nba_props_env, override=True)  # NBA props .env takes precedence

DATABASE_URL = os.getenv("NBA_DATABASE_URL", "sqlite:///nba_props.db")

# Convert postgres:// to postgresql:// if needed (for Heroku compatibility)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Determine database type for driver-specific configuration
is_postgres = DATABASE_URL.startswith("postgresql://")
is_mysql = DATABASE_URL.startswith("mysql://")
is_sqlite = DATABASE_URL.startswith("sqlite://")

# Configure engine options based on database type
engine_kwargs = {
    "pool_pre_ping": True,
    "future": True,
    "echo": False  # Set to True for SQL query debugging
}

# Add database-specific configurations
if is_postgres:
    # PostgreSQL on Heroku - use connection pooling
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_recycle"] = 3600  # Recycle connections after 1 hour
    print(f"[DB] Configuring PostgreSQL connection")
elif is_mysql:
    # MySQL - add charset and connection settings
    if "?" not in DATABASE_URL:
        DATABASE_URL += "?charset=utf8mb4"
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    print(f"[DB] Configuring MySQL connection")
elif is_sqlite:
    # SQLite - no pooling needed
    engine_kwargs["pool_pre_ping"] = False
    print(f"[DB] Configuring SQLite connection (local dev)")

# Create engine with appropriate configuration
engine = create_engine(DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = scoped_session(
    sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False
    )
)

# Base class for models
Base = declarative_base()


def init_db():
    """Initialize database - create all tables."""
    from .models import Player, Team, Game, PlayerGameStats, PropLine, Prediction, Result
    Base.metadata.create_all(bind=engine)
    print("[OK] Database initialized successfully")


def get_session():
    """Get a new database session. Remember to close it when done!"""
    return SessionLocal()
