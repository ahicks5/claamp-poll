"""
Update CFP Rankings Script - Replaces global default ballot

This script:
1. Deletes existing global default rankings (poll_id = None)
2. Inserts new CFP rankings as the default ballot

Run this whenever you need to update the default CFP rankings.
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
from sqlalchemy import select, delete
from db import SessionLocal
from models import DefaultBallot, Team

# NEW CFP RANKINGS
NEW_RANKINGS = [
    ("Ohio State", 1),
    ("Indiana", 2),
    ("Texas A&M", 3),
    ("Alabama", 4),
    ("Georgia", 5),
    ("Texas Tech", 6),
    ("Ole Miss", 7),
    ("Oregon", 8),
    ("Notre Dame", 9),
    ("Texas", 10),
    ("Oklahoma", 11),
    ("BYU", 12),
    ("Utah", 13),
    ("Vanderbilt", 14),
    ("Miami", 15),
    ("Georgia Tech", 16),
    ("Southern California", 17),
    ("Michigan", 18),
    ("Virginia", 19),
    ("Louisville", 20),
    ("Iowa", 21),
    ("Pittsburgh", 22),
    ("Tennessee", 23),
    ("South Florida", 24),
    ("Cincinnati", 25),
]

# Common team name variations to handle
TEAM_NAME_MAP = {
    "Texas A&M": ["Texas A&M", "Texas A & M"],
    "Ole Miss": ["Ole Miss", "Mississippi"],
    "Miami": ["Miami", "Miami (FL)", "Miami FL"],
    "Southern California": ["Southern California", "USC", "Southern Cal"],
    "BYU": ["BYU", "Brigham Young"],
    "Georgia Tech": ["Georgia Tech", "Georgia Institute of Technology"],
    "South Florida": ["South Florida", "USF"],
    "Pittsburgh": ["Pittsburgh", "Pitt"],
}

def find_team_id(session, team_name):
    """Find team ID by name, trying variations"""
    # Try exact match first
    team = session.execute(
        select(Team).where(Team.name == team_name)
    ).scalar_one_or_none()

    if team:
        return team.id

    # Try variations
    variations = TEAM_NAME_MAP.get(team_name, [team_name])
    for variant in variations:
        team = session.execute(
            select(Team).where(Team.name == variant)
        ).scalar_one_or_none()
        if team:
            return team.id

    # Try case-insensitive partial match
    team = session.execute(
        select(Team).where(Team.name.ilike(f"%{team_name}%"))
    ).scalars().first()

    if team:
        return team.id

    return None

def run_update():
    """Update the CFP rankings"""
    session = SessionLocal()

    try:
        print("\n" + "="*60)
        print("CFP RANKINGS UPDATE")
        print("="*60 + "\n")

        # Step 1: Delete existing global defaults
        print("[1/3] Removing old global default rankings...")
        deleted_count = session.execute(
            delete(DefaultBallot).where(DefaultBallot.poll_id.is_(None))
        ).rowcount
        session.commit()
        print(f"  ✓ Deleted {deleted_count} old default rankings")

        # Step 2: Get all teams and build lookup
        print("\n[2/3] Loading teams from database...")
        all_teams = session.execute(select(Team)).scalars().all()
        print(f"  ✓ Found {len(all_teams)} teams in database")

        # Step 3: Insert new rankings
        print("\n[3/3] Inserting new CFP rankings...")
        inserted = 0
        not_found = []

        for team_name, rank in NEW_RANKINGS:
            team_id = find_team_id(session, team_name)

            if not team_id:
                not_found.append((rank, team_name))
                print(f"  [!] Could not find team: {team_name} (rank {rank})")
                continue

            default_ballot = DefaultBallot(
                poll_id=None,  # Global default
                week_key=None,
                rank=rank,
                team_id=team_id
            )
            session.add(default_ballot)
            inserted += 1

            # Get the actual team name from DB for confirmation
            team = session.get(Team, team_id)
            print(f"  ✓ Rank {rank:2d}: {team.name}")

        session.commit()

        print("\n" + "="*60)
        print("UPDATE COMPLETE!")
        print("="*60)
        print(f"\n✓ Inserted {inserted} rankings")

        if not_found:
            print(f"\n⚠ Warning: {len(not_found)} teams not found:")
            for rank, name in not_found:
                print(f"  • Rank {rank}: {name}")
            print("\nYou may need to add these teams to the database first.")
        else:
            print("\n✓ All teams matched successfully!")

        print()

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Update failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("\nThis will replace the current CFP default rankings.")
    print("The old rankings will be deleted and replaced with the new ones.\n")

    response = input("Continue? (yes/no): ")
    if response.lower() in ('yes', 'y'):
        run_update()
    else:
        print("Update cancelled.")
