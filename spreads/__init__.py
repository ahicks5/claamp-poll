from flask import Blueprint
bp = Blueprint("spreads", __name__, url_prefix="/spreads", template_folder="../templates")
from . import routes  # noqa
