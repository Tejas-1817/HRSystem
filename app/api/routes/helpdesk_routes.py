from flask import Blueprint, request, jsonify
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required
from app.services.helpdesk_service import (
    generate_ticket_ref,
    log_history,
    get_tickets,
    get_ticket_or_404,
    get_ticket_history,
    can_view_ticket,
    STAFF_ROLES,
)

helpdesk_bp = Blueprint("helpdesk", __name__)

VALID_CATEGORIES = {"it_issue", "hr_issue", "payroll", "leave", "others"}
VALID_PRIORITIES  = {"low", "medium", "high", "urgent"}
VALID_STATUSES    = {"open", "in_progress", "resolved", "closed"}
VALID_ISSUE_TYPES = {"Hardware", "Software", "Network"}

CATEGORY_LABELS = {
    "it_issue": "IT Issue",
    "hr_issue": "HR Issue",
    "payroll":  "Payroll",
    "leave":    "Leave",
    "others":   "Others",
}


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# POST /helpdesk/ — Create a new ticket
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/", methods=["POST"])
@token_required
def create_ticket(current_user):
    """
    Any authenticated user can raise a ticket.
    Employees create for themselves; HR/Admin may specify employee_name.

    Payload:
    {
      "title":       "Laptop not connecting to VPN",
      "description": "Since yesterday, my laptop...",
      "category":    "it_issue",           // it_issue | hr_issue | payroll | leave | others
      "priority":    "high"                // low | medium | high | urgent  (default: medium)
    }
    """
    try:
        data = request.get_json() or {}
        required = ("title", "description", "category")
        if not all(k in data for k in required):
            return jsonify({
                "success": False,
                "error": "Missing required fields: title, description, category"
            }), 400

        title       = data["title"].strip()
        description = data["description"].strip()
        category    = data["category"].lower()
        priority    = data.get("priority", "medium").lower()

        if not title:
            return jsonify({"success": False, "error": "title cannot be empty"}), 400
        if not description:
            return jsonify({"success": False, "error": "description cannot be empty"}), 400
        if category not in VALID_CATEGORIES:
            return jsonify({
                "success": False,
                "error": f"Invalid category. Choose from: {', '.join(sorted(VALID_CATEGORIES))}"
            }), 400
        if priority not in VALID_PRIORITIES:
            return jsonify({
                "success": False,
                "error": f"Invalid priority. Choose from: {', '.join(sorted(VALID_PRIORITIES))}"
            }), 400
        
        issue_type = data.get("issue_type")
        device_id  = data.get("device_id")

        if issue_type and issue_type not in VALID_ISSUE_TYPES:
            return jsonify({
                "success": False,
                "error": f"Invalid issue_type. Choose from: {', '.join(sorted(VALID_ISSUE_TYPES))}"
            }), 400

        # RBAC: employees and managers always raise for themselves
        if current_user["role"] in ("employee", "manager"):
            employee_name = current_user["employee_name"]
        else:
            employee_name = data.get("employee_name", current_user["employee_name"])

        ticket_ref = generate_ticket_ref()

        execute_query("""
            INSERT INTO helpdesk_tickets
                (ticket_ref, title, description, category, priority, status, employee_name, device_id, issue_type)
            VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s)
        """, (ticket_ref, title, description, category, priority, employee_name, device_id, issue_type),
             commit=True)

        ticket = execute_single(
            "SELECT id FROM helpdesk_tickets WHERE ticket_ref = %s", (ticket_ref,)
        )

        # Log creation event in history
        log_history(
            ticket_id=ticket["id"],
            changed_by=current_user["employee_name"],
            field="status",
            old_value=None,
            new_value="open",
            note="Ticket created",
        )

        return jsonify({
            "success":    True,
            "message":    "Ticket raised successfully.",
            "ticket_ref": ticket_ref,
            "ticket_id":  ticket["id"],
            "priority":   priority,
            "category":   CATEGORY_LABELS.get(category, category),
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /helpdesk/ — List tickets (RBAC scoped + filters)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/", methods=["GET"])
@token_required
def list_tickets(current_user):
    """
    Returns tickets based on role:
      - Employee: own tickets only
      - HR / Admin: all tickets
      - Manager: 403 — blocked by policy

    Query filters (all optional):
      ?status=open&priority=urgent&category=it_issue&search=vpn&assigned_to=H_Saurabh
    """
    try:


        filters = {
            "status":      request.args.get("status"),
            "priority":    request.args.get("priority"),
            "category":    request.args.get("category"),
            "search":      request.args.get("search"),
            "assigned_to": request.args.get("assigned_to"),
        }

        tickets = get_tickets(current_user, filters)

        return jsonify({
            "success": True,
            "count":   len(tickets),
            "tickets": tickets,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /helpdesk/stats — Dashboard counts (HR / Admin only)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/stats", methods=["GET"])
@role_required(["hr"])
def ticket_stats(current_user):
    """
    Returns aggregate counts for the Help Desk dashboard.
    Response includes counts by status and priority.
    """
    try:
        by_status = execute_query("""
            SELECT status, COUNT(*) AS count
            FROM helpdesk_tickets
            GROUP BY status
        """)

        by_priority = execute_query("""
            SELECT priority, COUNT(*) AS count
            FROM helpdesk_tickets
            WHERE status NOT IN ('resolved', 'closed')
            GROUP BY priority
        """)

        by_category = execute_query("""
            SELECT category, COUNT(*) AS count
            FROM helpdesk_tickets
            WHERE status NOT IN ('resolved', 'closed')
            GROUP BY category
        """)

        unassigned = execute_single("""
            SELECT COUNT(*) AS count FROM helpdesk_tickets
            WHERE assigned_to IS NULL AND status NOT IN ('resolved', 'closed')
        """)

        total = execute_single("SELECT COUNT(*) AS total FROM helpdesk_tickets")

        return jsonify({
            "success":     True,
            "total":       total["total"] if total else 0,
            "by_status":   {r["status"]:   r["count"] for r in by_status},
            "by_priority": {r["priority"]: r["count"] for r in by_priority},
            "by_category": {r["category"]: r["count"] for r in by_category},
            "unassigned":  unassigned["count"] if unassigned else 0,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /helpdesk/<id> — Get single ticket with inline history
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>", methods=["GET"])
@token_required
def get_ticket(current_user, ticket_id):
    """
    Returns a single ticket and its full audit history.
    Employees can only retrieve their own tickets.
    Managers are blocked entirely.
    """
    try:


        ticket = execute_single("""
            SELECT t.*, d.brand, d.model AS device_model 
            FROM helpdesk_tickets t
            LEFT JOIN devices d ON t.device_id = d.id
            WHERE t.id = %s
        """, (ticket_id,))
        
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404
        
        # Serialize datetime
        for k, v in ticket.items():
            if hasattr(v, "isoformat"):
                ticket[k] = v.isoformat()

        if not can_view_ticket(current_user, ticket):
            return jsonify({"success": False, "error": "Access denied"}), 403

        history = get_ticket_history(ticket_id)

        return jsonify({
            "success": True,
            "ticket":  ticket,
            "history": history,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /helpdesk/<id>/history — Full audit trail (HR / Admin only)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>/history", methods=["GET"])
@role_required(["hr"])
def get_ticket_history_route(current_user, ticket_id):
    """Returns the full immutable audit trail for a ticket."""
    try:
        ticket = get_ticket_or_404(ticket_id)
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        history = get_ticket_history(ticket_id)

        return jsonify({
            "success":    True,
            "ticket_ref": ticket["ticket_ref"],
            "history":    history,
            "count":      len(history),
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PATCH /helpdesk/<id>/status — Update ticket status (HR / Admin)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>/status", methods=["PATCH"])
@role_required(["hr"])
def update_status(current_user, ticket_id):
    """
    Update a ticket's status. Auto-sets resolved_at when status = 'resolved'.

    Payload: { "status": "in_progress", "note": "Looking into it now." }
    """
    try:
        data       = request.get_json() or {}
        new_status = data.get("status", "").lower()

        if new_status not in VALID_STATUSES:
            return jsonify({
                "success": False,
                "error": f"Invalid status. Choose from: {', '.join(sorted(VALID_STATUSES))}"
            }), 400

        ticket = get_ticket_or_404(ticket_id)
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        old_status = ticket["status"]
        if old_status == new_status:
            return jsonify({"success": True, "message": "No change — status is already set to that value."}), 200

        # Auto-set resolved_at when moving to resolved
        if new_status == "resolved":
            execute_query(
                "UPDATE helpdesk_tickets SET status = %s, resolved_at = NOW() WHERE id = %s",
                (new_status, ticket_id), commit=True
            )
        else:
            # Clear resolved_at if un-resolving
            execute_query(
                "UPDATE helpdesk_tickets SET status = %s, resolved_at = NULL WHERE id = %s",
                (new_status, ticket_id), commit=True
            )

        log_history(
            ticket_id=ticket_id,
            changed_by=current_user["employee_name"],
            field="status",
            old_value=old_status,
            new_value=new_status,
            note=data.get("note"),
        )

        return jsonify({
            "success": True,
            "message": f"Ticket {ticket['ticket_ref']} status updated: {old_status} → {new_status}",
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PATCH /helpdesk/<id>/assign — Assign ticket to a resolver (HR / Admin)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>/assign", methods=["PATCH"])
@role_required(["hr"])
def assign_ticket(current_user, ticket_id):
    """
    Assign a ticket to a resolver (HR/support staff).
    Also transitions status to 'in_progress' if currently 'open'.

    Payload: { "assigned_to": "H_Saurabh", "note": "Assigning to IT support." }
    """
    try:
        data        = request.get_json() or {}
        assigned_to = data.get("assigned_to", "").strip()

        if not assigned_to:
            return jsonify({"success": False, "error": "assigned_to is required"}), 400

        ticket = get_ticket_or_404(ticket_id)
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        old_assigned = ticket.get("assigned_to")
        old_status   = ticket["status"]

        # Auto-advance status open → in_progress on first assignment
        new_status = "in_progress" if old_status == "open" else old_status

        execute_query("""
            UPDATE helpdesk_tickets
            SET assigned_to = %s, status = %s
            WHERE id = %s
        """, (assigned_to, new_status, ticket_id), commit=True)

        log_history(
            ticket_id=ticket_id,
            changed_by=current_user["employee_name"],
            field="assigned_to",
            old_value=old_assigned,
            new_value=assigned_to,
            note=data.get("note"),
        )

        if old_status != new_status:
            log_history(
                ticket_id=ticket_id,
                changed_by=current_user["employee_name"],
                field="status",
                old_value=old_status,
                new_value=new_status,
                note="Auto-advanced on assignment",
            )

        # Notify the assignee
        execute_query("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, 'helpdesk')
        """, (
            assigned_to,
            f"Ticket Assigned: {ticket['ticket_ref']}",
            f"You have been assigned ticket {ticket['ticket_ref']}: \"{ticket['title']}\" "
            f"by {current_user['employee_name']}.",
        ), commit=True)

        return jsonify({
            "success": True,
            "message": f"Ticket {ticket['ticket_ref']} assigned to {assigned_to}.",
            "new_status": new_status,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PATCH /helpdesk/<id>/priority — Change priority (Admin only)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>/priority", methods=["PATCH"])
@role_required(["hr"])  # admin bypass handled in role_required middleware
def update_priority(current_user, ticket_id):
    """
    Change ticket priority. Admin-only (role_required + admin bypass in middleware).

    Payload: { "priority": "urgent", "note": "Escalated by CTO." }
    """
    try:
        # Additional check: only admin can change priority
        if current_user["role"] != "admin":
            return jsonify({
                "success": False,
                "error":   "Only admins can change ticket priority."
            }), 403

        data         = request.get_json() or {}
        new_priority = data.get("priority", "").lower()

        if new_priority not in VALID_PRIORITIES:
            return jsonify({
                "success": False,
                "error": f"Invalid priority. Choose from: {', '.join(sorted(VALID_PRIORITIES))}"
            }), 400

        ticket = get_ticket_or_404(ticket_id)
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        old_priority = ticket["priority"]
        if old_priority == new_priority:
            return jsonify({"success": True, "message": "Priority already set to that value."}), 200

        execute_query(
            "UPDATE helpdesk_tickets SET priority = %s WHERE id = %s",
            (new_priority, ticket_id), commit=True
        )

        log_history(
            ticket_id=ticket_id,
            changed_by=current_user["employee_name"],
            field="priority",
            old_value=old_priority,
            new_value=new_priority,
            note=data.get("note"),
        )

        return jsonify({
            "success": True,
            "message": f"Ticket {ticket['ticket_ref']} priority updated: {old_priority} → {new_priority}",
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# DELETE /helpdesk/<id> — Close / soft-delete a ticket (Admin only)
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>", methods=["DELETE"])
@role_required(["hr"])  # admin bypass handled in middleware
def delete_ticket(current_user, ticket_id):
    """
    Soft-deletes a ticket by setting status to 'closed'.
    Only admins may close tickets via DELETE (role enforced below).
    HR/Managers close through PATCH /status.
    """
    try:
        if current_user["role"] != "admin":
            return jsonify({
                "success": False,
                "error":   "Only admins can delete tickets. Use PATCH /<id>/status to close."
            }), 403

        ticket = get_ticket_or_404(ticket_id)
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        old_status = ticket["status"]

        execute_query(
            "UPDATE helpdesk_tickets SET status = 'closed', resolved_at = NOW() WHERE id = %s",
            (ticket_id,), commit=True
        )

        log_history(
            ticket_id=ticket_id,
            changed_by=current_user["employee_name"],
            field="status",
            old_value=old_status,
            new_value="closed",
            note="Closed by admin",
        )

        return jsonify({
            "success": True,
            "message": f"Ticket {ticket['ticket_ref']} has been closed.",
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /helpdesk/<id>/comments — Add a follow-up comment
# ---------------------------------------------------------------------------

@helpdesk_bp.route("/<int:ticket_id>/comments", methods=["POST"])
@token_required
def add_comment(current_user, ticket_id):
    """
    Add a follow-up comment to a ticket.
    Accessible to the owner (Employee/Manager) or HR/Admin.

    Payload: { "note": "Is there any update on this?", "status": "open" }
    """
    try:
        data = request.get_json() or {}
        note = data.get("note", "").strip()

        if not note:
            return jsonify({"success": False, "error": "Comment note is required"}), 400

        ticket = get_ticket_or_404(ticket_id)
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        # RBAC Check
        if not can_view_ticket(current_user, ticket):
            return jsonify({"success": False, "error": "Access denied"}), 403

        new_status = data.get("status")
        old_status = ticket["status"]

        if new_status and new_status != old_status:
            if new_status not in VALID_STATUSES:
                return jsonify({"success": False, "error": "Invalid status"}), 400
            
            # Only owner can re-open their own ticket if it was resolved/closed?
            # Or anyone with access can change status if they are staff.
            # For simplicity, if they have access to comment, they can suggest a status change.
            # But usually status change is restricted. 
            # Let's allow owners to re-open if they are commenting.
            
            execute_query(
                "UPDATE helpdesk_tickets SET status = %s WHERE id = %s",
                (new_status, ticket_id), commit=True
            )
            
            log_history(
                ticket_id=ticket_id,
                changed_by=current_user["employee_name"],
                field="status",
                old_value=old_status,
                new_value=new_status,
                note=f"Status changed via comment: {note}"
            )
        else:
            log_history(
                ticket_id=ticket_id,
                changed_by=current_user["employee_name"],
                field="comment",
                old_value=None,
                new_value="comment",
                note=note
            )

        return jsonify({
            "success": True,
            "message": "Comment added successfully.",
            "ticket_id": ticket_id
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
