from flask import Blueprint, request, jsonify
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required

notification_bp = Blueprint('notifications', __name__)

@notification_bp.route("/", methods=["GET"])
@token_required
def get_notifications(current_user):
    """Fetch all notifications for the logged-in employee."""
    try:
        rows = execute_query(
            "SELECT * FROM notifications WHERE employee_name = %s ORDER BY created_at DESC",
            (current_user["employee_name"],)
        )
        return jsonify({"success": True, "notifications": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@notification_bp.route("/<int:notif_id>/read", methods=["PUT"])
@token_required
def mark_as_read(current_user, notif_id):
    """Mark a specific notification as read."""
    try:
        # Check if notification exists and belongs to the user
        notif = execute_single(
            "SELECT * FROM notifications WHERE id = %s AND employee_name = %s",
            (notif_id, current_user["employee_name"])
        )
        if not notif:
            return jsonify({"success": False, "error": "Notification not found"}), 404

        execute_query(
            "UPDATE notifications SET is_read = TRUE WHERE id = %s",
            (notif_id,),
            commit=True
        )
        return jsonify({"success": True, "message": "Notification marked as read"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@notification_bp.route("/<int:notif_id>", methods=["DELETE"])
@token_required
def delete_notification(current_user, notif_id):
    """Delete a specific notification."""
    try:
        # Check if notification exists and belongs to the user
        notif = execute_single(
            "SELECT * FROM notifications WHERE id = %s AND employee_name = %s",
            (notif_id, current_user["employee_name"])
        )
        if not notif:
            return jsonify({"success": False, "error": "Notification not found"}), 404

        execute_query(
            "DELETE FROM notifications WHERE id = %s",
            (notif_id,),
            commit=True
        )
        return jsonify({"success": True, "message": "Notification deleted"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
