# app.py
"""
TakeFreePoints.com - Data-driven sports betting
Main Flask application
"""
import os
from datetime import datetime
from flask import Flask, redirect, url_for, jsonify, render_template
from flask_login import LoginManager, current_user
from dotenv import load_dotenv
load_dotenv()

from db import SessionLocal
from models import User

# Import blueprints
from auth import bp as auth_bp
from dashboard.routes import bp as dashboard_bp
from nba_props import bp as nba_props_bp

# Create Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-override")

# ============================================================
# FLASK-LOGIN SETUP
# ============================================================

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id: str):
    """Load user from database for Flask-Login"""
    with SessionLocal() as s:
        return s.get(User, int(user_id))


# ============================================================
# GLOBAL TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    return {
        "current_year": datetime.utcnow().year,
        "year": datetime.utcnow().year,
        "site_name": "TakeFreePoints.com"
    }


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def root():
    """Homepage - public landing page or dashboard if logged in"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    # Public landing page
    return render_template("home.html")


@app.get("/about")
def about():
    """About page - explain the strategy"""
    return render_template("about.html")


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
app.register_blueprint(nba_props_bp, url_prefix="/nba-props")


# ============================================================
# DIAGNOSTICS & DEBUG ROUTES
# ============================================================

@app.get("/healthz")
def healthz():
    """Health check endpoint"""
    return "ok", 200


@app.get("/debug/routes")
def debug_routes():
    """List all registered routes"""
    return jsonify(routes=sorted(str(r) for r in app.url_map.iter_rules()))


@app.get("/debug/db")
def debug_db():
    """Database diagnostics"""
    try:
        from db import engine, SessionLocal
        from models import User, Strategy, BetJournal
        from sqlalchemy import inspect

        insp = inspect(engine)
        with SessionLocal() as s:
            users = s.query(User).count()
            strategies = s.query(Strategy).count()
            bets = s.query(BetJournal).count()

        return jsonify(
            db=str(engine.url),
            tables=sorted(insp.get_table_names()),
            users=users,
            strategies=strategies,
            bets=bets
        )
    except Exception as e:
        return jsonify(error=f"{e.__class__.__name__}: {e}"), 500


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    app.run(debug=True, port=5057)
