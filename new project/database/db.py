"""
Database Connection
Simple SQLite setup
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from database.models import Base

# Database file location
DB_FILE = "props.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Session factory
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False)
)


def init_database():
    """Create all tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print(f"✓ Database created: {DB_FILE}")


def get_session():
    """Get a database session"""
    return SessionLocal()


if __name__ == "__main__":
    # Run this to create the database
    init_database()
