from flask import Blueprint, request, jsonify, send_from_directory
import os
import logging
from datetime import datetime
from app.config import Config
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required
from app.utils.helpers import log_audit_event

logger = logging.getLogger(__name__)
document_bp = Blueprint('documents', __name__)

# Valid document types that the UI supports
VALID_DOC_TYPES = {
    "pan_card",
    "aadhar_card",
    "tenth_cert",
    "twelfth_cert",
    "graduation_cert",
    "post_graduation_cert",
    "offer_letter",
    "relieving_letter",
    "experience_letter",
    "other",
}


# ---------------------------------------------------------------------------
# POST /documents/upload — Upload or replace a document
# ---------------------------------------------------------------------------

@document_bp.route("/upload", methods=["POST"])
@token_required
def upload_document(current_user):
    """
    Upload or replace an employee document.

    Accepts multipart/form-data with:
      - 'file'     : the document file (PDF, DOCX, DOC — max 10 MB)
      - 'doc_type' : one of VALID_DOC_TYPES (e.g. 'pan_card', 'aadhar_card')
      - 'employee_name' (optional, HR/Admin only): upload on behalf of another employee

    Employees can only upload their own documents.
    HR and Admin can upload for any employee.
    """
    try:
        from app.utils.file_upload import save_upload, ALLOWED_DOC_EXTENSIONS

        # ── 1. Determine target employee ──────────────────────────────────
        if current_user["role"] in ("hr", "admin"):
            employee_name = request.form.get("employee_name") or current_user["employee_name"]
        else:
            # Employees cannot upload for others
            requested_name = request.form.get("employee_name")
            if requested_name and requested_name != current_user["employee_name"]:
                return jsonify({"success": False, "error": "Access denied. You can only upload your own documents."}), 403
            employee_name = current_user["employee_name"]

        # ── 2. Validate doc_type ──────────────────────────────────────────
        doc_type = request.form.get("doc_type", "").strip().lower()
        if not doc_type:
            return jsonify({"success": False, "error": "'doc_type' is required. Example: pan_card, aadhar_card"}), 400
        if doc_type not in VALID_DOC_TYPES:
            return jsonify({
                "success": False,
                "error": f"Invalid doc_type '{doc_type}'. Allowed: {', '.join(sorted(VALID_DOC_TYPES))}"
            }), 400

        # ── 3. Validate file ──────────────────────────────────────────────
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No 'file' provided in request. Use multipart/form-data."}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"success": False, "error": "Empty filename. Please select a file."}), 400

        # ── 4. Save file to disk ──────────────────────────────────────────
        # save_upload handles extension validation, size check, UUID naming
        file_path = save_upload(file, folder="documents", allowed=ALLOWED_DOC_EXTENSIONS)

        # ── 5. Delete old file from disk if replacing ─────────────────────
        existing = execute_single(
            "SELECT id, file_path FROM employee_documents WHERE employee_name = %s AND doc_type = %s",
            (employee_name, doc_type)
        )
        if existing and existing.get("file_path"):
            old_path = existing["file_path"].lstrip("/")
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    logger.warning(f"Could not remove old document file: {old_path}")

        # ── 6. Upsert into employee_documents ─────────────────────────────
        # Use INSERT … ON DUPLICATE KEY UPDATE so re-upload replaces cleanly
        execute_query(
            """
            INSERT INTO employee_documents
                (employee_name, doc_type, file_path, status, uploaded_at, updated_at)
            VALUES
                (%s, %s, %s, 'uploaded', NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                file_path    = VALUES(file_path),
                status       = 'uploaded',
                verified_by  = NULL,
                verified_at  = NULL,
                rejection_reason = NULL,
                updated_at   = NOW()
            """,
            (employee_name, doc_type, file_path),
            commit=True
        )

        # ── 7. Audit log ──────────────────────────────────────────────────
        log_audit_event(
            current_user["user_id"],
            "document_upload",
            f"{current_user['employee_name']} uploaded '{doc_type}' for employee '{employee_name}'"
        )

        logger.info(f"Document '{doc_type}' uploaded for '{employee_name}' → {file_path}")

        return jsonify({
            "success": True,
            "message": f"Document '{doc_type}' uploaded successfully. Pending HR verification.",
            "doc_type": doc_type,
            "employee_name": employee_name,
            "file_path": file_path,
            "status": "uploaded",
        }), 201

    except ValueError as e:
        # Raised by save_upload for invalid extension or size
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Document upload error: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /documents/my-status — Employee views their own document statuses
# ---------------------------------------------------------------------------

@document_bp.route("/my-status", methods=["GET"])
@token_required
def get_my_status(current_user):
    """Returns document upload statuses for the logged-in employee."""
    try:
        rows = execute_query(
            "SELECT id, doc_type, status, uploaded_at, verified_by, verified_at, rejection_reason "
            "FROM employee_documents WHERE employee_name = %s ORDER BY doc_type",
            (current_user["employee_name"],)
        )
        # Serialize datetime fields
        for r in rows:
            for field in ("uploaded_at", "verified_at"):
                if r.get(field) and hasattr(r[field], "isoformat"):
                    r[field] = r[field].isoformat()
        return jsonify({"success": True, "documents": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /documents/<int:emp_id>/status — HR views any employee's doc statuses
# ---------------------------------------------------------------------------

@document_bp.route("/<int:emp_id>/status", methods=["GET"])
@role_required(["hr", "admin"])
def get_employee_doc_status(current_user, emp_id):
    """HR/Admin: view document statuses for any employee by their DB id."""
    try:
        emp = execute_single("SELECT name FROM employee WHERE id = %s", (emp_id,))
        if not emp:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        rows = execute_query(
            "SELECT id, doc_type, status, uploaded_at, verified_by, verified_at, rejection_reason "
            "FROM employee_documents WHERE employee_name = %s ORDER BY doc_type",
            (emp["name"],)
        )
        for r in rows:
            for field in ("uploaded_at", "verified_at"):
                if r.get(field) and hasattr(r[field], "isoformat"):
                    r[field] = r[field].isoformat()
        return jsonify({"success": True, "employee_name": emp["name"], "documents": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /documents/pending-review — HR views all documents awaiting verification
# ---------------------------------------------------------------------------

@document_bp.route("/pending-review", methods=["GET"])
@role_required(["hr"])
def get_pending_documents(current_user):
    try:
        rows = execute_query(
            "SELECT * FROM employee_documents WHERE status IN ('pending', 'uploaded') ORDER BY uploaded_at DESC"
        )
        for r in rows:
            for field in ("uploaded_at", "verified_at", "updated_at"):
                if r.get(field) and hasattr(r[field], "isoformat"):
                    r[field] = r[field].isoformat()
        return jsonify({"success": True, "pending_documents": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PUT /documents/verify/<int:doc_id> — HR verifies a document
# ---------------------------------------------------------------------------

@document_bp.route("/verify/<int:doc_id>", methods=["PUT"])
@role_required(["hr"])
def verify_document(current_user, doc_id):
    try:
        doc = execute_single("SELECT id, employee_name, doc_type FROM employee_documents WHERE id = %s", (doc_id,))
        if not doc:
            return jsonify({"success": False, "error": "Document not found"}), 404

        execute_query(
            "UPDATE employee_documents SET status='verified', verified_by=%s, verified_at=NOW(), rejection_reason=NULL WHERE id=%s",
            (current_user["employee_name"], doc_id),
            commit=True
        )
        log_audit_event(current_user["user_id"], "document_verified",
                        f"HR '{current_user['employee_name']}' verified '{doc['doc_type']}' for '{doc['employee_name']}'")
        return jsonify({"success": True, "message": "Document verified successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# PUT /documents/reject/<int:doc_id> — HR rejects a document with a reason
# ---------------------------------------------------------------------------

@document_bp.route("/reject/<int:doc_id>", methods=["PUT"])
@role_required(["hr"])
def reject_document(current_user, doc_id):
    try:
        data = request.get_json() or {}
        reason = data.get("rejection_reason", "").strip()
        if not reason:
            return jsonify({"success": False, "error": "'rejection_reason' is required when rejecting a document"}), 400

        doc = execute_single("SELECT id, employee_name, doc_type FROM employee_documents WHERE id = %s", (doc_id,))
        if not doc:
            return jsonify({"success": False, "error": "Document not found"}), 404

        execute_query(
            "UPDATE employee_documents SET status='rejected', rejection_reason=%s, verified_by=%s, verified_at=NOW() WHERE id=%s",
            (reason, current_user["employee_name"], doc_id),
            commit=True
        )
        log_audit_event(current_user["user_id"], "document_rejected",
                        f"HR '{current_user['employee_name']}' rejected '{doc['doc_type']}' for '{doc['employee_name']}': {reason}")
        return jsonify({"success": True, "message": "Document rejected"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /documents/download/<int:doc_id> — Download a document file
# ---------------------------------------------------------------------------

@document_bp.route("/download/<int:doc_id>", methods=["GET"])
@token_required
def download_document(current_user, doc_id):
    try:
        doc = execute_single("SELECT * FROM employee_documents WHERE id = %s", (doc_id,))
        if not doc:
            return jsonify({"success": False, "error": "Document not found"}), 404

        # RBAC: employees can only download their own documents
        if current_user["role"] == "employee" and doc["employee_name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied"}), 403

        if not doc.get("file_path"):
            return jsonify({"success": False, "error": "No file associated with this document record"}), 404

        file_path = doc["file_path"].lstrip("/")
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        if not os.path.isfile(file_path):
            return jsonify({"success": False, "error": "File not found on server"}), 404

        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Document download error for doc_id={doc_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# DELETE /documents/<int:doc_id> — Employee deletes their own document
# ---------------------------------------------------------------------------

@document_bp.route("/<int:doc_id>", methods=["DELETE"])
@token_required
def delete_document(current_user, doc_id):
    """
    Delete a document record and its file.
    Employees can only delete their own documents.
    HR/Admin can delete any document.
    """
    try:
        doc = execute_single("SELECT * FROM employee_documents WHERE id = %s", (doc_id,))
        if not doc:
            return jsonify({"success": False, "error": "Document not found"}), 404

        # RBAC
        if current_user["role"] == "employee" and doc["employee_name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Delete file from disk
        if doc.get("file_path"):
            file_path = doc["file_path"].lstrip("/")
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    logger.warning(f"Could not delete document file: {file_path}")

        execute_query("DELETE FROM employee_documents WHERE id = %s", (doc_id,), commit=True)
        log_audit_event(current_user["user_id"], "document_deleted",
                        f"'{current_user['employee_name']}' deleted '{doc['doc_type']}' for '{doc['employee_name']}'")

        return jsonify({"success": True, "message": "Document deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Document delete error for doc_id={doc_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

