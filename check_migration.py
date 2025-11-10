"""
Check Groups Migration Status

This script verifies if the groups migration completed successfully.
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from db import SessionLocal
from models import Group, Poll, SpreadPoll, User, GroupMembership
from sqlalchemy import select, func

def check_migration_status():
    session = SessionLocal()

    try:
        print("\n" + "="*60)
        print("GROUPS MIGRATION STATUS CHECK")
        print("="*60 + "\n")

        # Check for CLAAMP group
        print("[1/5] Checking for CLAAMP group...")
        claamp = session.execute(
            select(Group).where(Group.name == 'CLAAMP')
        ).scalar_one_or_none()

        if claamp:
            print(f"  ✓ CLAAMP group exists")
            print(f"    - ID: {claamp.id}")
            print(f"    - Public: {claamp.is_public}")
            print(f"    - Description: {claamp.description[:50] if claamp.description else 'None'}...")
        else:
            print(f"  ✗ CLAAMP group NOT found")
            print(f"    Action needed: Create CLAAMP group manually")

        # Check group memberships
        print("\n[2/5] Checking group memberships...")
        if claamp:
            member_count = session.execute(
                select(func.count(GroupMembership.id))
                .where(GroupMembership.group_id == claamp.id)
            ).scalar()
            total_users = session.execute(
                select(func.count(User.id))
            ).scalar()
            print(f"  ✓ CLAAMP has {member_count} members")
            print(f"    - Total users in system: {total_users}")
            if member_count < total_users:
                print(f"    ⚠ Warning: {total_users - member_count} users are not in CLAAMP")
        else:
            print(f"  - Skipped (no CLAAMP group)")

        # Check polls with group_id
        print("\n[3/5] Checking polls...")
        polls_total = session.execute(select(func.count(Poll.id))).scalar()
        polls_with_group = session.execute(
            select(func.count(Poll.id)).where(Poll.group_id.isnot(None))
        ).scalar()
        polls_without_group = session.execute(
            select(func.count(Poll.id)).where(Poll.group_id.is_(None))
        ).scalar()

        print(f"  Total polls: {polls_total}")
        print(f"  ✓ Polls with group_id: {polls_with_group}")
        if polls_without_group > 0:
            print(f"  ✗ Polls WITHOUT group_id: {polls_without_group}")
            print(f"    Action needed: Assign these polls to CLAAMP")

        # Check spread_polls with group_id
        print("\n[4/5] Checking spread polls...")
        spreads_total = session.execute(select(func.count(SpreadPoll.id))).scalar()
        spreads_with_group = session.execute(
            select(func.count(SpreadPoll.id)).where(SpreadPoll.group_id.isnot(None))
        ).scalar()
        spreads_without_group = session.execute(
            select(func.count(SpreadPoll.id)).where(SpreadPoll.group_id.is_(None))
        ).scalar()

        print(f"  Total spread polls: {spreads_total}")
        print(f"  ✓ Spread polls with group_id: {spreads_with_group}")
        if spreads_without_group > 0:
            print(f"  ✗ Spread polls WITHOUT group_id: {spreads_without_group}")
            print(f"    Action needed: Assign these to CLAAMP")

        # Overall status
        print("\n[5/5] Overall Status")
        print("="*60)

        migration_complete = (
            claamp is not None and
            polls_without_group == 0 and
            spreads_without_group == 0 and
            (member_count == total_users if claamp else False)
        )

        if migration_complete:
            print("✅ MIGRATION COMPLETE!")
            print("\nAll data successfully migrated to groups system.")
            print(f"- CLAAMP group created with {member_count} members")
            print(f"- {polls_with_group} polls assigned to CLAAMP")
            print(f"- {spreads_with_group} spread polls assigned to CLAAMP")
            print("\n🚀 Ready for Phase 2: Update routes and create templates")
        else:
            print("⚠️  MIGRATION INCOMPLETE")
            print("\nIssues detected:")
            if not claamp:
                print("  - CLAAMP group not created")
            if polls_without_group > 0:
                print(f"  - {polls_without_group} polls need group assignment")
            if spreads_without_group > 0:
                print(f"  - {spreads_without_group} spread polls need group assignment")
            if claamp and member_count < total_users:
                print(f"  - {total_users - member_count} users not added to CLAAMP")

            print("\n💡 Next steps:")
            print("  1. Run: python fix_migration.py")
            print("     (I can create this script if needed)")

        print("="*60 + "\n")

    finally:
        session.close()

if __name__ == "__main__":
    check_migration_status()
