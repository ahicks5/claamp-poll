# create_admin.py
import os
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from db import SessionLocal
from models import User

def main():
    username = 'ahicks5'
    email = 'arhicks14@yahoo.com'
    password = 'ihateAndrew0!'

    if not (username and email and password):
        raise SystemExit("Missing one or more of: ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD")

    pw_hash = generate_password_hash(password)

    with SessionLocal() as s:
        # Try find by username or email
        existing = s.execute(
            select(User).where((User.username == username) | (User.email == email))
        ).scalars().first()

        if existing:
            # Promote to admin and (optionally) reset password
            existing.is_admin = True
            existing.pw_hash = pw_hash
            s.add(existing)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise
            print(f"✅ Updated existing user '{existing.username}' as admin.")
        else:
            # Create new admin
            u = User(username=username, email=email, pw_hash=pw_hash, is_admin=True)
            s.add(u)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise
            print(f"✅ Created admin user '{username}'.")

if __name__ == "__main__":
    main()
