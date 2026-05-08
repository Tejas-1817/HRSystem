"""
Timesheet Approval Service
──────────────────────────
Centralised RBAC-enforced approval/rejection logic for timesheets.

Business Rules (role hierarchy):
  • Employee timesheets  → approved by the Manager of the referenced project
  • HR timesheets        → approved by Admin only
  • Manager timesheets   → approved by Admin only
  • Admin timesheets     → no approval required (or self-service)
  • Self-approval        → BLOCKED for all roles
  • HR approving employee timesheets → BLOCKED
"""

import logging
from app.models.database import execute_query, execute_single, Transaction

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# RBAC Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_approval_authority(approver: dict, timesheet: dict) -> tuple[bool, str]:
    """
    Checks whether `approver` (current_user dict) is authorised to approve/reject
    the given `timesheet` row (dict from DB).

    Returns:
        (True, "")              – authorised
        (False, "reason string") – blocked, with human-readable reason
    """
    approver_name = approver["employee_name"]
    approver_role = approver["role"]
    owner_name    = timesheet["employee_name"]
    owner_role    = timesheet.get("owner_role") or _resolve_owner_role(owner_name)

    # ── 1. Self-approval prevention ───────────────────────────────────────
    if approver_name == owner_name:
        return False, "Self-approval is not permitted. Timesheets must be reviewed by an authorised approver."

    # ── 2. Employee cannot approve anything ───────────────────────────────
    if approver_role == "employee":
        return False, "Employees do not have timesheet approval permissions."

    # ── 3. Admin: full authority (except self-approval, already blocked) ──
    if approver_role == "admin":
        return True, ""

    # ── 4. Manager: can only approve employee timesheets on their projects ─
    if approver_role == "manager":
        if owner_role in ("hr", "manager", "admin"):
            return False, (
                f"Managers cannot approve {owner_role.upper()} timesheets. "
                f"Only Admin can approve timesheets for {owner_role.upper()} employees."
            )
        # Verify manager owns the project referenced in this timesheet entry
        project_name = timesheet.get("project")
        if project_name:
            is_project_manager = execute_single(
                "SELECT id FROM projects WHERE name = %s AND manager_name = %s",
                (project_name, approver_name)
            )
            if not is_project_manager:
                return False, (
                    f"You are not the manager of project '{project_name}'. "
                    f"Only the assigned project manager can approve this timesheet."
                )
        return True, ""

    # ── 5. HR: cannot approve employee timesheets ─────────────────────────
    if approver_role == "hr":
        return False, (
            "HR is not permitted to approve timesheets directly. "
            "Employee timesheets must be approved by their project Manager. "
            "HR timesheets must be approved by Admin."
        )

    # Fallback: deny unknown roles
    return False, f"Unknown approver role '{approver_role}'. Access denied."


def _resolve_owner_role(employee_name: str) -> str:
    """Fallback: look up the owner's role from the users table if not cached."""
    user = execute_single(
        "SELECT role FROM users WHERE employee_name = %s", (employee_name,)
    )
    return user["role"] if user else "employee"


# ─────────────────────────────────────────────────────────────────────────────
# Approval Action
# ─────────────────────────────────────────────────────────────────────────────

def approve_timesheet(approver: dict, timesheet_id: int, comments: str = None) -> dict:
    """
    Full approval flow: validate → update → audit-log → notify.

    Args:
        approver:     current_user dict from middleware
        timesheet_id: primary key of the timesheet entry
        comments:     optional reviewer comments

    Returns:
        dict with success/error keys
    """
    # 1. Fetch timesheet
    ts = execute_single("SELECT * FROM timesheets WHERE id = %s", (timesheet_id,))
    if not ts:
        return {"success": False, "error": "Timesheet entry not found", "status_code": 404}

    # 2. Check current status
    if ts["status"] == "approved":
        return {"success": False, "error": "This timesheet entry is already approved.", "status_code": 400}
    if ts["status"] not in ("submitted", "pending"):
        return {
            "success": False,
            "error": f"Cannot approve a timesheet with status '{ts['status']}'. Only 'submitted' or 'pending' entries can be reviewed.",
            "status_code": 400,
        }

    # 3. RBAC validation
    authorised, reason = validate_approval_authority(approver, ts)
    if not authorised:
        # Log the unauthorized attempt
        _log_audit(approver, "RBAC_VIOLATION",
                   f"Unauthorized approval attempt on timesheet {timesheet_id} for {ts['employee_name']}: {reason}")
        return {"success": False, "error": reason, "status_code": 403}

    # 4. Update timesheet
    execute_query("""
        UPDATE timesheets
        SET status = 'approved',
            manager_comments = %s,
            manager_name     = %s,
            approved_by      = %s,
            approver_role    = %s,
            approved_at      = NOW(),
            reviewed_at      = NOW(),
            rejection_reason = NULL
        WHERE id = %s
    """, (comments, approver["employee_name"], approver["employee_name"],
          approver["role"], timesheet_id), commit=True)

    # 5. Audit trail
    _record_approval_history(timesheet_id, "approved", approver, comments)

    # 6. Notify the timesheet owner
    _notify(
        recipient=ts["employee_name"],
        title="Timesheet Approved",
        message=(
            f"Your timesheet entry (ID: {timesheet_id}) for project '{ts.get('project', 'N/A')}' "
            f"on {ts.get('start_date', '')} has been approved by {approver['employee_name']}."
            + (f" Comments: {comments}" if comments else "")
        ),
        notif_type="timesheet_approved",
    )

    # 7. System audit log
    _log_audit(approver, "timesheet_approved",
               f"{approver['employee_name']} ({approver['role']}) approved timesheet {timesheet_id} "
               f"for {ts['employee_name']}")

    logger.info(
        f"APPROVAL: {approver['employee_name']} ({approver['role']}) approved "
        f"timesheet {timesheet_id} for {ts['employee_name']}"
    )

    return {
        "success": True,
        "message": "Timesheet entry approved successfully",
        "entry_id": timesheet_id,
        "status_code": 200,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rejection Action
# ─────────────────────────────────────────────────────────────────────────────

def reject_timesheet(approver: dict, timesheet_id: int, reason: str, comments: str = None) -> dict:
    """
    Full rejection flow: validate → update → audit-log → notify.

    Args:
        approver:     current_user dict from middleware
        timesheet_id: primary key of the timesheet entry
        reason:       mandatory rejection reason
        comments:     optional additional reviewer comments

    Returns:
        dict with success/error keys
    """
    # 1. Fetch timesheet
    ts = execute_single("SELECT * FROM timesheets WHERE id = %s", (timesheet_id,))
    if not ts:
        return {"success": False, "error": "Timesheet entry not found", "status_code": 404}

    # 2. Check current status
    if ts["status"] == "rejected":
        return {"success": False, "error": "This timesheet entry is already rejected.", "status_code": 400}
    if ts["status"] not in ("submitted", "pending"):
        return {
            "success": False,
            "error": f"Cannot reject a timesheet with status '{ts['status']}'. Only 'submitted' or 'pending' entries can be reviewed.",
            "status_code": 400,
        }

    # 3. Mandatory reason
    if not reason or not reason.strip():
        return {"success": False, "error": "A rejection reason is required.", "status_code": 400}

    # 4. RBAC validation
    authorised, deny_reason = validate_approval_authority(approver, ts)
    if not authorised:
        _log_audit(approver, "RBAC_VIOLATION",
                   f"Unauthorized rejection attempt on timesheet {timesheet_id} for {ts['employee_name']}: {deny_reason}")
        return {"success": False, "error": deny_reason, "status_code": 403}

    # 5. Update timesheet
    combined_comments = reason if not comments else f"{reason} | {comments}"
    execute_query("""
        UPDATE timesheets
        SET status           = 'rejected',
            manager_comments = %s,
            manager_name     = %s,
            approved_by      = %s,
            approver_role    = %s,
            approved_at      = NOW(),
            reviewed_at      = NOW(),
            rejection_reason = %s
        WHERE id = %s
    """, (combined_comments, approver["employee_name"], approver["employee_name"],
          approver["role"], reason, timesheet_id), commit=True)

    # 6. Audit trail
    _record_approval_history(timesheet_id, "rejected", approver, combined_comments)

    # 7. Notify the timesheet owner
    _notify(
        recipient=ts["employee_name"],
        title="Timesheet Rejected",
        message=(
            f"Your timesheet entry (ID: {timesheet_id}) for project '{ts.get('project', 'N/A')}' "
            f"on {ts.get('start_date', '')} was rejected by {approver['employee_name']}. "
            f"Reason: {reason}"
        ),
        notif_type="timesheet_rejected",
    )

    # 8. System audit log
    _log_audit(approver, "timesheet_rejected",
               f"{approver['employee_name']} ({approver['role']}) rejected timesheet {timesheet_id} "
               f"for {ts['employee_name']}. Reason: {reason}")

    logger.info(
        f"REJECTION: {approver['employee_name']} ({approver['role']}) rejected "
        f"timesheet {timesheet_id} for {ts['employee_name']}. Reason: {reason}"
    )

    return {
        "success": True,
        "message": "Timesheet entry rejected successfully",
        "entry_id": timesheet_id,
        "status_code": 200,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Trail Query
# ─────────────────────────────────────────────────────────────────────────────

def get_approval_history(timesheet_id: int) -> list[dict]:
    """Fetch the immutable approval audit trail for a timesheet entry."""
    rows = execute_query("""
        SELECT id, timesheet_id, action, performed_by, performer_role, comments, created_at
        FROM timesheet_approval_history
        WHERE timesheet_id = %s
        ORDER BY created_at ASC
    """, (timesheet_id,))

    # Serialise datetime fields
    for row in rows:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Pending Approvals Query
# ─────────────────────────────────────────────────────────────────────────────

def get_pending_approvals(approver: dict) -> list[dict]:
    """
    Return timesheets that are pending the given approver's review,
    filtered by the RBAC rules:
      - Manager: submitted/pending employee timesheets on their projects
      - Admin:   submitted/pending HR and Manager timesheets (+ everything)
    """
    approver_role = approver["role"]
    approver_name = approver["employee_name"]

    if approver_role == "admin":
        # Admin sees all pending timesheets (primary audience: HR + Manager entries)
        rows = execute_query("""
            SELECT t.*, u.role as owner_role_live
            FROM timesheets t
            LEFT JOIN users u ON t.employee_name = u.employee_name
            WHERE t.status IN ('submitted', 'pending')
            ORDER BY t.submitted_at DESC
        """)
    elif approver_role == "manager":
        # Manager sees pending timesheets only for employees on their projects
        rows = execute_query("""
            SELECT t.*, u.role as owner_role_live
            FROM timesheets t
            LEFT JOIN users u ON t.employee_name = u.employee_name
            INNER JOIN projects p ON t.project = p.name AND p.manager_name = %s
            WHERE t.status IN ('submitted', 'pending')
              AND (u.role = 'employee' OR t.owner_role = 'employee')
              AND t.employee_name != %s
            ORDER BY t.submitted_at DESC
        """, (approver_name, approver_name))
    else:
        # HR and employees: no pending approvals queue
        return []

    # Serialise date/datetime fields
    for row in rows:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Submission Notification
# ─────────────────────────────────────────────────────────────────────────────

def notify_submission(employee_name: str, employee_role: str, timesheet_id: int, project_name: str, date_str: str):
    """
    Send notification to the appropriate approver when a timesheet is submitted.
      - Employee  → notify the project manager
      - HR/Manager → notify admin(s)
    """
    if employee_role == "employee":
        # Find the project manager
        if project_name:
            proj = execute_single(
                "SELECT manager_name FROM projects WHERE name = %s", (project_name,)
            )
            if proj and proj["manager_name"]:
                _notify(
                    recipient=proj["manager_name"],
                    title="Timesheet Pending Approval",
                    message=(
                        f"{employee_name} has submitted a timesheet entry for project "
                        f"'{project_name}' on {date_str}. Please review and approve/reject."
                    ),
                    notif_type="timesheet_pending",
                )
    elif employee_role in ("hr", "manager"):
        # Notify all admin users
        admins = execute_query("SELECT employee_name FROM users WHERE role = 'admin' AND is_active = TRUE")
        for admin in admins:
            _notify(
                recipient=admin["employee_name"],
                title="Timesheet Pending Admin Approval",
                message=(
                    f"{employee_name} ({employee_role.upper()}) has submitted a timesheet entry "
                    f"for project '{project_name}' on {date_str}. As Admin, your review is required."
                ),
                notif_type="timesheet_pending",
            )


def log_submission_event(timesheet_id: int, employee_name: str, employee_role: str, is_resubmit: bool = False):
    """Record a submission or resubmission event in the approval history."""
    action = "resubmitted" if is_resubmit else "submitted"
    try:
        execute_query("""
            INSERT INTO timesheet_approval_history (timesheet_id, action, performed_by, performer_role, comments)
            VALUES (%s, %s, %s, %s, %s)
        """, (timesheet_id, action, employee_name, employee_role,
              "Resubmitted after rejection" if is_resubmit else "Initial submission"),
            commit=True)
    except Exception as e:
        # Non-critical — log but don't fail the submission
        logger.warning(f"Failed to log submission event for timesheet {timesheet_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _record_approval_history(timesheet_id: int, action: str, approver: dict, comments: str = None):
    """Insert an immutable row into timesheet_approval_history."""
    try:
        execute_query("""
            INSERT INTO timesheet_approval_history (timesheet_id, action, performed_by, performer_role, comments)
            VALUES (%s, %s, %s, %s, %s)
        """, (timesheet_id, action, approver["employee_name"], approver["role"], comments),
            commit=True)
    except Exception as e:
        logger.error(f"Failed to record approval history for timesheet {timesheet_id}: {e}")


def _notify(recipient: str, title: str, message: str, notif_type: str = "general"):
    """Insert a notification for a user."""
    try:
        execute_query("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, %s)
        """, (recipient, title, message, notif_type), commit=True)
    except Exception as e:
        logger.warning(f"Failed to send notification to {recipient}: {e}")


def _log_audit(user: dict, event_type: str, description: str):
    """Insert an audit log entry."""
    try:
        execute_query("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (user["user_id"], event_type, description), commit=True)
    except Exception as e:
        logger.warning(f"Failed to log audit event: {e}")
