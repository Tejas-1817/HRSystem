from flask import Blueprint, request, jsonify
from decimal import Decimal
from datetime import datetime, date, timedelta
import calendar

from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required
from app.services.leave_service import (
    get_employee_balance,
    get_leave_config,
    allocate_default_leaves,
    deduct_leave_balance,
    refund_leave_balance,
    validate_half_day_conflict,
    calculate_leave_duration,
)

leave_bp = Blueprint('leaves', __name__)

LEAVE_CALENDAR_LABELS = {
    "leave":      "On Leave",
    "half_day":   "Half Day Leave",
    "weekend":    "Weekend",
    "holiday":    "Holiday",
    "future":     "Future Date",
    "available":  "Working Day",
}

VALID_HALF_DAY_PERIODS = {"first_half", "second_half"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_leave(row: dict) -> dict:
    """Ensure date/Decimal fields are JSON-serialisable."""
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            row[k] = v.isoformat()
        elif isinstance(v, Decimal):
            row[k] = float(v)
    return row


def _get_stored_duration(leave: dict) -> Decimal:
    """
    Read the pre-calculated leave_duration from a leave record.
    Falls back to counting working days for legacy records that pre-date the
    half-day feature (leave_duration will be DEFAULT 1.00 per the migration).
    """
    stored = leave.get("leave_duration")
    if stored is not None:
        return Decimal(str(stored))
    # Legacy fallback: count Mon–Fri days
    sd = leave["start_date"] if isinstance(leave["start_date"], date) else date.fromisoformat(str(leave["start_date"]))
    ed = leave["end_date"]   if isinstance(leave["end_date"],   date) else date.fromisoformat(str(leave["end_date"]))
    from app.utils.helpers import get_working_days_count
    return Decimal(str(get_working_days_count(sd, ed)))


# ---------------------------------------------------------------------------
# GET /leaves/ — list leave applications
# ---------------------------------------------------------------------------

@leave_bp.route("/", methods=["GET"])
@token_required
def view_leaves(current_user):
    try:
        if current_user["role"] in ("manager", "hr"):
            rows = execute_query("""
                SELECT id, employee_name, leave_type, leave_type_category,
                       half_day_period, leave_duration, start_date, end_date,
                       reason, status, applied_at
                FROM leaves ORDER BY applied_at DESC
            """)
        else:
            rows = execute_query("""
                SELECT id, employee_name, leave_type, leave_type_category,
                       half_day_period, leave_duration, start_date, end_date,
                       reason, status, applied_at
                FROM leaves
                WHERE employee_name = %s ORDER BY applied_at DESC
            """, (current_user["employee_name"],))

        rows = [_serialize_leave(r) for r in rows]
        return jsonify({"success": True, "leaves": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /leaves/balance/<name> — get a specific employee's leave balance
# ---------------------------------------------------------------------------

@leave_bp.route("/balance/<string:name>", methods=["GET"])
@token_required
def get_leave_balance_api(current_user, name):
    try:
        if current_user["role"] == "employee" and current_user["employee_name"] != name:
            return jsonify({"success": False, "error": "Access denied"}), 403

        balances = get_employee_balance(name)
        total_remaining = sum(b["remaining_leaves"] for b in balances) if balances else 0

        for b in balances:
            b["totalLeaves"]     = b["total_leaves"]
            b["usedLeaves"]      = b["used_leaves"]
            b["remainingLeaves"] = b["remaining_leaves"]

        return jsonify({
            "success": True,
            "balances": balances,
            "summary": {
                "remaining_leaves": total_remaining,
                "remainingLeaves": total_remaining,
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /leaves/balance — employee views own leave balance summary
# ---------------------------------------------------------------------------

@leave_bp.route("/balance", methods=["GET"])
@token_required
def view_leave_balance(current_user):
    """
    Returns the employee's leave balance across all leave types.
    Supports half-day (decimal) values.
    """
    try:
        if current_user["role"] in ("hr", "manager") and request.args.get("employee_name"):
            emp_name = request.args.get("employee_name")
        else:
            emp_name = current_user["employee_name"]

        balance = get_employee_balance(emp_name)

        if not balance:
            allocate_default_leaves(emp_name)
            balance = get_employee_balance(emp_name)

        total     = sum(b.get("total_leaves",     0) for b in balance)
        used      = sum(b.get("used_leaves",      0) for b in balance)
        remaining = sum(b.get("remaining_leaves", 0) for b in balance)

        for b in balance:
            b["totalLeaves"]     = b["total_leaves"]
            b["usedLeaves"]      = b["used_leaves"]
            b["remainingLeaves"] = b["remaining_leaves"]

        return jsonify({
            "success": True,
            "employee_name": emp_name,
            "balance": balance,
            "total_summary": {
                "total": total,     "used": used,     "remaining": remaining,
                "total_leaves": total, "used_leaves": used, "remaining_leaves": remaining,
                "totalLeaves": total,  "usedLeaves": used,  "remainingLeaves": remaining,
            },
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /leaves/balance/all — HR views all employees' leave balances
# ---------------------------------------------------------------------------

@leave_bp.route("/balance/all", methods=["GET"])
@role_required(["hr", "manager"])
def view_all_leave_balances(current_user):
    """HR-only: returns leave balances for every employee, grouped by name."""
    try:
        rows = execute_query("""
            SELECT employee_name, leave_type,
                   CAST(total_leaves AS FLOAT) AS total_leaves,
                   CAST(used_leaves  AS FLOAT) AS used_leaves,
                   CAST(total_leaves - used_leaves AS FLOAT) AS remaining_leaves
            FROM leave_balance
            ORDER BY employee_name, leave_type
        """)

        grouped = {}
        for r in rows:
            name = r["employee_name"]
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(r)

        return jsonify({"success": True, "balances": grouped, "total_employees": len(grouped)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /leaves/config — view leave type configuration
# ---------------------------------------------------------------------------

@leave_bp.route("/config", methods=["GET"])
@token_required
def view_leave_config(current_user):
    """Returns the current leave type defaults (quotas)."""
    try:
        config = get_leave_config()
        return jsonify({"success": True, "leave_types": config}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /leaves/currently-on-leave — who is on leave today
# ---------------------------------------------------------------------------

@leave_bp.route("/currently-on-leave", methods=["GET"])
@role_required(["manager", "hr"])
def get_currently_on_leave(current_user):
    try:
        rows = execute_query("""
            SELECT id, employee_name, leave_type, leave_type_category,
                   half_day_period, leave_duration, start_date, end_date,
                   reason, status
            FROM leaves
            WHERE status = 'approved'
              AND CURDATE() BETWEEN start_date AND end_date
            ORDER BY employee_name
        """)
        rows = [_serialize_leave(r) for r in rows]
        return jsonify({"success": True, "on_leave_today": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /leaves/calendar — leave calendar with half-day support
# ---------------------------------------------------------------------------

@leave_bp.route("/calendar", methods=["GET"])
@token_required
def leave_calendar(current_user):
    """
    Returns month view data for the leave calendar.
    New: half-day leaves produce `status: 'half_day'` with `half_day_period`.
    A day that has only one half-day leave retains `can_apply_second_half: True`
    so the employee knows they can still apply for the other half.
    """
    try:
        today = date.today()
        try:
            year  = int(request.args.get("year",  today.year))
            month = int(request.args.get("month", today.month))
        except ValueError:
            return jsonify({"success": False, "error": "Invalid year or month"}), 400

        if not (1 <= month <= 12):
            return jsonify({"success": False, "error": "Month must be 1-12"}), 400

        if current_user["role"] in ("hr", "manager") and request.args.get("employee_name"):
            employee_name = request.args.get("employee_name")
        else:
            employee_name = current_user["employee_name"]

        _, days_in_month = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end   = date(year, month, days_in_month)

        # Fetch all approved/pending leaves for this employee in this month
        leave_rows = execute_query("""
            SELECT start_date, end_date, leave_type, leave_type_category,
                   half_day_period, leave_duration, status
            FROM leaves
            WHERE employee_name = %s
              AND status IN ('approved', 'pending')
              AND start_date <= %s
              AND end_date   >= %s
        """, (employee_name, month_end.isoformat(), month_start.isoformat()))

        # Build per-date leave metadata index
        # Structure: { "YYYY-MM-DD": { "full_day": bool, "half_days": ["first_half"/"second_half"...], "status": "approved"/"pending" } }
        leave_index: dict[str, dict] = {}

        for row in leave_rows:
            sd = row["start_date"] if isinstance(row["start_date"], date) else date.fromisoformat(str(row["start_date"]))
            ed = row["end_date"]   if isinstance(row["end_date"],   date) else date.fromisoformat(str(row["end_date"]))
            cat = row.get("leave_type_category", "full_day") or "full_day"
            period = row.get("half_day_period")
            cur = sd

            while cur <= ed:
                if month_start <= cur <= month_end:
                    d_str = cur.isoformat()
                    if d_str not in leave_index:
                        leave_index[d_str] = {"full_day": False, "half_days": [], "leave_type": row["leave_type"]}

                    if cat == "half_day" and period:
                        if period not in leave_index[d_str]["half_days"]:
                            leave_index[d_str]["half_days"].append(period)
                    else:
                        leave_index[d_str]["full_day"] = True

                cur += timedelta(days=1)

        # Fetch holidays
        holiday_rows = execute_query("""
            SELECT name, date, type, description FROM holidays
            WHERE YEAR(date) = %s AND MONTH(date) = %s
        """, (year, month))

        holiday_by_date = {}
        for h in holiday_rows:
            key = h["date"].isoformat() if hasattr(h["date"], "isoformat") else str(h["date"])
            holiday_by_date[key] = {
                "holiday_name": h["name"],
                "type":         h["type"],
                "description":  h.get("description"),
            }

        days_payload = {}
        summary = {"leave": 0, "half_day": 0, "weekend": 0, "holiday": 0, "future": 0, "available": 0}

        for day in range(1, days_in_month + 1):
            d     = date(year, month, day)
            d_str = d.isoformat()
            is_weekend = d.weekday() >= 5
            is_holiday = d_str in holiday_by_date
            is_future  = d > today
            leave_info = leave_index.get(d_str)

            # Determine day status
            if is_holiday:
                status = "holiday"
            elif leave_info and leave_info["full_day"]:
                status = "leave"
            elif leave_info and leave_info["half_days"]:
                # Has half-day leave(s) — it's a partial leave day
                status = "half_day"
            elif is_weekend:
                status = "weekend"
            elif is_future:
                status = "future"
            else:
                status = "available"

            summary[status] = summary.get(status, 0) + 1

            # Determine if a second half-day can still be applied
            applied_halves = leave_info["half_days"] if leave_info else []
            can_apply_second_half = (
                status not in ("holiday", "leave", "weekend", "future")
                and len(applied_halves) < 2
            )

            days_payload[d_str] = {
                "status":                 status,
                "label":                  LEAVE_CALENDAR_LABELS.get(status, status.title()),
                "is_weekend":             is_weekend,
                "holiday":                holiday_by_date.get(d_str),
                "half_day_period":        applied_halves[0] if len(applied_halves) == 1 else None,
                "half_days_applied":      applied_halves,
                "can_apply_second_half":  can_apply_second_half,
            }

        return jsonify({
            "success":       True,
            "employee_name": employee_name,
            "year":          year,
            "month":         month,
            "days":          days_payload,
            "summary":       summary,
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /leaves/ — apply for leave (full-day or half-day)
# ---------------------------------------------------------------------------

@leave_bp.route("/", methods=["POST"])
@token_required
def apply_leave(current_user):
    """
    Apply for a leave. Supports full-day and half-day.

    Payload:
    {
      "leave_type": "sick",
      "start_date": "2026-04-25",
      "end_date":   "2026-04-25",
      "reason":     "Doctor visit",
      "leave_type_category": "half_day",    // "full_day" (default) | "half_day"
      "half_day_period": "first_half"       // required when half_day: "first_half" | "second_half"
    }
    """
    try:
        data = request.get_json() or {}
        required = ("leave_type", "start_date", "end_date")
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": "Missing required fields: leave_type, start_date, end_date"}), 400

        # RBAC: employees apply for themselves only
        if current_user["role"] == "employee":
            employee_name = current_user["employee_name"]
        else:
            employee_name = data.get("employee_name", current_user["employee_name"])

        leave_type          = data["leave_type"]
        start_date          = data["start_date"]
        end_date            = data["end_date"]
        leave_type_category = data.get("leave_type_category", "full_day")
        half_day_period     = data.get("half_day_period")       # None for full-day

        # ── Parse dates ───────────────────────────────────────────────────
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt   = datetime.strptime(end_date,   "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400

        if start_dt > end_dt:
            return jsonify({"success": False, "error": "start_date cannot be after end_date."}), 400

        # ── Validate category ─────────────────────────────────────────────
        if leave_type_category not in ("full_day", "half_day"):
            return jsonify({"success": False, "error": "leave_type_category must be 'full_day' or 'half_day'."}), 400

        # ── Half-day specific validations ─────────────────────────────────
        if leave_type_category == "half_day":
            # Must be a single day
            if start_dt != end_dt:
                return jsonify({
                    "success": False,
                    "error": "Half-day leave must be applied for a single date (start_date must equal end_date)."
                }), 400

            # period is required
            if half_day_period not in VALID_HALF_DAY_PERIODS:
                return jsonify({
                    "success": False,
                    "error": "half_day_period is required for half-day leave. Use 'first_half' or 'second_half'."
                }), 400

            # Cannot apply on a weekend
            if start_dt.weekday() >= 5:
                return jsonify({"success": False, "error": "Half-day leave cannot be applied on weekends."}), 400

            # Check holiday
            holiday_check = execute_single(
                "SELECT id FROM holidays WHERE date = %s", (start_date,)
            )
            if holiday_check:
                return jsonify({"success": False, "error": "Cannot apply leave on a public holiday."}), 400

            # Conflict validation (overlapping half-days / full-day on same date)
            conflict = validate_half_day_conflict(employee_name, start_dt, half_day_period)
            if not conflict["ok"]:
                return jsonify({"success": False, "error": conflict["error"]}), 409

        else:
            # ── Full-day validations ──────────────────────────────────────
            # Block if either boundary falls on a weekend
            if start_dt.weekday() >= 5 or end_dt.weekday() >= 5:
                return jsonify({
                    "success": False,
                    "error": "Leave cannot be applied on weekends as they are non-working days."
                }), 400

            # Check for overlapping leave (approved or pending)
            overlap = execute_single("""
                SELECT id FROM leaves
                WHERE employee_name = %s
                  AND status IN ('approved', 'pending')
                  AND start_date <= %s AND end_date >= %s
                LIMIT 1
            """, (employee_name, end_date, start_date))
            if overlap:
                return jsonify({
                    "success": False,
                    "error": "An existing leave application overlaps with the selected date range."
                }), 409

        # ── Calculate duration ────────────────────────────────────────────
        duration = calculate_leave_duration(leave_type_category, start_dt, end_dt)

        if duration == 0:
            return jsonify({
                "success": False,
                "error": "Selected range contains only weekends or holidays. Please select valid working days."
            }), 400

        # ── Balance check ─────────────────────────────────────────────────
        balance = execute_single("""
            SELECT total_leaves, used_leaves,
                   (total_leaves - used_leaves) AS remaining
            FROM leave_balance
            WHERE employee_name = %s AND leave_type = %s
        """, (employee_name, leave_type))

        if not balance:
            allocate_default_leaves(employee_name)
            balance = execute_single("""
                SELECT total_leaves, used_leaves,
                       (total_leaves - used_leaves) AS remaining
                FROM leave_balance
                WHERE employee_name = %s AND leave_type = %s
            """, (employee_name, leave_type))

        if not balance:
            return jsonify({"success": False, "error": f"Unknown leave type: {leave_type}"}), 400

        remaining = Decimal(str(balance["remaining"]))
        if duration > remaining:
            return jsonify({
                "success": False,
                "error": (
                    f"Insufficient {leave_type} leave balance. "
                    f"Remaining: {float(remaining):.1f} days, "
                    f"Requested: {float(duration):.1f} days."
                )
            }), 400

        # ── Insert leave record ───────────────────────────────────────────
        execute_query("""
            INSERT INTO leaves
              (employee_name, leave_type, leave_type_category, half_day_period,
               leave_duration, start_date, end_date, reason, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            employee_name, leave_type, leave_type_category,
            half_day_period, str(duration),
            start_date, end_date, data.get("reason", "")
        ), commit=True)

        period_label = ""
        if leave_type_category == "half_day":
            period_label = " (First Half)" if half_day_period == "first_half" else " (Second Half)"

        return jsonify({
            "success":                   True,
            "message":                   "Leave applied successfully — awaiting approval.",
            "leave_type_category":       leave_type_category,
            "half_day_period":           half_day_period,
            "duration_days":             float(duration),
            "remaining_after_approval":  float(remaining - duration),
            "note":                      f"{leave_type.title()} leave{period_label} for {float(duration):.1f} day(s) submitted.",
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PATCH /leaves/<id>/approve — manager/HR approves and deducts balance
# ---------------------------------------------------------------------------

@leave_bp.route("/<int:leave_id>/approve", methods=["PATCH"])
@role_required(["manager", "hr"])
def approve_leave(current_user, leave_id):
    """Approve a pending leave application and deduct from the employee's balance."""
    try:
        leave = execute_single("SELECT * FROM leaves WHERE id = %s", (leave_id,))
        if not leave:
            return jsonify({"success": False, "error": "Leave application not found"}), 404

        if leave["status"] != "pending":
            return jsonify({"success": False, "error": f"Leave is already {leave['status']}"}), 400

        duration = _get_stored_duration(leave)

        success = deduct_leave_balance(leave["employee_name"], leave["leave_type"], duration)
        if not success:
            return jsonify({"success": False, "error": "Insufficient leave balance — cannot approve"}), 400

        execute_query(
            "UPDATE leaves SET status = 'approved' WHERE id = %s",
            (leave_id,), commit=True
        )

        cat = leave.get("leave_type_category", "full_day") or "full_day"
        period_str = ""
        if cat == "half_day" and leave.get("half_day_period"):
            period_str = f" ({leave['half_day_period'].replace('_', ' ').title()})"

        return jsonify({
            "success": True,
            "message": (
                f"Leave approved for {leave['employee_name']} "
                f"({float(duration):.1f} day(s){period_str} "
                f"deducted from {leave['leave_type']} balance)."
            )
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PATCH /leaves/<id>/reject — manager/HR rejects a leave
# ---------------------------------------------------------------------------

@leave_bp.route("/<int:leave_id>/reject", methods=["PATCH"])
@role_required(["manager", "hr"])
def reject_leave(current_user, leave_id):
    """Reject a pending leave. If it was already approved, refund the balance."""
    try:
        data  = request.get_json() or {}
        leave = execute_single("SELECT * FROM leaves WHERE id = %s", (leave_id,))
        if not leave:
            return jsonify({"success": False, "error": "Leave application not found"}), 404

        if leave["status"] == "rejected":
            return jsonify({"success": True, "message": "Leave is already rejected"}), 200

        if leave["status"] == "approved":
            duration = _get_stored_duration(leave)
            refund_leave_balance(leave["employee_name"], leave["leave_type"], duration)

        execute_query(
            "UPDATE leaves SET status = 'rejected' WHERE id = %s",
            (leave_id,), commit=True
        )

        return jsonify({
            "success": True,
            "message": f"Leave rejected for {leave['employee_name']}",
            "reason":  data.get("reason", "")
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PUT /leaves/<id> — manager/HR updates leave status (toggle)
# ---------------------------------------------------------------------------

@leave_bp.route("/<int:leave_id>", methods=["PUT"])
@role_required(["manager", "hr"])
def update_leave_status_api(current_user, leave_id):
    try:
        data       = request.get_json()
        new_status = data.get("status")

        if new_status not in ("approved", "rejected", "pending"):
            return jsonify({"success": False, "error": "Invalid status. Use: approved, rejected, pending"}), 400

        leave = execute_single("SELECT * FROM leaves WHERE id = %s", (leave_id,))
        if not leave:
            return jsonify({"success": False, "error": "Leave request not found"}), 404

        old_status = leave["status"]
        if old_status == new_status:
            return jsonify({"success": True, "message": "No change needed"}), 200

        duration = _get_stored_duration(leave)

        if new_status == "approved" and old_status != "approved":
            success = deduct_leave_balance(leave["employee_name"], leave["leave_type"], duration)
            if not success:
                return jsonify({"success": False, "error": "Employee does not have enough remaining leave balance."}), 400

        elif old_status == "approved" and new_status != "approved":
            refund_leave_balance(leave["employee_name"], leave["leave_type"], duration)

        execute_query("UPDATE leaves SET status = %s WHERE id = %s", (new_status, leave_id), commit=True)
        return jsonify({"success": True, "message": f"Leave successfully {new_status}"}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
