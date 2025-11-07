# scripts/normalize_team_names.py

from sqlalchemy import select
from db import SessionLocal
from models import Team

from utils.logo_map import logo_map  # your 134-map

MASTER_TEAM_NAMES = list(logo_map.keys())

def run():
    with SessionLocal() as s:
        teams = s.execute(select(Team)).scalars().all()

        print("Current DB teams:")
        for t in teams:
            print(" -", t.name)

        # Step 1: For every current team, if it’s not in master list, warn
        db_names = {t.name for t in teams}

        missing = db_names - set(MASTER_TEAM_NAMES)
        extra = set(MASTER_TEAM_NAMES) - db_names

        print("\nTeams in DB but NOT in master list:")
        for n in sorted(missing):
            print("  •", n)

        print("\nTeams in master list but NOT in DB:")
        for n in sorted(extra):
            print("  •", n)

        # Step 2: blow away DB names and replace with master list
        print("\nUpdating DB to canonical team list...")

        # Clear all existing rows
        for t in teams:
            s.delete(t)
        s.commit()

        # Re-insert fresh unified list
        for name in MASTER_TEAM_NAMES:
            s.add(Team(name=name))

        s.commit()
        print("\n✅ Done. DB now has the exact 134 canonical names.")

if __name__ == "__main__":
    run()
