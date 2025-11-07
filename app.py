# app.py
import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from dotenv import load_dotenv
load_dotenv()

from db import SessionLocal
from models import User
from auth import bp as auth_bp
from poll import bp as poll_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-override")

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id:str):
    with SessionLocal() as s:
        return s.get(User, int(user_id))

@app.route("/")
def root():
    if current_user.is_authenticated:
        return redirect(url_for("poll.dashboard"))
    return redirect(url_for("auth.login"))

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(poll_bp)


# ---------------- TEMP DIAGNOSTICS: remove after we stabilize ----------------
import os, sys
from flask import jsonify
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

# Hard-wire a minimal root so we never 404 while debugging
@app.get("/")
def root_health_only():
    return "app root reachable", 200
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    app.run(debug=True, port=5057)

