from flask import Blueprint, jsonify
from app.models.database import execute_query
from app.api.middleware.auth import token_required

birthday_bp = Blueprint('birthdays', __name__)

def _serialize_birthdays(rows):
    if not rows:
        return []
    items = rows if isinstance(rows, list) else [rows]
    for item in items:
        if isinstance(item, dict):
            for k, v in list(item.items()):
                if v is not None and not isinstance(v, (str, int, float, bool, list, dict)):
                    item[k] = str(v)
    return items

@birthday_bp.route("", methods=["GET"])
@birthday_bp.route("/", methods=["GET"])
@birthday_bp.route("/all", methods=["GET"])
@token_required
def get_all_birthdays(current_user):
    """Fetch all team members' public birthday info for organization widgets."""
    try:
        query = """
            SELECT e.id, e.name, e.date_of_birth, e.photo, e.designation, e.department, u.role
            FROM employee e
            LEFT JOIN users u ON e.name = u.employee_name
            WHERE e.date_of_birth IS NOT NULL
        """
        rows = execute_query(query) or []
        serialized = _serialize_birthdays(rows)
        return jsonify({
            "success": True,
            "count": len(serialized),
            "birthdays": serialized,
            "data": serialized
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@birthday_bp.route("/today", methods=["GET"])
@token_required
def get_todays_birthdays(current_user):
    """Fetch employees whose birthday is today."""
    try:
        # MySQL query to find birthdays matching month and day of current date
        query = """
            SELECT id, name, date_of_birth, photo
            FROM employee
            WHERE MONTH(date_of_birth) = MONTH(CURDATE())
              AND DAY(date_of_birth) = DAY(CURDATE())
        """
        rows = execute_query(query) or []
        serialized = _serialize_birthdays(rows)
        return jsonify({
            "success": True, 
            "count": len(serialized),
            "birthdays": serialized,
            "message": f"{len(serialized)} birthday(s) today!" if serialized else "No birthdays today."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@birthday_bp.route("/upcoming", methods=["GET"])
@token_required
def get_upcoming_birthdays(current_user):
    """Fetch employees whose birthday is in the next 7 days."""
    try:
        # Complex MySQL query to calculate days until next birthday, handling year rollover
        query = """
            SELECT id, name, date_of_birth, photo,
                   DATEDIFF(
                       STR_TO_DATE(CONCAT(YEAR(CURDATE()), '-', MONTH(date_of_birth), '-', DAY(date_of_birth)), '%Y-%m-%d') + 
                       INTERVAL (STR_TO_DATE(CONCAT(YEAR(CURDATE()), '-', MONTH(date_of_birth), '-', DAY(date_of_birth)), '%Y-%m-%d') < CURDATE()) YEAR,
                       CURDATE()
                   ) AS days_until_birthday
            FROM employee
            HAVING days_until_birthday BETWEEN 1 AND 7
            ORDER BY days_until_birthday ASC
        """
        rows = execute_query(query) or []
        serialized = _serialize_birthdays(rows)
        return jsonify({
            "success": True, 
            "count": len(serialized),
            "upcoming_birthdays": serialized
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
