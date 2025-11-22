"""
Run once on Heroku:
  heroku run python seed_committee_default.py --app <your-app-name>

This upserts the committee's default 1..25 for a given poll_id + week_key.
"""

import sys
from sqlalchemy import select, delete
from db import SessionLocal
from models import Team, DefaultBallot  # adjust import paths if needed

# ==== CONFIG ====
POLL_ID  = None   # or set the integer poll_id if you want poll-specific defaults
WEEK_KEY = "2025-11-07"  # something you’ll bump weekly

# Committee list: (rank, exact team name used in your DB)
RAW = [
    (1,  "Ohio State"),
    (2,  "Indiana"),
    (3,  "Texas A&M"),
    (4,  "Alabama"),
    (5,  "Georgia"),
    (6,  "Ole Miss"),
    (7,  "BYU"),
    (8,  "Texas Tech"),
    (9,  "Oregon"),
    (10, "Notre Dame"),
    (11, "Texas"),
    (12, "Oklahoma"),
    (13, "Utah"),
    (14, "Virginia"),
    (15, "Louisville"),
    (16, "Vanderbilt"),
    (17, "Georgia Tech"),
    (18, "Miami (FL)"),       # choose one that matches your Teams table
    (19, "USC"),              # your DB likely uses "USC" not "Southern California"
    (20, "Iowa"),
    (21, "Michigan"),
    (22, "Missouri"),
    (23, "Washington"),
    (24, "Pitt"),             # if your DB uses "Pitt"; otherwise "Pittsburgh"
    (25, "Tennessee"),
]

# Optional alias resolver if committee names differ from your Team.name:
ALIASES = {
    "Southern California": "USC",
    "Miami": "Miami (FL)",   # adjust if you ever mean (OH)
    "Pittsburgh": "Pitt",
}

def resolve_name(name: str) -> str:
    return ALIASES.get(name, name)

def main():
    s = SessionLocal()

    # Clear existing for this (poll_id, week_key)
    s.execute(
        delete(DefaultBallot).where(
            DefaultBallot.poll_id.is_(POLL_ID) if POLL_ID is None else DefaultBallot.poll_id == POLL_ID,
            DefaultBallot.week_key == WEEK_KEY
        )
    )
    s.commit()

    # Build lookup of Team by name
    teams = {t.name: t for t in s.scalars(select(Team)).all()}

    missing = []
    to_add = []
    for rank, raw_name in RAW:
        name = resolve_name(raw_name)
        team = teams.get(name)
        if not team:
            missing.append((rank, raw_name))
            continue
        to_add.append(DefaultBallot(
            poll_id=POLL_ID,
            week_key=WEEK_KEY,
            rank=rank,
            team_id=team.id
        ))

    if missing:
        print("WARNING: Some names did not match your Teams table:")
        for r, n in missing:
            print(f"  rank {r}: {n}")
        print("Fix ALIASES or insert the Teams, then re-run.")
        sys.exit(1)

    s.add_all(to_add)
    s.commit()
    print(f"Inserted {len(to_add)} defaults for week_key={WEEK_KEY}, poll_id={POLL_ID}")

if __name__ == "__main__":
    main()
