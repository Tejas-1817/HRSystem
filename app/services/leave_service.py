# ---------------------------------------------------------------------------
# Leave Service — Allocation, balance queries, conflict validation,
#                 half-day duration calculation, and RBAC approval logic
# ---------------------------------------------------------------------------

from decimal import Decimal
from datetime import date, timedelta
from app.models.database import execute_query, execute_single


# ---------------------------------------------------------------------------
# RBAC — Approval Authority Validation
# ---------------------------------------------------------------------------

# Role hierarchy: who can approve whose leave
# Format: { requester_role: [allowed_approver_roles] }
_APPROVAL_MATRIX = {
    "employee": ["manager", "admin"],
    "hr":       ["admin"],
    "manager":  ["admin"],
    "admin":    [],  # Admins don't need approval
}


def validate_approval_authority(approver: dict, leave: dict) -> dict:
    """
    Enforce the role-based leave approval hierarchy.

    Rules:
      - employee leave  → approved by manager or admin
      - hr leave        → approved by admin ONLY
      - manager leave   → approved by admin ONLY
      - admin leave     → no one needs to approve (guard returns ok=False)
      - No self-approval for any role

    Args:
        approver : current_user dict from JWT (keys: employee_name, role)
        leave    : leave row from DB (keys: employee_name, requester_role)

    Returns:
        {"ok": True}  — approver is authorised
        {"ok": False, "error": "<message>", "code": <http_status_int>}
    """
    approver_name = approver.get("employee_name")
    approver_role = approver.get("role", "")
    requester_name = leave.get("employee_name")

    # ── Fetch requester role (use stored snapshot if available, else query) ──
    requester_role = leave.get("requester_role")
    if not requester_role:
        user_row = execute_single(
            "SELECT role FROM users WHERE employee_name = %s LIMIT 1",
            (requester_name,)
        )
        requester_role = user_row["role"] if user_row else "employee"

    # ── Self-approval block ──────────────────────────────────────────────────
    if approver_name == requester_name:
        return {
            "ok": False,
            "error": "Self-approval is not permitted. Please contact your designated approver.",
            "code": 403,
        }

    # ── Admin bypass: admin can approve everyone except themselves ───────────
    if approver_role == "admin":
        if requester_role == "admin":
            return {
                "ok": False,
                "error": "Admin leave requests do not require approval.",
                "code": 400,
            }
        return {"ok": True}

    # ── Lookup allowed approvers for this requester's role ───────────────────
    allowed = _APPROVAL_MATRIX.get(requester_role, [])
    if approver_role not in allowed:
        role_label = requester_role.title()
        allowed_label = " or ".join(r.title() for r in allowed) if allowed else "No one"
        return {
            "ok": False,
            "error": (
                f"Unauthorized leave approval action. "
                f"{role_label} leave requests can only be approved by: {allowed_label}. "
                f"Your role ({approver_role.title()}) does not have this permission."
            ),
            "code": 403,
        }

    return {"ok": True}


# ---------------------------------------------------------------------------
# Manager Resolution — find the right approver for an employee
# ---------------------------------------------------------------------------

def get_employee_manager(employee_name: str) -> str | None:
    """
    Resolve the designated manager for a given employee.

    Strategy (priority order):
      1. Most recently assigned project manager via project_assignments
      2. Any active manager in the system (fallback)

    Returns the manager's employee_name, or None if not found.
    """
    # 1. Most recent active project assignment
    row = execute_single("""
        SELECT p.manager_name
        FROM project_assignments pa
        JOIN projects p ON pa.project_id = p.id
        WHERE pa.employee_name = %s
          AND p.status NOT IN ('completed', 'closed', 'cancelled')
          AND p.manager_name IS NOT NULL
        ORDER BY pa.assigned_at DESC
        LIMIT 1
    """, (employee_name,))
    if row and row.get("manager_name"):
        return row["manager_name"]

    # 2. Fallback: any active manager
    mgr = execute_single(
        "SELECT employee_name FROM users WHERE role = 'manager' AND is_active = TRUE LIMIT 1"
    )
    return mgr["employee_name"] if mgr else None

# Default leave quotas (used if leave_config table is empty or missing)
DEFAULT_LEAVE_QUOTAS = [
    {"leave_type": "sick",   "total_leaves": 12, "description": "Medical / health related leave"},
    {"leave_type": "casual", "total_leaves": 10, "description": "Personal / casual leave"},
    {"leave_type": "earned", "total_leaves": 15, "description": "Earned / privilege leave"},
]


def get_leave_config():
    """
    Fetch leave configuration from `leave_config` table.
    Falls back to DEFAULT_LEAVE_QUOTAS if the table is empty or doesn't exist.
    """
    try:
        rows = execute_query(
            "SELECT leave_type, default_total, description FROM leave_config WHERE is_active = TRUE ORDER BY leave_type"
        )
        if rows:
            return [
                {"leave_type": r["leave_type"], "total_leaves": int(r["default_total"]), "description": r.get("description")}
                for r in rows
            ]
    except Exception:
        pass  # Table may not exist yet — use defaults
    return DEFAULT_LEAVE_QUOTAS


def allocate_default_leaves(employee_name, cursor=None):
    """
    Allocate default leave balances for a new employee.
    Uses INSERT IGNORE to prevent duplicates if called multiple times.

    Args:
        employee_name: The employee's system name (e.g., T_Kartik).
        cursor: Optional MySQL cursor. If provided, executes on the cursor
                (caller must commit). If None, uses execute_query with auto-commit.
    """
    config = get_leave_config()

    for entry in config:
        leave_type   = entry["leave_type"]
        total_leaves = entry["total_leaves"]

        if cursor:
            # Use the shared cursor (caller commits the transaction)
            cursor.execute("""
                INSERT IGNORE INTO leave_balance (employee_name, leave_type, total_leaves, used_leaves)
                VALUES (%s, %s, %s, 0)
            """, (employee_name, leave_type, total_leaves))
        else:
            # Standalone call — auto-commit each insert
            execute_query("""
                INSERT IGNORE INTO leave_balance (employee_name, leave_type, total_leaves, used_leaves)
                VALUES (%s, %s, %s, 0)
            """, (employee_name, leave_type, total_leaves), commit=True)


def get_employee_balance(employee_name):
    """
    Fetch the full leave balance summary for an employee.
    Returns a list of dicts with total, used, and remaining per leave type.
    Values are returned as float to support 0.5 half-day deductions.
    """
    rows = execute_query("""
        SELECT leave_type, total_leaves, used_leaves,
               (total_leaves - used_leaves) AS remaining_leaves
        FROM leave_balance
        WHERE employee_name = %s
        ORDER BY leave_type
    """, (employee_name,))

    # Normalize Decimal DB values to float for JSON serialisation
    for r in rows:
        r["total_leaves"]     = float(r["total_leaves"])
        r["used_leaves"]      = float(r["used_leaves"])
        r["remaining_leaves"] = float(r["remaining_leaves"])

    return rows


# ---------------------------------------------------------------------------
# Half-Day: Duration calculation
# ---------------------------------------------------------------------------

def calculate_leave_duration(leave_type_category: str, start_date: date, end_date: date) -> Decimal:
    """
    Returns the canonical leave duration (in days) to deduct from the balance.

    Rules:
      - half_day  → always 0.5  (start_date MUST equal end_date, enforced upstream)
      - full_day  → count of Mon–Fri working days between start_date and end_date (inclusive),
                    skipping bank holidays stored in the `holidays` table.

    Returns Decimal for precision safety in arithmetic.
    """
    if leave_type_category == "half_day":
        return Decimal("0.5")

    # Full-day: count Mon–Fri days, skipping declared holidays
    holiday_rows = execute_query("""
        SELECT date FROM holidays
        WHERE date BETWEEN %s AND %s
    """, (start_date.isoformat(), end_date.isoformat()))
    holiday_dates = {
        (r["date"] if isinstance(r["date"], date) else date.fromisoformat(str(r["date"])))
        for r in holiday_rows
    }

    count = 0
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5 and cur not in holiday_dates:
            count += 1
        cur += timedelta(days=1)

    return Decimal(str(count))


# ---------------------------------------------------------------------------
# Half-Day: Conflict validation
# ---------------------------------------------------------------------------

def validate_half_day_conflict(employee_name: str, target_date: date, new_period: str) -> dict:
    """
    Validates that a new half-day leave application does not conflict with
    existing leave records for the same employee and date.

    Checks:
      1. No existing approved/pending FULL-DAY leave on target_date.
      2. No existing approved/pending HALF-DAY leave for the SAME period.
      3. Combined approved+pending half-day leaves on that date do not exceed 1.0 day.

    Args:
        employee_name : The employee applying.
        target_date   : The leave date (start == end for half-day).
        new_period    : 'first_half' | 'second_half'

    Returns:
        {"ok": True}  on no conflict.
        {"ok": False, "error": "<message>"}  on conflict.
    """
    date_str = target_date.isoformat()

    # 1. Check for any overlapping full-day leave on this date
    full_day_conflict = execute_single("""
        SELECT id FROM leaves
        WHERE employee_name = %s
          AND leave_type_category = 'full_day'
          AND status IN ('pending', 'approved')
          AND %s BETWEEN start_date AND end_date
        LIMIT 1
    """, (employee_name, date_str))

    if full_day_conflict:
        return {
            "ok": False,
            "error": f"A full-day leave already exists on {date_str}. "
                     "Cannot apply a half-day leave on the same date."
        }

    # 2. Check for same-period half-day conflict
    period_conflict = execute_single("""
        SELECT id FROM leaves
        WHERE employee_name = %s
          AND leave_type_category = 'half_day'
          AND half_day_period = %s
          AND status IN ('pending', 'approved')
          AND start_date = %s
        LIMIT 1
    """, (employee_name, new_period, date_str))

    period_label = "First Half (Morning)" if new_period == "first_half" else "Second Half (Afternoon)"
    if period_conflict:
        return {
            "ok": False,
            "error": f"A {period_label} leave already exists on {date_str}."
        }

    # 3. Guard: combined half-day duration on this date must not exceed 1.0
    existing_duration = execute_single("""
        SELECT COALESCE(SUM(leave_duration), 0) AS total_duration
        FROM leaves
        WHERE employee_name = %s
          AND leave_type_category = 'half_day'
          AND status IN ('pending', 'approved')
          AND start_date = %s
    """, (employee_name, date_str))

    current = Decimal(str(existing_duration["total_duration"])) if existing_duration else Decimal("0")
    if current + Decimal("0.5") > Decimal("1.0"):
        return {
            "ok": False,
            "error": f"Adding another half-day on {date_str} would exceed 1 full day of leave."
        }

    return {"ok": True}


# ---------------------------------------------------------------------------
# Balance deduction / refund  (decimal-safe)
# ---------------------------------------------------------------------------

def deduct_leave_balance(employee_name: str, leave_type: str, days) -> bool:
    """
    Increment used_leaves for the given employee and leave type.
    `days` may be an int, float, or Decimal (e.g. 0.5 for a half-day).
    Returns True on success, False if insufficient balance.
    """
    days = Decimal(str(days))

    balance = execute_single("""
        SELECT total_leaves, used_leaves, (total_leaves - used_leaves) AS remaining
        FROM leave_balance
        WHERE employee_name = %s AND leave_type = %s
    """, (employee_name, leave_type))

    if not balance:
        return False

    remaining = Decimal(str(balance["remaining"]))
    if days > remaining:
        return False

    execute_query("""
        UPDATE leave_balance
        SET used_leaves = used_leaves + %s
        WHERE employee_name = %s AND leave_type = %s
    """, (str(days), employee_name, leave_type), commit=True)

    return True


def refund_leave_balance(employee_name: str, leave_type: str, days) -> None:
    """
    Decrement used_leaves when a leave is cancelled/rejected after approval.
    Ensures used_leaves never goes below 0.
    `days` may be int, float, or Decimal.
    """
    days = Decimal(str(days))

    execute_query("""
        UPDATE leave_balance
        SET used_leaves = GREATEST(used_leaves - %s, 0)
        WHERE employee_name = %s AND leave_type = %s
    """, (str(days), employee_name, leave_type), commit=True)
