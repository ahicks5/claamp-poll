"""
Manual data migration script - Move user and ballot between groups.

This script:
1. Moves CoachCalATX from CLAAMP to Degens FF
2. Moves his ballot from CLAAMP poll to Degens FF poll
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from sqlalchemy import select
from db import SessionLocal
from models import User, Group, GroupMembership, Poll, Ballot, BallotItem

def run_migration():
    session = SessionLocal()

    try:
        print("\n" + "="*60)
        print("USER AND BALLOT MIGRATION")
        print("="*60 + "\n")

        # 1. Find the user
        print("[1/4] Finding user CoachCalATX...")
        user = session.execute(
            select(User).where(User.username == "CoachCalATX")
        ).scalar_one_or_none()

        if not user:
            print("  [!] User CoachCalATX not found!")
            return

        print(f"  ✓ Found user: {user.username} (ID: {user.id})")

        # 2. Find the groups
        print("\n[2/4] Finding groups...")
        claamp = session.execute(
            select(Group).where(Group.name == "CLAAMP")
        ).scalar_one_or_none()

        degens = session.execute(
            select(Group).where(Group.name == "Degens FF")
        ).scalar_one_or_none()

        if not claamp or not degens:
            print(f"  [!] Could not find groups!")
            print(f"      CLAAMP: {claamp.name if claamp else 'NOT FOUND'}")
            print(f"      Degens FF: {degens.name if degens else 'NOT FOUND'}")
            return

        print(f"  ✓ CLAAMP group (ID: {claamp.id})")
        print(f"  ✓ Degens FF group (ID: {degens.id})")

        # 3. Move user from CLAAMP to Degens FF
        print("\n[3/4] Moving user between groups...")

        # Check if already in Degens FF
        degens_membership = session.execute(
            select(GroupMembership).where(
                GroupMembership.user_id == user.id,
                GroupMembership.group_id == degens.id
            )
        ).scalar_one_or_none()

        if not degens_membership:
            # Add to Degens FF
            new_membership = GroupMembership(
                user_id=user.id,
                group_id=degens.id,
                role="member"
            )
            session.add(new_membership)
            print(f"  ✓ Added {user.username} to Degens FF")
        else:
            print(f"  ✓ {user.username} already in Degens FF")

        # Remove from CLAAMP
        claamp_membership = session.execute(
            select(GroupMembership).where(
                GroupMembership.user_id == user.id,
                GroupMembership.group_id == claamp.id
            )
        ).scalar_one_or_none()

        if claamp_membership:
            session.delete(claamp_membership)
            print(f"  ✓ Removed {user.username} from CLAAMP")
        else:
            print(f"  ⚠ {user.username} was not in CLAAMP")

        # 4. Move ballot between polls
        print("\n[4/4] Moving ballot between polls...")

        # Find the polls
        claamp_poll = session.execute(
            select(Poll).where(
                Poll.group_id == claamp.id,
                Poll.title.ilike("%After Week 11%")
            )
        ).scalar_one_or_none()

        degens_poll = session.execute(
            select(Poll).where(
                Poll.group_id == degens.id,
                Poll.title.ilike("%Week 11%")
            )
        ).scalar_one_or_none()

        if not claamp_poll:
            print("  [!] Could not find 'CLAAMP - After Week 11' poll")
        elif not degens_poll:
            print("  [!] Could not find 'Week 11 Poll' in Degens FF")
        else:
            print(f"  ✓ Found CLAAMP poll: {claamp_poll.title} (ID: {claamp_poll.id})")
            print(f"  ✓ Found Degens poll: {degens_poll.title} (ID: {degens_poll.id})")

            # Find user's ballot in CLAAMP poll
            ballot = session.execute(
                select(Ballot).where(
                    Ballot.poll_id == claamp_poll.id,
                    Ballot.user_id == user.id
                )
            ).scalar_one_or_none()

            if not ballot:
                print(f"  [!] No ballot found for {user.username} in CLAAMP poll")
            else:
                print(f"  ✓ Found ballot (ID: {ballot.id})")

                # Check if ballot already exists in Degens poll
                existing_degens_ballot = session.execute(
                    select(Ballot).where(
                        Ballot.poll_id == degens_poll.id,
                        Ballot.user_id == user.id
                    )
                ).scalar_one_or_none()

                if existing_degens_ballot:
                    print(f"  [!] Ballot already exists in Degens FF poll")
                    print(f"      Deleting old ballot from Degens FF first...")
                    session.delete(existing_degens_ballot)

                # Move the ballot by changing poll_id
                ballot.poll_id = degens_poll.id
                print(f"  ✓ Moved ballot to Degens FF poll")

        # Commit all changes
        session.commit()

        print("\n" + "="*60)
        print("MIGRATION COMPLETE!")
        print("="*60)
        print(f"\n✓ {user.username} is now in Degens FF group")
        print(f"✓ {user.username} is removed from CLAAMP group")
        if claamp_poll and degens_poll and ballot:
            print(f"✓ {user.username}'s ballot moved to Degens FF poll")
        print()

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    print("\nThis will move CoachCalATX from CLAAMP to Degens FF")
    print("and migrate his poll ballot.\n")

    response = input("Continue? (yes/no): ")
    if response.lower() in ('yes', 'y'):
        run_migration()
    else:
        print("Migration cancelled.")
