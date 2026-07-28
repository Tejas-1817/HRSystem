from flask import Blueprint

offboarding_bp = Blueprint('offboarding', __name__)

from app.offboarding import routes
