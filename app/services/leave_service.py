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
    "employee":    ["manager", "hr", "admin", "superadmin"],
    "team_member": ["manager", "hr", "admin", "superadmin"],
    "intern":      ["manager", "hr", "admin", "superadmin"],
    "consultant":  ["manager", "hr", "admin", "superadmin"],
    "hr":          ["admin", "superadmin"],
    "manager":     ["admin", "superadmin"],
    "admin":       ["superadmin"],
    "superadmin":  [],
}


def validate_approval_authority(approver: dict, leave: dict) -> dict:
    """
    Enforce the role-based leave approval hierarchy.
    """
    approver_name = (approver.get("employee_name") or "").strip()
    approver_role = str(approver.get("role", "")).lower().strip()
    requester_name = (leave.get("employee_name") or "").strip()

    # ── Fetch requester role (use stored snapshot if available, else query) ──
    requester_role = str(leave.get("requester_role") or "").lower().strip()
    if not requester_role:
        user_row = execute_single(
            "SELECT role FROM users WHERE employee_name = %s LIMIT 1",
            (requester_name,)
        )
        requester_role = str(user_row["role"] if user_row else "employee").lower().strip()

    # ── Self-approval block ──────────────────────────────────────────────────
    if approver_name and requester_name and approver_name.lower() == requester_name.lower():
        return {
            "ok": False,
            "error": "Self-approval is not permitted. Please contact your designated approver.",
            "code": 403,
        }

    # ── Admin/Superadmin bypass: can approve everyone except themselves ───────────
    if approver_role in ("admin", "superadmin"):
        return {"ok": True}

    # ── Lookup allowed approvers for this requester's role ───────────────────
    allowed = _APPROVAL_MATRIX.get(requester_role, ["manager", "hr", "admin", "superadmin"])
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
# Manager Resolution & Multi-Approver Signoff Helpers
# ---------------------------------------------------------------------------

_table_ensured = False

def _ensure_leave_signoffs_table():
    global _table_ensured
    if _table_ensured:
        return
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS leave_signoffs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                leave_id INT NOT NULL,
                approver_role VARCHAR(50) NOT NULL,
                approver_name VARCHAR(100) NULL,
                project_name VARCHAR(100) NULL,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                action_by VARCHAR(100) NULL,
                action_at TIMESTAMP NULL,
                comments TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ls_leave (leave_id),
                INDEX idx_ls_approver (approver_name, approver_role),
                INDEX idx_ls_status (status)
            )
        """, commit=True)
        _table_ensured = True
    except Exception as e:
        logger.warning("Error ensuring leave_signoffs table: %s", e)


def get_employee_project_managers(employee_name: str) -> list[dict]:
    """
    Find all distinct project managers for active projects assigned to employee_name.
    Returns: [{'manager_name': '...', 'project_name': '...'}, ...]
    """
    try:
        rows = execute_query("""
            SELECT DISTINCT p.manager_name, p.name AS project_name
            FROM project_assignments pa
            JOIN projects p ON pa.project_id = p.id
            WHERE pa.employee_name = %s
              AND p.status NOT IN ('completed', 'closed', 'cancelled')
              AND p.manager_name IS NOT NULL
              AND p.manager_name != ''
            ORDER BY p.name
        """, (employee_name,))
        return rows or []
    except Exception as e:
        logger.warning("Error getting project managers for %s: %s", employee_name, e)
        return []


def create_leave_signoffs(leave_id: int, employee_name: str, applicant_role: str = None) -> list[dict]:
    """
    Generate required multi-signoffs when a leave application is created:
      - Team Member (role: employee) -> 1 HR signoff + 1 signoff per assigned project manager.
      - Non-employee (Manager/HR) -> 1 Admin signoff.
    """
    _ensure_leave_signoffs_table()
    created = []
    
    # Always resolve the target employee's actual role in the system
    user_row = execute_single("SELECT role FROM users WHERE employee_name = %s LIMIT 1", (employee_name,))
    actual_role = (user_row["role"] if user_row else (applicant_role or "employee"))
    applicant_role_norm = str(actual_role or "employee").lower().strip()

    try:
        if applicant_role_norm in ("employee", "team_member", "intern", "consultant"):
            # 1. HR Signoff required
            execute_query("""
                INSERT INTO leave_signoffs (leave_id, approver_role, approver_name, project_name, status)
                VALUES (%s, 'hr', NULL, NULL, 'pending')
            """, (leave_id,), commit=True)
            created.append({"approver_role": "hr", "approver_name": None, "project_name": None})

            # 2. All assigned project managers
            mgrs = get_employee_project_managers(employee_name)
            for m in mgrs:
                execute_query("""
                    INSERT INTO leave_signoffs (leave_id, approver_role, approver_name, project_name, status)
                    VALUES (%s, 'manager', %s, %s, 'pending')
                """, (leave_id, m["manager_name"], m["project_name"]), commit=True)
                created.append({"approver_role": "manager", "approver_name": m["manager_name"], "project_name": m["project_name"]})
        else:
            # Non-employee: Admin signoff
            execute_query("""
                INSERT INTO leave_signoffs (leave_id, approver_role, approver_name, project_name, status)
                VALUES (%s, 'admin', NULL, NULL, 'pending')
            """, (leave_id,), commit=True)
            created.append({"approver_role": "admin", "approver_name": None, "project_name": None})
    except Exception as e:
        logger.error("Failed creating leave_signoffs for leave %s: %s", leave_id, e)

    return created


def get_leave_signoffs(leave_id: int) -> list[dict]:
    """Fetch all signoff requirements and current status for a given leave_id."""
    try:
        _ensure_leave_signoffs_table()
        rows = execute_query("""
            SELECT id, leave_id, approver_role, approver_name, project_name, status,
                   action_by, action_at, comments, created_at
            FROM leave_signoffs
            WHERE leave_id = %s
            ORDER BY id ASC
        """, (leave_id,))
        for r in rows or []:
            if hasattr(r.get("action_at"), "isoformat") and r["action_at"]:
                r["action_at"] = r["action_at"].isoformat()
            if hasattr(r.get("created_at"), "isoformat") and r["created_at"]:
                r["created_at"] = r["created_at"].isoformat()
        return rows or []
    except Exception as e:
        logger.warning("Error fetching leave_signoffs for leave %s: %s", leave_id, e)
        return []


def process_leave_signoff(leave: dict, current_user: dict, action: str, comments: str = None) -> dict:
    """
    Process an individual approval or rejection decision.
    Matches the approver against required signoffs and evaluates overall status.
    """
    _ensure_leave_signoffs_table()
    leave_id = leave["id"]
    approver_name = (current_user.get("employee_name") or "").strip()
    approver_role = str(current_user.get("role", "")).lower().strip()
    applicant_name = (leave.get("employee_name") or "").strip()

    if approver_name and applicant_name and approver_name.lower() == applicant_name.lower():
        return {"ok": False, "error": "Self-approval is not permitted.", "code": 403}

    signoffs = get_leave_signoffs(leave_id)
    
    # Auto-heal: verify signoffs match target employee's actual role
    user_row = execute_single("SELECT role FROM users WHERE employee_name = %s LIMIT 1", (applicant_name,))
    applicant_role = str(user_row["role"] if user_row else (leave.get("requester_role") or "employee")).lower().strip()
    is_emp = applicant_role in ("employee", "team_member", "intern", "consultant")
    has_hr = any(str(s.get("approver_role", "")).lower() == "hr" for s in signoffs)

    if not signoffs or (is_emp and not has_hr):
        execute_query("DELETE FROM leave_signoffs WHERE leave_id = %s", (leave_id,), commit=True)
        create_leave_signoffs(leave_id, applicant_name, applicant_role)
        signoffs = get_leave_signoffs(leave_id)

    # Match which signoff record(s) the current user can fulfill
    matched_ids = []
    if approver_role in ("admin", "superadmin"):
        matched_ids = [s["id"] for s in signoffs if str(s.get("status", "")).lower() == "pending"]
    elif approver_role == "hr":
        matched_ids = [s["id"] for s in signoffs if str(s.get("approver_role", "")).lower() == "hr" and str(s.get("status", "")).lower() == "pending"]
    elif approver_role == "manager":
        from app.api_helpers import names_match
        matched_ids = [
            s["id"] for s in signoffs
            if str(s.get("approver_role", "")).lower() == "manager"
            and str(s.get("status", "")).lower() == "pending"
            and (names_match(s.get("approver_name"), approver_name) or not s.get("approver_name"))
        ]

    if not matched_ids:
        already_done = any(s.get("action_by") == approver_name and s["status"] in ("approved", "rejected") for s in signoffs)
        if already_done:
            return {"ok": False, "error": "You have already recorded your decision for this leave application.", "code": 400}
        return {"ok": False, "error": "You are not an authorized pending approver for this leave request.", "code": 403}

    for sid in matched_ids:
        execute_query("""
            UPDATE leave_signoffs
            SET status = %s,
                action_by = %s,
                action_at = NOW(),
                comments = %s
            WHERE id = %s
        """, (action, approver_name, comments, sid), commit=True)

    updated_signoffs = get_leave_signoffs(leave_id)
    has_rejection = any(s["status"] == "rejected" for s in updated_signoffs)
    all_approved = all(s["status"] == "approved" for s in updated_signoffs)

    if action == "rejected" or has_rejection:
        return {
            "ok": True,
            "overall_status": "rejected",
            "is_final": True,
            "signoffs": updated_signoffs,
            "message": f"Leave application rejected by {approver_name} ({approver_role.upper()})."
        }
    elif all_approved:
        return {
            "ok": True,
            "overall_status": "approved",
            "is_final": True,
            "signoffs": updated_signoffs,
            "message": "All required approvals (HR and Project Managers) completed. Leave is fully approved."
        }
    else:
        pending_list = [
            s["project_name"] and f"Manager ({s['project_name']})" or s["approver_role"].upper()
            for s in updated_signoffs if s["status"] == "pending"
        ]
        return {
            "ok": True,
            "overall_status": "pending",
            "is_final": False,
            "signoffs": updated_signoffs,
            "message": f"Approval recorded. Awaiting sign-off from: {', '.join(pending_list)}."
        }


def get_employee_manager(employee_name: str) -> str | None:
    """
    Resolve the designated manager for a given employee.
    Strategy (priority order):
      1. Most recently assigned project manager via project_assignments
      2. Any active manager in the system (fallback)
    Returns the manager's employee_name, or None if not found.
    """
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

    mgr = execute_single(
        "SELECT employee_name FROM users WHERE role = 'manager' AND is_active = TRUE LIMIT 1"
    )
    return mgr["employee_name"] if mgr else None


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

    Phase 3 note:
        Planned, Unplanned, and Optional leaves are inserted with
        total_leaves = 0. The quarterly credit scheduler is the *only*
        mechanism that increments those three balances. Inserting them at
        their full annual amount here would cause double-crediting once the
        scheduler runs, because it would add on top of the initial full amount.
        All other leave types (sick, casual, earned, …) are unaffected.
    """
    # Leave types managed exclusively by the quarterly credit scheduler.
    # They must start at 0 to avoid double-crediting.
    QUARTERLY_LEAVE_TYPES = {"planned", "unplanned", "optional"}

    config = get_leave_config()

    for entry in config:
        leave_type   = entry["leave_type"]
        # For quarterly-managed types, override to 0 regardless of config value.
        total_leaves = 0 if leave_type.lower() in QUARTERLY_LEAVE_TYPES else entry["total_leaves"]

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

    # Also ensure the quarterly-managed types have a zero row even if
    # they are not in leave_config yet (they may be added later).
    for qt in sorted(QUARTERLY_LEAVE_TYPES):
        if not any(e["leave_type"].lower() == qt for e in config):
            if cursor:
                cursor.execute("""
                    INSERT IGNORE INTO leave_balance (employee_name, leave_type, total_leaves, used_leaves)
                    VALUES (%s, %s, 0, 0)
                """, (employee_name, qt))
            else:
                execute_query("""
                    INSERT IGNORE INTO leave_balance (employee_name, leave_type, total_leaves, used_leaves)
                    VALUES (%s, %s, 0, 0)
                """, (employee_name, qt), commit=True)


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
