from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import select
from datetime import datetime, timezone

from db import SessionLocal
from models import User
from . import bp

@bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        with SessionLocal() as s:
            user = s.execute(select(User).where(User.username==username)).scalars().first()
            if user and check_password_hash(user.pw_hash, password):
                login_user(user)
                user.last_login_at = datetime.now(timezone.utc)
                s.commit()
                return redirect(url_for("poll.dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("auth_login.html")

@bp.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        password_confirm = request.form.get("password_confirm","")

        # Validation
        if not username or len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
            return render_template("auth_register.html", username=username, email=email)

        if not email or "@" not in email:
            flash("Please enter a valid email address.", "danger")
            return render_template("auth_register.html", username=username, email=email)

        if not password or len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("auth_register.html", username=username, email=email)

        if password != password_confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth_register.html", username=username, email=email)

        with SessionLocal() as s:
            if s.execute(select(User).where((User.username==username)|(User.email==email))).first():
                flash("Username or email already exists.", "warning")
                return render_template("auth_register.html", username=username, email=email)
            user = User(username=username, email=email, pw_hash=generate_password_hash(password))
            s.add(user); s.commit()
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth_register.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

