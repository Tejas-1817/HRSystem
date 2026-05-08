import os
import logging
from datetime import date
from flask import Blueprint, request, jsonify, send_file
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required
from app.services.reimbursement_service import (
    generate_ref,
    save_receipt,
    log_history,
    get_reimbursements,
    get_reimbursement_or_404,
    get_reimbursement_history,
    can_view_reimbursement,
)

logger = logging.getLogger(__name__)
reimbursement_bp = Blueprint("reimbursements", __name__)

VALID_CATEGORIES = {"travel", "food", "accommodation", "office_supplies", "others"}
VALID_STATUSES   = {"pending", "approved", "rejected", "paid"}
STAFF_ROLES      = {"hr", "manager", "admin"}

CATEGORY_LABELS = {
    "travel":          "Travel",
    "food":            "Food",
    "accommodation":   "Accommodation",
    "office_supplies": "Office Supplies",
    "others":          "Others",
}


# ---------------------------------------------------------------------------
# POST /reimbursements/ — Submit expense claim (+ optional receipt upload)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/", methods=["POST"])
@token_required
def submit_claim(current_user):
    """
    Any authenticated user can submit a reimbursement claim.
    Supports both multipart/form-data (with receipt file) and JSON.

    Required fields: title, amount, expense_date, category
    Optional fields: description, currency, project_id, billable, receipt (file)

    Receipt rules: jpg/jpeg/png/pdf, max 5 MB.
    """
    try:
        is_multipart = request.content_type and "multipart" in request.content_type
        data         = request.form if is_multipart else (request.get_json(silent=True) or {})

        # ── Required field validation ─────────────────────────────────────
        required = ("title", "amount", "expense_date", "category")
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "error":   f"Missing required fields: {', '.join(missing)}"
            }), 400

        title        = str(data["title"]).strip()
        description  = str(data.get("description", "")).strip() or None
        currency     = str(data.get("currency", "INR")).strip().upper()
        expense_date = str(data["expense_date"]).strip()
        category     = str(data["category"]).strip().lower()
        project_id   = data.get("project_id") or None
        billable     = str(data.get("billable", "false")).lower() in ("true", "1", "yes")

        # Validate amount
        try:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "amount must be a positive number."}), 400

        # Validate date format
        try:
            from datetime import datetime
            datetime.strptime(expense_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False,
                            "error": "expense_date must be in YYYY-MM-DD format."}), 400

        if category not in VALID_CATEGORIES:
            return jsonify({
                "success": False,
                "error":   f"Invalid category. Choose from: {', '.join(sorted(VALID_CATEGORIES))}"
            }), 400

        # ── Receipt file handling ─────────────────────────────────────────
        receipt_path = None
        receipt_file = request.files.get("receipt") if is_multipart else None
        if receipt_file and receipt_file.filename:
            try:
                receipt_path = save_receipt(receipt_file, current_user["employee_name"])
            except ValueError as ve:
                return jsonify({"success": False, "error": str(ve)}), 400

        # ── Determine employee (staff can submit on behalf) ───────────────
        if current_user["role"] == "employee":
            employee_name = current_user["employee_name"]
        else:
            employee_name = data.get("employee_name", current_user["employee_name"])

        # ── Insert record ─────────────────────────────────────────────────
        ref = generate_ref()
        execute_query("""
            INSERT INTO reimbursements
                (ref, employee_name, title, description, amount, currency,
                 expense_date, category, receipt_file, project_id, billable)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (ref, employee_name, title, description, amount, currency,
              expense_date, category, receipt_path, project_id, billable),
             commit=True)

        record = execute_single("SELECT id FROM reimbursements WHERE ref = %s", (ref,))

        # Log creation in history
        log_history(
            reimbursement_id=record["id"],
            changed_by=current_user["employee_name"],
            field="status",
            old_value=None,
            new_value="pending",
            note="Expense claim submitted",
        )

        return jsonify({
            "success":          True,
            "message":          "Expense claim submitted successfully.",
            "reimbursement_ref": ref,
            "reimbursement_id": record["id"],
            "amount":           amount,
            "currency":         currency,
            "category":         CATEGORY_LABELS.get(category, category),
            "has_receipt":      receipt_path is not None,
        }), 201

    except Exception as e:
        logger.error(f"Error submitting reimbursement: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /reimbursements/ — List (RBAC scoped + filters)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/", methods=["GET"])
@token_required
def list_reimbursements(current_user):
    """
    Returns reimbursements based on role:
      - Employee: own records only
      - Manager / HR / Admin: all records

    Query filters (all optional):
      ?status=pending&category=travel&employee_name=T_Raj
      &project_id=1&from_date=2026-01-01&to_date=2026-04-30
    """
    try:
        filters = {
            "status":        request.args.get("status"),
            "category":      request.args.get("category"),
            "employee_name": request.args.get("employee_name"),
            "project_id":    request.args.get("project_id"),
            "from_date":     request.args.get("from_date"),
            "to_date":       request.args.get("to_date"),
        }

        records = get_reimbursements(current_user, filters)

        return jsonify({
            "success": True,
            "count":   len(records),
            "reimbursements": records,
        }), 200

    except Exception as e:
        logger.error(f"Error listing reimbursements: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /reimbursements/stats — Dashboard totals (Manager / HR / Admin)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/stats", methods=["GET"])
@role_required(["hr", "manager"])
def reimbursement_stats(current_user):
    """
    Returns aggregate totals for the reimbursement dashboard.
    """
    try:
        by_status = execute_query("""
            SELECT status, COUNT(*) AS count, SUM(amount) AS total_amount
            FROM reimbursements GROUP BY status
        """)

        by_category = execute_query("""
            SELECT category, COUNT(*) AS count, SUM(amount) AS total_amount
            FROM reimbursements WHERE status != 'rejected' GROUP BY category
        """)

        pending_total = execute_single("""
            SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total
            FROM reimbursements WHERE status = 'pending'
        """)

        approved_unpaid = execute_single("""
            SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total
            FROM reimbursements WHERE status = 'approved' AND payment_status = 'pending'
        """)

        return jsonify({
            "success":          True,
            "by_status":        {r["status"]: {"count": r["count"],
                                               "total_amount": float(r["total_amount"] or 0)}
                                 for r in by_status},
            "by_category":      {r["category"]: {"count": r["count"],
                                                 "total_amount": float(r["total_amount"] or 0)}
                                 for r in by_category},
            "pending_approval": {
                "count": pending_total["count"] if pending_total else 0,
                "total": float(pending_total["total"]) if pending_total else 0,
            },
            "approved_unpaid":  {
                "count": approved_unpaid["count"] if approved_unpaid else 0,
                "total": float(approved_unpaid["total"]) if approved_unpaid else 0,
            },
        }), 200

    except Exception as e:
        logger.error(f"Error fetching reimbursement stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /reimbursements/<id> — Single claim with inline history
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>", methods=["GET"])
@token_required
def get_reimbursement(current_user, record_id):
    """
    Returns a single reimbursement with its full audit history.
    Employees may only retrieve their own records.
    """
    try:
        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        if not can_view_reimbursement(current_user, record):
            return jsonify({"success": False, "error": "Access denied"}), 403

        history = get_reimbursement_history(record_id)

        return jsonify({
            "success":       True,
            "reimbursement": record,
            "history":       history,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching reimbursement {record_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# PATCH /reimbursements/<id>/approve — Approve claim (Manager / HR / Admin)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>/approve", methods=["PATCH"])
@role_required(["hr", "manager"])
def approve_reimbursement(current_user, record_id):
    """
    Approve an expense claim.
    Only pending claims can be approved.

    Payload (optional): { "note": "Approved. Will be processed in next payroll." }
    """
    try:
        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        if record["status"] != "pending":
            return jsonify({
                "success": False,
                "error":   f"Cannot approve — current status is '{record['status']}'. "
                           "Only pending claims can be approved."
            }), 400

        data = request.get_json(silent=True) or {}

        execute_query("""
            UPDATE reimbursements
            SET status = 'approved', approved_by = %s, approved_at = NOW()
            WHERE id = %s
        """, (current_user["employee_name"], record_id), commit=True)

        log_history(
            reimbursement_id=record_id,
            changed_by=current_user["employee_name"],
            field="status",
            old_value="pending",
            new_value="approved",
            note=data.get("note"),
        )

        # Notify the employee
        try:
            execute_query("""
                INSERT INTO notifications (employee_name, title, message, type)
                VALUES (%s, %s, %s, 'reimbursement')
            """, (
                record["employee_name"],
                f"Expense Claim Approved: {record['ref']}",
                f"Your expense claim '{record['title']}' ({record['ref']}) of "
                f"{record['currency']} {record['amount']} has been approved "
                f"by {current_user['employee_name']}.",
            ), commit=True)
        except Exception:
            pass  # Notification failure must not block approval

        return jsonify({
            "success": True,
            "message": f"Claim {record['ref']} approved successfully.",
        }), 200

    except Exception as e:
        logger.error(f"Error approving reimbursement {record_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# PATCH /reimbursements/<id>/reject — Reject claim (Manager / HR / Admin)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>/reject", methods=["PATCH"])
@role_required(["hr", "manager"])
def reject_reimbursement(current_user, record_id):
    """
    Reject an expense claim with a mandatory reason.
    Only pending or approved claims can be rejected.

    Payload: { "reason": "Receipt is missing / not valid.", "note": "..." }
    """
    try:
        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        if record["status"] not in ("pending", "approved"):
            return jsonify({
                "success": False,
                "error":   f"Cannot reject — current status is '{record['status']}'."
            }), 400

        data   = request.get_json(silent=True) or {}
        reason = str(data.get("reason", "")).strip()

        if not reason:
            return jsonify({
                "success": False,
                "error":   "rejection_reason is mandatory. Please provide a reason."
            }), 400

        old_status = record["status"]

        execute_query("""
            UPDATE reimbursements
            SET status = 'rejected', rejection_reason = %s
            WHERE id = %s
        """, (reason, record_id), commit=True)

        log_history(
            reimbursement_id=record_id,
            changed_by=current_user["employee_name"],
            field="status",
            old_value=old_status,
            new_value="rejected",
            note=f"Reason: {reason}",
        )

        # Notify the employee
        try:
            execute_query("""
                INSERT INTO notifications (employee_name, title, message, type)
                VALUES (%s, %s, %s, 'reimbursement')
            """, (
                record["employee_name"],
                f"Expense Claim Rejected: {record['ref']}",
                f"Your expense claim '{record['title']}' ({record['ref']}) has been rejected. "
                f"Reason: {reason}",
            ), commit=True)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": f"Claim {record['ref']} rejected.",
        }), 200

    except Exception as e:
        logger.error(f"Error rejecting reimbursement {record_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# PATCH /reimbursements/<id>/pay — Mark as paid (Admin only)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>/pay", methods=["PATCH"])
@role_required(["hr", "manager"])   # admin bypass handled in middleware
def mark_paid(current_user, record_id):
    """
    Mark an approved claim as paid. Admin-only.

    Payload (optional): { "payment_date": "2026-04-30", "note": "Bank transfer ref: TXN123" }
    """
    try:
        # Only admin can mark as paid (HR/Manager bypass comes from decorator, extra check below)
        if current_user["role"] != "admin":
            return jsonify({
                "success": False,
                "error":   "Only Admin can mark claims as paid."
            }), 403

        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        if record["status"] != "approved":
            return jsonify({
                "success": False,
                "error":   f"Cannot mark as paid — status is '{record['status']}'. "
                           "Only approved claims can be paid."
            }), 400

        data         = request.get_json(silent=True) or {}
        payment_date = data.get("payment_date") or date.today().isoformat()

        # Validate payment date format
        try:
            from datetime import datetime
            datetime.strptime(payment_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False,
                            "error": "payment_date must be YYYY-MM-DD."}), 400

        execute_query("""
            UPDATE reimbursements
            SET status = 'paid', payment_status = 'processed', payment_date = %s
            WHERE id = %s
        """, (payment_date, record_id), commit=True)

        log_history(
            reimbursement_id=record_id,
            changed_by=current_user["employee_name"],
            field="payment_status",
            old_value="pending",
            new_value="processed",
            note=data.get("note", f"Payment date: {payment_date}"),
        )
        log_history(
            reimbursement_id=record_id,
            changed_by=current_user["employee_name"],
            field="status",
            old_value="approved",
            new_value="paid",
            note=None,
        )

        # Notify the employee
        try:
            execute_query("""
                INSERT INTO notifications (employee_name, title, message, type)
                VALUES (%s, %s, %s, 'reimbursement')
            """, (
                record["employee_name"],
                f"Expense Reimbursed: {record['ref']}",
                f"Your expense claim '{record['title']}' ({record['ref']}) of "
                f"{record['currency']} {record['amount']} has been paid on {payment_date}.",
            ), commit=True)
        except Exception:
            pass

        return jsonify({
            "success":      True,
            "message":      f"Claim {record['ref']} marked as paid.",
            "payment_date": payment_date,
        }), 200

    except Exception as e:
        logger.error(f"Error marking reimbursement {record_id} as paid: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /reimbursements/<id>/history — Full audit trail (Manager / HR / Admin)
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>/history", methods=["GET"])
@role_required(["hr", "manager"])
def get_history(current_user, record_id):
    """Returns the full immutable audit trail for a reimbursement claim."""
    try:
        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        history = get_reimbursement_history(record_id)

        return jsonify({
            "success": True,
            "ref":     record["ref"],
            "history": history,
            "count":   len(history),
        }), 200

    except Exception as e:
        logger.error(f"Error fetching history for reimbursement {record_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /reimbursements/<id>/receipt — Download receipt file
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>/receipt", methods=["GET"])
@token_required
def download_receipt(current_user, record_id):
    """
    Download the uploaded receipt for a reimbursement.
    Employees may only download receipts for their own claims.
    """
    try:
        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        if not can_view_reimbursement(current_user, record):
            return jsonify({"success": False, "error": "Access denied"}), 403

        if not record.get("receipt_file"):
            return jsonify({"success": False, "error": "No receipt attached to this claim."}), 404

        file_path = record["receipt_file"]
        if not os.path.exists(file_path):
            return jsonify({"success": False,
                            "error": "Receipt file not found on server."}), 404

        return send_file(
            os.path.abspath(file_path),
            as_attachment=True,
            download_name=os.path.basename(file_path),
        )

    except Exception as e:
        logger.error(f"Error downloading receipt for {record_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# DELETE /reimbursements/<id> — Withdraw (employee, pending only) / Admin delete
# ---------------------------------------------------------------------------

@reimbursement_bp.route("/<int:record_id>", methods=["DELETE"])
@token_required
def delete_reimbursement(current_user, record_id):
    """
    - Employee: can withdraw their own PENDING claim only.
    - Admin: can delete any claim (hard delete with history cascade).
    - Others: 403.
    """
    try:
        record = get_reimbursement_or_404(record_id)
        if not record:
            return jsonify({"success": False, "error": "Reimbursement not found"}), 404

        role = current_user["role"]

        # Employee: may only withdraw own pending claims
        if role == "employee":
            if record["employee_name"] != current_user["employee_name"]:
                return jsonify({"success": False, "error": "Access denied"}), 403
            if record["status"] != "pending":
                return jsonify({
                    "success": False,
                    "error":   f"Cannot withdraw — claim is already '{record['status']}'. "
                               "Only pending claims can be withdrawn."
                }), 400

            # Log withdrawal first, then delete
            log_history(
                reimbursement_id=record_id,
                changed_by=current_user["employee_name"],
                field="status",
                old_value="pending",
                new_value="withdrawn",
                note="Claim withdrawn by employee",
            )
            execute_query("DELETE FROM reimbursements WHERE id = %s", (record_id,), commit=True)
            return jsonify({"success": True,
                            "message": f"Claim {record['ref']} withdrawn successfully."}), 200

        # Admin: can delete any record
        if role == "admin":
            execute_query("DELETE FROM reimbursements WHERE id = %s", (record_id,), commit=True)
            return jsonify({"success": True,
                            "message": f"Claim {record['ref']} deleted by admin."}), 200

        # All other roles: blocked
        return jsonify({
            "success": False,
            "error":   "Access denied. Only Admin can delete claims. "
                       "Employees may withdraw their own pending claims."
        }), 403

    except Exception as e:
        logger.error(f"Error deleting reimbursement {record_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500
