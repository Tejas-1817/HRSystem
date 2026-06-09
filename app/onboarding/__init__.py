from flask import Blueprint

onboarding_bp = Blueprint('onboarding', __name__)

from app.onboarding import routes
