from flask import Blueprint
bp = Blueprint("poll", __name__, url_prefix="/poll", template_folder="../templates")
from . import routes  # noqa

