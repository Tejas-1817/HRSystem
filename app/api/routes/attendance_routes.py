from flask import Blueprint, jsonify
from app.api.middleware.auth import token_required
from app.models.database import execute_query

attendance_bp = Blueprint('attendance', __name__)

MIN_WORK_HOURS = 8.0


def _derive_attendance_rows(current_user):
    """
    Build attendance view from timesheet entries.
    Compatibility: retains legacy attendance keys consumed by older UI.
    """
    if current_user["role"] in ("manager", "hr"):
        rows = execute_query(
            """
            SELECT
                t.employee_name,
                DATE(t.start_date) AS date,
                ROUND(SUM(t.hours), 2) AS total_hours
            FROM timesheets t
            GROUP BY t.employee_name, DATE(t.start_date)
            ORDER BY DATE(t.start_date) DESC, t.employee_name
            """
        )
    else:
        rows = execute_query(
            """
            SELECT
                t.employee_name,
                DATE(t.start_date) AS date,
                ROUND(SUM(t.hours), 2) AS total_hours
            FROM timesheets t
            WHERE t.employee_name = %s
            GROUP BY t.employee_name, DATE(t.start_date)
            ORDER BY DATE(t.start_date) DESC, t.employee_name
            """,
            (current_user["employee_name"],),
        )

    derived = []
    for row in rows:
        total_worked_hours = float(row.get("total_hours") or 0.0)
        overtime_hours = round(max(0.0, total_worked_hours - MIN_WORK_HOURS), 2)
        underwork_hours = round(max(0.0, MIN_WORK_HOURS - total_worked_hours), 2)

        if total_worked_hours >= MIN_WORK_HOURS:
            work_status = "complete"
            status = "present"
            remarks = "Overtime" if total_worked_hours > MIN_WORK_HOURS else "Meets minimum hours"
        else:
            work_status = "incomplete"
            status = "present"
            remarks = "Below minimum hours"

        date_val = row.get("date")
        if hasattr(date_val, "isoformat"):
            date_val = date_val.isoformat()
        else:
            date_val = str(date_val)

        derived.append(
            {
                "employee_name": row.get("employee_name"),
                "date": date_val,
                "status": status,
                "clock_in": None,
                "clock_out": None,
                "break_minutes": 0,
                "total_worked_hours": total_worked_hours,
                "overtime_hours": overtime_hours,
                "underwork_hours": underwork_hours,
                "work_status": work_status,
                "remarks": remarks,
            }
        )

    return derived


@attendance_bp.route("/", methods=["GET"])
@token_required
def get_attendance(current_user):
    """
    Timesheet-derived attendance endpoint.
    Note: Clock-in/clock-out endpoints have been removed.
    """
    try:
        rows = _derive_attendance_rows(current_user)
        return jsonify({"success": True, "attendance": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
