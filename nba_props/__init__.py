from flask import Blueprint
bp = Blueprint("nba_props", __name__, template_folder="../templates")
from . import routes  # noqa
