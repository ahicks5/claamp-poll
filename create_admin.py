# scripts/logo_audit.py
import os
from pathlib import Path
from sqlalchemy import select

# Local imports from your app
from db import SessionLocal
from models import Team
from utils.logo_map import logo_map

LOGO_DIR = Path("static/logos")

def main():
    missing_map = []        # teams not found in logo_map
    missing_file = []       # teams mapped, but file not present on slug
    ok = []                 # mapped & found

    with SessionLocal() as s:
        teams = s.execute(select(Team)).scalars().all()

    for t in teams:
        fname = logo_map.get(t.name)
        if not fname:
            missing_map.append(t.name)
            continue

        path = LOGO_DIR / fname
        if not path.exists():
            missing_file.append((t.name, fname))
        else:
            ok.append((t.name, fname))

    print("=== LOGO AUDIT ===")
    print(f"Logo directory: {LOGO_DIR.resolve()}")
    print(f"✅ Logos OK: {len(ok)}")
    print(f"❌ No logo_map entry: {len(missing_map)}")
    for name in missing_map[:50]:
        print(f"   - {name}")
    if len(missing_map) > 50:
        print(f"   ...and {len(missing_map) - 50} more")

    print(f"❌ File missing on slug: {len(missing_file)}")
    for name, fname in missing_file[:50]:
        print(f"   - {name} -> {fname} (not found under {LOGO_DIR})")
    if len(missing_file) > 50:
        print(f"   ...and {len(missing_file) - 50} more")

    # Exit code for CI or quick sanity
    if missing_map or missing_file:
        raise SystemExit(1)
    else:
        print("All good. 🎉")

if __name__ == "__main__":
    main()
