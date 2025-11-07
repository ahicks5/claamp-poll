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

if __name__ == "__main__":
    app.run(debug=True, port=5057)

