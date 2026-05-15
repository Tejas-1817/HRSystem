from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from app.config import Config
import os
import logging

logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    CORS(app)
    
    # Load configuration
    app.config.from_object(Config)

    # Max upload size (10 MB) — enforced globally by Flask/Werkzeug
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

    # Setup logging
    from app.utils.logger import setup_logger
    setup_logger()

    # ── GLOBAL ERROR HANDLERS (Production-Safe) ──────────────────────────
    @app.errorhandler(500)
    def handle_500_error(error):
        """Catch unhandled exceptions and return safe error response without stack trace."""
        logger.error(f"500 Error: {error}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please contact support."
        }), 500

    @app.errorhandler(404)
    def handle_404_error(error):
        """Catch 404 errors."""
        return jsonify({
            "success": False,
            "error": "Not found",
            "message": "The requested resource does not exist."
        }), 404

    @app.errorhandler(403)
    def handle_403_error(error):
        """Catch 403 errors."""
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "You do not have permission to access this resource."
        }), 403

    @app.errorhandler(400)
    def handle_400_error(error):
        """Catch 400 errors."""
        return jsonify({
            "success": False,
            "error": "Bad request",
            "message": "The request contains invalid data."
        }), 400

    # Register Blueprints
    from app.api.routes.auth_routes import auth_bp
    from app.api.routes.employee_routes import employee_bp
    from app.api.routes.team_member_routes import team_member_bp
    from app.api.routes.attendance_routes import attendance_bp
    from app.api.routes.project_routes import project_bp
    from app.api.routes.timesheet_routes import timesheet_bp
    from app.api.routes.leave_routes import leave_bp
    from app.api.routes.document_routes import document_bp
    from app.api.routes.report_routes import report_bp
    from app.api.routes.birthday_routes import birthday_bp
    from app.api.routes.holiday_routes import holiday_bp
    from app.api.routes.notification_routes import notification_bp
    from app.api.routes.bank_routes import bank_bp
    from app.api.routes.helpdesk_routes import helpdesk_bp
    from app.api.routes.reimbursement_routes import reimbursement_bp
    from app.api.routes.device_routes import device_bp
    from app.api.routes.profile_routes import profile_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(employee_bp, url_prefix='/employees')
    app.register_blueprint(team_member_bp)  # Registered with /api/v1/team-members prefix
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(project_bp, url_prefix='/projects')
    app.register_blueprint(timesheet_bp, url_prefix='/timesheets')
    app.register_blueprint(leave_bp, url_prefix='/leaves')
    app.register_blueprint(document_bp, url_prefix='/documents')
    app.register_blueprint(report_bp, url_prefix='/reports')
    app.register_blueprint(birthday_bp, url_prefix='/birthdays')
    app.register_blueprint(holiday_bp, url_prefix='/holidays')
    app.register_blueprint(notification_bp, url_prefix='/notifications')
    app.register_blueprint(bank_bp, url_prefix='/bank')
    app.register_blueprint(helpdesk_bp, url_prefix='/helpdesk')
    app.register_blueprint(reimbursement_bp, url_prefix='/reimbursements')
    app.register_blueprint(device_bp, url_prefix='/devices')
    app.register_blueprint(profile_bp)  # /profile/<employee_name> — team member profile pages

    @app.after_request
    def add_security_headers(response):
        """Prevent browser caching of sensitive API data for security."""
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # ── Static file serving for uploads (photos, receipts, docs) ──────────
    uploads_dir = os.path.join(os.getcwd(), Config.UPLOAD_FOLDER)

    @app.route("/uploads/<path:filepath>")
    def serve_upload(filepath):
        """
        Serve files from the uploads directory.
        URL pattern:  /uploads/photos/<uuid>.jpg
        """
        return send_from_directory(uploads_dir, filepath)

    @app.route("/")
    def home():
        return {"success": True, "message": "Welcome to the Modular HR Management API"}

    return app

