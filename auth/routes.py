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
        with SessionLocal() as s:
            if s.execute(select(User).where((User.username==username)|(User.email==email))).first():
                flash("Username or email already exists.", "warning")
                return redirect(url_for("auth.register"))
            user = User(username=username, email=email, pw_hash=generate_password_hash(password))
            s.add(user); s.commit()
        flash("Registered. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth_register.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

