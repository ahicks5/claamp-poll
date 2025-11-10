"""
Fix incomplete Groups migration

This script completes any missing steps from the migration:
- Creates CLAAMP group if missing
- Assigns polls/spread_polls to CLAAMP
- Adds users to CLAAMP group
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
from sqlalchemy import select, text
from db import SessionLocal
from models import Group, Poll, SpreadPoll, User, GroupMembership

def fix_migration():
    session = SessionLocal()

    try:
        print("\n" + "="*60)
        print("FIXING GROUPS MIGRATION")
        print("="*60 + "\n")

        # Step 1: Get or create CLAAMP group
        print("[1/4] Checking CLAAMP group...")
        claamp = session.execute(
            select(Group).where(Group.name == 'CLAAMP')
        ).scalar_one_or_none()

        if not claamp:
            print("  Creating CLAAMP group...")

            # Get first admin or first user
            first_user = session.execute(
                select(User).where(User.is_admin == True)
            ).first()

            if not first_user:
                first_user = session.execute(select(User)).first()

            creator_id = first_user[0].id if first_user else None

            claamp = Group(
                name="CLAAMP",
                description="The original Take Free Points community - everyone's default group",
                is_public=True,
                invite_code=None,
                created_by_user_id=creator_id
            )
            session.add(claamp)
            session.flush()
            print(f"  ✓ Created CLAAMP group (ID: {claamp.id})")
        else:
            print(f"  ✓ CLAAMP group exists (ID: {claamp.id})")

        # Step 2: Assign polls to CLAAMP
        print("\n[2/4] Assigning polls to CLAAMP...")
        polls_updated = session.execute(
            text("UPDATE polls SET group_id = :group_id WHERE group_id IS NULL"),
            {"group_id": claamp.id}
        ).rowcount
        print(f"  ✓ Assigned {polls_updated} poll(s) to CLAAMP")

        # Step 3: Assign spread_polls to CLAAMP
        print("\n[3/4] Assigning spread polls to CLAAMP...")
        spreads_updated = session.execute(
            text("UPDATE spread_polls SET group_id = :group_id WHERE group_id IS NULL"),
            {"group_id": claamp.id}
        ).rowcount
        print(f"  ✓ Assigned {spreads_updated} spread poll(s) to CLAAMP")

        # Step 4: Add users to CLAAMP
        print("\n[4/4] Adding users to CLAAMP group...")

        # Get all users not in CLAAMP
        users_in_claamp = session.execute(
            select(GroupMembership.user_id)
            .where(GroupMembership.group_id == claamp.id)
        ).scalars().all()

        all_users = session.execute(select(User.id)).scalars().all()

        users_to_add = set(all_users) - set(users_in_claamp)

        added_count = 0
        for user_id in users_to_add:
            membership = GroupMembership(
                group_id=claamp.id,
                user_id=user_id,
                role="member"
            )
            session.add(membership)
            added_count += 1

        print(f"  ✓ Added {added_count} user(s) to CLAAMP")

        # Set creator as owner if they exist
        if claamp.created_by_user_id:
            session.execute(
                text("""
                    UPDATE group_memberships
                    SET role = 'owner'
                    WHERE group_id = :group_id AND user_id = :user_id
                """),
                {"group_id": claamp.id, "user_id": claamp.created_by_user_id}
            )
            print(f"  ✓ Set user {claamp.created_by_user_id} as owner")

        # Commit everything
        session.commit()

        print("\n" + "="*60)
        print("✅ MIGRATION FIXED SUCCESSFULLY!")
        print("="*60)
        print(f"\nSummary:")
        print(f"  - CLAAMP group: {claamp.name} (ID: {claamp.id})")
        print(f"  - Polls migrated: {polls_updated}")
        print(f"  - Spread polls migrated: {spreads_updated}")
        print(f"  - Users added: {added_count}")
        print("\n🚀 Ready to proceed with Phase 2!\n")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Fix failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("\nThis will fix any incomplete migration steps.")
    response = input("Continue? (yes/no): ")
    if response.lower() in ('yes', 'y'):
        fix_migration()
    else:
        print("Cancelled.")
