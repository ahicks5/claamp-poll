# seed.py
import os
from db import SessionLocal
from models import User, Team
from werkzeug.security import generate_password_hash

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "ahicks5")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "arhicks14@yahoo.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ihateAndrew0!")

default_teams = [
    "Georgia","Ohio State","Michigan","Texas","Alabama","Oregon","Notre Dame","Washington",
    "Florida State","Penn State","Ole Miss","LSU","Tennessee","Oklahoma","Utah",
    "Kansas State","Missouri","Clemson","Arizona","Louisville","Iowa",
    "North Carolina","USC","Miami (FL)","Liberty"
]

with SessionLocal() as s:
    # Create admin if not exists
    user = s.query(User).filter_by(username=ADMIN_USERNAME).first()
    if not user:
        print("👑 Creating admin user...")
        user = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            pw_hash=generate_password_hash(ADMIN_PASSWORD),
            is_admin=True
        )
        s.add(user)

    # Seed teams if empty
    if s.query(Team).count() == 0:
        print("🏈 Seeding team list...")
        for name in default_teams:
            s.add(Team(name=name))

    s.commit()

print("✅ Seed complete (admin + teams).")
