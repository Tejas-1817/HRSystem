# ---------------------------------------------------------------------------
# Help Desk Service — Ticket reference generation, audit logging,
#                     and RBAC-aware query building
# ---------------------------------------------------------------------------

from app.models.database import execute_query, execute_single


# ---------------------------------------------------------------------------
# Ticket Reference Generator
# ---------------------------------------------------------------------------

def generate_ticket_ref() -> str:
    """
    Generate a sequential human-readable ticket reference: HD-0001, HD-0042, etc.
    Uses MAX(id) + 1 to determine the next number safely.
    Thread safety: the UNIQUE constraint on ticket_ref handles concurrent inserts.
    """
    row = execute_single("SELECT COALESCE(MAX(id), 0) AS max_id FROM helpdesk_tickets")
    next_num = (row["max_id"] + 1) if row else 1
    return f"HD-{next_num:04d}"


# ---------------------------------------------------------------------------
# Audit History Logger
# ---------------------------------------------------------------------------

def log_history(ticket_id: int, changed_by: str, field: str,
                old_value, new_value, note: str = None) -> None:
    """
    Append one immutable row to helpdesk_ticket_history.

    Args:
        ticket_id  : The helpdesk_tickets.id being changed.
        changed_by : employee_name of the actor making the change.
        field      : Column being changed: 'status' | 'assigned_to' | 'priority'.
        old_value  : Previous value (None if field was empty).
        new_value  : New value being set.
        note       : Optional free-text comment from the actor.
    """
    execute_query("""
        INSERT INTO helpdesk_ticket_history
            (ticket_id, changed_by, field, old_value, new_value, note)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        ticket_id,
        changed_by,
        field,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None,
        note,
    ), commit=True)


# ---------------------------------------------------------------------------
# RBAC-aware ticket fetcher
# ---------------------------------------------------------------------------

def get_tickets(current_user: dict, filters: dict) -> list:
    """
    Fetch tickets with strict RBAC scoping and optional filters.

    Visibility Policy:
      - employee → own tickets only (WHERE employee_name = <self>)
      - hr / admin → all tickets
      - manager   → BLOCKED — call site must reject before reaching here

    Supported filters (all optional):
      status, priority, category, search (matches title/description), assigned_to
    """
    role = current_user["role"]
    emp  = current_user["employee_name"]

    conditions = []
    params = []

    # Scope to own tickets for regular employees and managers
    if role in ("employee", "manager"):
        conditions.append("t.employee_name = %s")
        params.append(emp)

    # Optional status filter
    status = filters.get("status")
    if status:
        conditions.append("t.status = %s")
        params.append(status)

    # Optional priority filter
    priority = filters.get("priority")
    if priority:
        conditions.append("t.priority = %s")
        params.append(priority)

    # Optional category filter
    category = filters.get("category")
    if category:
        conditions.append("t.category = %s")
        params.append(category)

    # Optional keyword search across title + description
    search = filters.get("search")
    if search:
        conditions.append("(t.title LIKE %s OR t.description LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    # Optional assigned_to filter (HR/Admin use case)
    assigned_to = filters.get("assigned_to")
    if assigned_to and role != "employee":
        conditions.append("t.assigned_to = %s")
        params.append(assigned_to)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = execute_query(f"""
        SELECT
            t.id, t.ticket_ref, t.title, t.description,
            t.category, t.priority, t.status,
            t.employee_name, t.assigned_to,
            t.created_at, t.updated_at, t.resolved_at,
            t.issue_type, t.device_id,
            d.brand AS device_brand, d.model AS device_model
        FROM helpdesk_tickets t
        LEFT JOIN devices d ON t.device_id = d.id
        {where_clause}
        ORDER BY
            FIELD(t.priority, 'urgent', 'high', 'medium', 'low'),
            t.created_at DESC
    """, tuple(params) if params else None)

    # Serialize datetime fields
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_ticket_or_404(ticket_id: int):
    """Fetch a single ticket dict by PK, or return None if not found."""
    row = execute_single("SELECT * FROM helpdesk_tickets WHERE id = %s", (ticket_id,))
    if row:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
    return row


def get_ticket_history(ticket_id: int) -> list:
    """Return the full audit trail for a ticket, newest first."""
    rows = execute_query("""
        SELECT id, changed_by, field, old_value, new_value, note, changed_at
        FROM helpdesk_ticket_history
        WHERE ticket_id = %s
        ORDER BY changed_at ASC
    """, (ticket_id,))

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()

    return rows


def can_view_ticket(current_user: dict, ticket: dict) -> bool:
    """
    Strict ticket visibility:
      - employee / manager → own tickets only
      - hr / admin → all tickets
    """
    role = current_user["role"]
    if role in ("employee", "manager"):
        return ticket["employee_name"] == current_user["employee_name"]
    return True  # hr, admin


# Roles that have HR-level read/write access to tickets (manager excluded by design)
STAFF_ROLES = {"hr", "admin"}
