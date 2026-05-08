from flask import Blueprint, request, jsonify
from app.models.database import execute_query
from app.api.middleware.auth import token_required, role_required

holiday_bp = Blueprint('holidays', __name__)

@holiday_bp.route("/", methods=["GET"])
@token_required
def get_holidays(current_user):
    """Fetch all holidays, with optional filtering by type."""
    try:
        holiday_type = request.args.get("type")
        if holiday_type:
            rows = execute_query("SELECT * FROM holidays WHERE type=%s ORDER BY date", (holiday_type,))
        else:
            rows = execute_query("SELECT * FROM holidays ORDER BY date")
            
        return jsonify({
            "success": True, 
            "count": len(rows),
            "holidays": rows
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@holiday_bp.route("/", methods=["POST"])
@role_required(["hr"])
def add_holiday(current_user):
    """Add a new holiday (HR only)."""
    try:
        data = request.get_json()
        required = ("name", "date")
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": "Missing name or date"}), 400
            
        holiday_type = data.get("type", "public")
        execute_query("""
            INSERT INTO holidays (name, date, type, description)
            VALUES (%s, %s, %s, %s)
        """, (data["name"], data["date"], holiday_type, data.get("description")), commit=True)
        
        return jsonify({"success": True, "message": "Holiday added successfully"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@holiday_bp.route("/dashboard", methods=["GET"])
@token_required
def holiday_dashboard(current_user):
    """Returns today's holiday and upcoming holidays (next 30 days)."""
    try:
        # Today's holiday(s)
        today_holidays = execute_query("""
            SELECT * FROM holidays 
            WHERE MONTH(date) = MONTH(CURDATE()) AND DAY(date) = DAY(CURDATE())
        """)
        
        # Upcoming holidays (next 30 days)
        upcoming = execute_query("""
            SELECT *, DATEDIFF(date, CURDATE()) AS days_away
            FROM holidays
            WHERE date > CURDATE() AND date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
            ORDER BY date ASC
        """)
        
        return jsonify({
            "success": True,
            "today": {
                "count": len(today_holidays),
                "holidays": today_holidays,
                "message": f"🎉 Today is {today_holidays[0]['name']}!" if today_holidays else "No holiday today."
            },
            "upcoming_holidays": upcoming
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
