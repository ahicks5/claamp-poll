"""
Migration script to add Groups feature to existing database.

This script:
1. Creates new tables: groups, group_memberships
2. Adds group_id column to polls and spread_polls tables
3. Creates default "CLAAMP" public group
4. Assigns all existing polls and spread_polls to CLAAMP
5. Adds all existing users as members of CLAAMP

Run this ONCE to migrate your existing database to support groups.
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
from sqlalchemy import text, inspect
from db import SessionLocal, engine
from models import Base, Group, GroupMembership, User

def check_if_migrated():
    """Check if groups tables already exist"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return 'groups' in tables

def run_migration():
    """Run the groups migration"""
    session = SessionLocal()

    try:
        print("\n" + "="*60)
        print("GROUPS MIGRATION")
        print("="*60 + "\n")

        # Check if already migrated
        if check_if_migrated():
            print("[!] Groups tables already exist!")
            print("[!] This migration has already been run.")
            print("[!] Exiting to prevent data corruption.")
            print("\nIf you need to re-run, please drop the tables first:")
            print("  - groups")
            print("  - group_memberships")
            print("  And remove group_id columns from polls and spread_polls\n")
            return

        print("[1/5] Creating new tables (groups, group_memberships)...")
        Base.metadata.create_all(bind=engine)
        print("  ✓ Tables created")

        print("\n[2/5] Adding group_id column to polls table...")
        try:
            session.execute(text("ALTER TABLE polls ADD COLUMN group_id INTEGER"))
            session.commit()
            print("  ✓ Added group_id to polls")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("  ✓ Column already exists, skipping")
                session.rollback()
            else:
                raise

        print("\n[3/5] Adding group_id column to spread_polls table...")
        try:
            session.execute(text("ALTER TABLE spread_polls ADD COLUMN group_id INTEGER"))
            session.commit()
            print("  ✓ Added group_id to spread_polls")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("  ✓ Column already exists, skipping")
                session.rollback()
            else:
                raise

        print("\n[4/5] Creating default 'CLAAMP' group...")

        # Get first admin user or first user
        first_user = session.execute(
            text("SELECT id FROM users WHERE is_admin = 1 LIMIT 1")
        ).first()

        if not first_user:
            first_user = session.execute(
                text("SELECT id FROM users LIMIT 1")
            ).first()

        creator_id = first_user[0] if first_user else None

        # Create CLAAMP group
        claamp_group = Group(
            name="CLAAMP",
            description="The original Take Free Points community - everyone's default group",
            is_public=True,
            invite_code=None,  # Public, no invite code needed
            created_by_user_id=creator_id
        )
        session.add(claamp_group)
        session.flush()

        print(f"  ✓ Created CLAAMP group (ID: {claamp_group.id})")

        print("\n[5/5] Migrating existing data...")

        # Assign all existing polls to CLAAMP
        poll_count = session.execute(
            text("UPDATE polls SET group_id = :group_id"),
            {"group_id": claamp_group.id}
        ).rowcount
        print(f"  ✓ Assigned {poll_count} poll(s) to CLAAMP")

        # Assign all existing spread_polls to CLAAMP
        spread_poll_count = session.execute(
            text("UPDATE spread_polls SET group_id = :group_id"),
            {"group_id": claamp_group.id}
        ).rowcount
        print(f"  ✓ Assigned {spread_poll_count} spread poll(s) to CLAAMP")

        # Add all existing users to CLAAMP group
        users = session.execute(text("SELECT id FROM users")).all()
        user_count = 0
        for user_row in users:
            membership = GroupMembership(
                group_id=claamp_group.id,
                user_id=user_row[0],
                role="member"
            )
            session.add(membership)
            user_count += 1

        print(f"  ✓ Added {user_count} user(s) to CLAAMP group")

        # Make creator an owner if they exist
        if creator_id:
            session.execute(
                text("UPDATE group_memberships SET role = 'owner' WHERE group_id = :group_id AND user_id = :user_id"),
                {"group_id": claamp_group.id, "user_id": creator_id}
            )
            print(f"  ✓ Set user {creator_id} as owner")

        # Commit all changes
        session.commit()

        print("\n" + "="*60)
        print("MIGRATION COMPLETE!")
        print("="*60)
        print("\nSummary:")
        print(f"  • Created 'CLAAMP' group (ID: {claamp_group.id})")
        print(f"  • Migrated {poll_count} polls")
        print(f"  • Migrated {spread_poll_count} spread polls")
        print(f"  • Added {user_count} users as members")
        print("\nAll existing data is now part of the CLAAMP group.")
        print("Users can now create additional groups!\n")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("\nWARNING: This will modify your database structure!")
    print("It's recommended to backup your database first.\n")

    response = input("Continue with migration? (yes/no): ")
    if response.lower() in ('yes', 'y'):
        run_migration()
    else:
        print("Migration cancelled.")
