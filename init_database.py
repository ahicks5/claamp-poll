#!/usr/bin/env python3
"""
Initialize TakeFreePoints.com database
Creates all tables and sets up admin user with initial strategy
"""
import os
from werkzeug.security import generate_password_hash
from db import SessionLocal, engine, Base
from models import User, Strategy, BankrollHistory
from datetime import datetime, timezone


def init_database():
    """Initialize database schema and create admin user"""
    print("🔧 TakeFreePoints.com Database Initialization")
    print("=" * 50)

    # Create session
    db_session = SessionLocal()

    # Drop all existing tables (fresh start)
    print("\n1. Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("   ✓ Old tables dropped")

    # Create all tables from models
    print("\n2. Creating new tables...")
    Base.metadata.create_all(bind=engine)
    print("   ✓ Tables created:")
    print("     - users")
    print("     - strategies")
    print("     - bet_journal")
    print("     - daily_performance")
    print("     - bankroll_history")

    # Create admin user
    print("\n3. Creating admin user...")
    admin_username = os.getenv("ADMIN_USERNAME", "ahicks5")
    admin_email = os.getenv("ADMIN_EMAIL", "arhicks14@yahoo.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "ihateAndrew0!")

    admin_user = User(
        username=admin_username,
        email=admin_email,
        pw_hash=generate_password_hash(admin_password),
        is_admin=True,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(admin_user)
    db_session.flush()  # Get the user ID

    print(f"   ✓ Admin user created: {admin_username} ({admin_email})")

    # Create default strategy
    print("\n4. Creating default NBA Props strategy...")
    default_strategy = Strategy(
        user_id=admin_user.id,
        name="NBA Props - Main Strategy",
        description="Data-driven NBA player props with Kelly Criterion bet sizing",
        sport="NBA",
        prop_types="points",  # Start with points only
        min_edge=1.5,  # Minimum 1.5 point edge
        initial_bankroll=100.0,  # Starting with $100
        bet_sizing_method="kelly",
        kelly_fraction=0.25,  # Quarter Kelly for conservative sizing
        max_bet_amount=20.0,  # Max $20 per bet (20% of initial bankroll)
        max_daily_bets=10,  # Max 10 bets per day
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(default_strategy)
    db_session.flush()  # Get the strategy ID

    print(f"   ✓ Strategy created: {default_strategy.name}")
    print(f"     - Min edge: {default_strategy.min_edge} points")
    print(f"     - Initial bankroll: ${default_strategy.initial_bankroll}")
    print(f"     - Bet sizing: {default_strategy.kelly_fraction * 100}% Kelly")
    print(f"     - Max bet: ${default_strategy.max_bet_amount}")

    # Create initial bankroll snapshot
    print("\n5. Creating initial bankroll snapshot...")
    initial_bankroll = BankrollHistory(
        user_id=admin_user.id,
        strategy_id=default_strategy.id,
        timestamp=datetime.now(timezone.utc),
        bankroll=default_strategy.initial_bankroll,
        event_type="initial_deposit",
        note="Initial bankroll for TakeFreePoints.com launch"
    )
    db_session.add(initial_bankroll)

    print(f"   ✓ Bankroll snapshot created: ${initial_bankroll.bankroll}")

    # Commit all changes
    db_session.commit()
    db_session.close()

    print("\n" + "=" * 50)
    print("✅ Database initialization complete!")
    print("\nYou can now log in with:")
    print(f"   Username: {admin_username}")
    print(f"   Password: {admin_password}")
    print("\n🏀 Ready to start tracking NBA props bets!")
    print("=" * 50)


if __name__ == "__main__":
    init_database()
