# app.py
import os
from datetime import datetime
from flask import Flask, redirect, url_for, jsonify
from flask_login import LoginManager, current_user
from dotenv import load_dotenv
load_dotenv()

from db import SessionLocal
from models import User
from auth import bp as auth_bp
from poll import bp as poll_bp
from spreads import bp as spreads_bp
from groups import bp as groups_bp
from admin import bp as admin_bp
from nba_props import bp as nba_props_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-override")

# ---- Flask-Login ----
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id: str):
    with SessionLocal() as s:
        return s.get(User, int(user_id))

# ---- Global template context (e.g., footer year, current_group) ----
@app.context_processor
def inject_globals():
    context = {
        "current_year": datetime.utcnow().year,
        "year": datetime.utcnow().year
    }

    # Inject current group and user groups for authenticated users
    if current_user.is_authenticated:
        from utils.group_helpers import get_current_group, get_user_groups
        with SessionLocal() as s:
            current_group = get_current_group(current_user, s)
            user_groups = get_user_groups(current_user.id, s)
            context["current_group"] = current_group
            context["user_groups"] = user_groups

    return context

# ---- Root: home page ----
@app.get("/")
def root():
    if current_user.is_authenticated:
        from flask import render_template
        return render_template("home.html")
    return redirect(url_for("auth.login"))

# ---- Blueprints ----
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(poll_bp)
app.register_blueprint(spreads_bp)
app.register_blueprint(groups_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(nba_props_bp, url_prefix="/nba-props")

# ---------------- TEMP DIAGNOSTICS: keep while stabilizing ----------------
from sqlalchemy import inspect
from sqlalchemy.exc import ProgrammingError, OperationalError

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/debug/routes")
def debug_routes():
    return jsonify(routes=sorted(str(r) for r in app.url_map.iter_rules()))

@app.get("/debug/files")
def debug_files():
    def safe_ls(path):
        try:
            return sorted(os.listdir(path))
        except Exception as e:
            return f"ERR: {e.__class__.__name__}: {e}"
    return jsonify(
        cwd=os.getcwd(),
        has_procfile=os.path.isfile("Procfile"),
        template_folder=app.template_folder,
        static_folder=app.static_folder,
        templates=safe_ls(app.template_folder),
        static=safe_ls(app.static_folder),
    )

@app.get("/debug/db")
def debug_db():
    try:
        from db import engine, SessionLocal
        from models import User
        insp = inspect(engine)
        with SessionLocal() as s:
            users = s.query(User).count()
        return jsonify(db=str(engine.url), tables=sorted(insp.get_table_names()), users=users)
    except Exception as e:
        return jsonify(error=f"{e.__class__.__name__}: {e}"), 500

@app.context_processor
def inject_year():
    return {"year": datetime.utcnow().year}
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False, port=5057)
