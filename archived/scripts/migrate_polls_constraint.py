"""
Migration script to fix polls unique constraint.

This script:
1. Drops old constraint uq_poll_season_week (season, week only)
2. Creates new constraint uq_poll_group_season_week (group_id, season, week)

This allows multiple groups to have polls for the same season/week.

Run this to fix the constraint that prevents multiple groups from having polls.
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
from sqlalchemy import text, inspect
from db import SessionLocal, engine

def get_existing_constraints():
    """Get all constraints on polls table"""
    inspector = inspect(engine)

    # Check if table exists
    tables = inspector.get_table_names()
    if 'polls' not in tables:
        return None, []

    # Get unique constraints
    unique_constraints = inspector.get_unique_constraints('polls')
    return unique_constraints

def run_migration():
    """Run the constraint fix migration"""
    session = SessionLocal()

    try:
        print("\n" + "="*60)
        print("POLLS CONSTRAINT MIGRATION")
        print("="*60 + "\n")

        # Detect database type
        dialect_name = engine.dialect.name
        print(f"[*] Detected database: {dialect_name}")

        # Check existing constraints
        print("\n[1/3] Checking existing constraints...")
        unique_constraints = get_existing_constraints()

        if unique_constraints is None:
            print("[!] polls table does not exist!")
            print("[!] Please run the groups migration first.")
            return

        # Find constraints by name
        old_constraint_exists = False
        new_constraint_exists = False

        for constraint in unique_constraints:
            print(f"  Found constraint: {constraint['name']} on columns {constraint['column_names']}")
            if constraint['name'] == 'uq_poll_season_week':
                old_constraint_exists = True
            if constraint['name'] == 'uq_poll_group_season_week':
                new_constraint_exists = True

        # If the new constraint already exists and old doesn't, we're done
        if new_constraint_exists and not old_constraint_exists:
            print("\n  ✓ Database already has correct constraint!")
            print("  ✓ No migration needed.")
            return

        # SQLite requires table recreation, PostgreSQL can use ALTER TABLE
        if dialect_name == 'sqlite':
            print("\n[2/3] Recreating table for SQLite...")
            print("  [!] SQLite doesn't support ALTER CONSTRAINT directly")
            print("  [!] For SQLite, please use the model definition to recreate tables:")
            print("  [!] Delete the database and run Base.metadata.create_all()")
            print("\n  OR run this on your PostgreSQL production database")
            print("  where ALTER TABLE is supported.\n")
            return

        # PostgreSQL - use ALTER TABLE
        # Step 2: Drop old constraint if it exists
        print("\n[2/3] Dropping old constraint (if exists)...")
        if old_constraint_exists:
            try:
                session.execute(text("""
                    ALTER TABLE polls
                    DROP CONSTRAINT uq_poll_season_week
                """))
                session.commit()
                print("  ✓ Dropped old constraint: uq_poll_season_week")
            except Exception as e:
                print(f"  [!] Could not drop old constraint: {e}")
                session.rollback()
                # If it failed, might already be gone
                if "does not exist" in str(e).lower():
                    print("  ✓ Constraint already removed")
                else:
                    raise
        else:
            print("  ✓ Old constraint does not exist (already removed or never existed)")

        # Step 3: Create new constraint if it doesn't exist
        print("\n[3/3] Creating new constraint (if needed)...")
        if not new_constraint_exists:
            try:
                session.execute(text("""
                    ALTER TABLE polls
                    ADD CONSTRAINT uq_poll_group_season_week
                    UNIQUE (group_id, season, week)
                """))
                session.commit()
                print("  ✓ Created new constraint: uq_poll_group_season_week")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("  ✓ Constraint already exists (created by another process)")
                    session.rollback()
                else:
                    print(f"  [!] Could not create new constraint: {e}")
                    session.rollback()
                    raise
        else:
            print("  ✓ New constraint already exists")

        # Verify final state
        print("\n[✓] Verifying final state...")
        final_constraints = get_existing_constraints()
        print("  Current constraints on polls:")
        for constraint in final_constraints:
            print(f"    • {constraint['name']}: {constraint['column_names']}")

        print("\n" + "="*60)
        print("MIGRATION COMPLETE!")
        print("="*60)
        print("\nYou can now create polls for multiple groups")
        print("with the same season and week.\n")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("\nThis migration will fix the polls constraint to support multiple groups.")
    print("It's safe to run multiple times - it checks before making changes.\n")

    response = input("Continue with migration? (yes/no): ")
    if response.lower() in ('yes', 'y'):
        run_migration()
    else:
        print("Migration cancelled.")
