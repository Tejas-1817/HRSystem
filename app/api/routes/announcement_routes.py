import os
import logging
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from app.models.database import execute_query, execute_single, Transaction
from app.api.middleware.auth import token_required, role_required
from app.utils.helpers import log_audit_event
from app.services.announcement_service import (
    save_attachment,
    sanitize_html,
    get_announcements_paginated
)

logger = logging.getLogger(__name__)
announcement_bp = Blueprint("announcements", __name__)


# ---------------------------------------------------------------------------
# POST /announcements/ — Create (HR / Admin only)
# ---------------------------------------------------------------------------

@announcement_bp.route("/", methods=["POST"])
@role_required(["hr"])
def create_announcement(current_user):
    """
    Creates a new company announcement.
    Supports JSON or multipart/form-data (with attachment file).

    Required: title, description, expires_at
    Optional: status ('draft' | 'published', default 'published'), attachment (file)
    """
    try:
        is_multipart = request.content_type and "multipart" in request.content_type
        data = request.form if is_multipart else (request.get_json(silent=True) or {})

        # Validation
        required = ("title", "description", "expires_at")
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400

        title = str(data["title"]).strip()
        description = str(data["description"]).strip()
        expires_at_str = str(data["expires_at"]).strip()
        status = str(data.get("status", "published")).strip().lower()

        if not title or not description:
            return jsonify({"success": False, "error": "Title and description cannot be empty."}), 400

        if status not in ("draft", "published"):
            return jsonify({"success": False, "error": "Status must be 'draft' or 'published'."}), 400

        # Validate expires_at is a future date
        try:
            # Supports both date and datetime formats
            try:
                expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d")
            
            if expires_at <= datetime.now():
                return jsonify({"success": False, "error": "Expiration date must be in the future."}), 400
        except ValueError:
            return jsonify({
                "success": False,
                "error": "expires_at must be in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format."
            }), 400

        # HTML XSS Sanitization
        sanitized_title = sanitize_html(title)
        sanitized_description = sanitize_html(description)

        # File attachment handling
        attachment_path = None
        attachment_file = request.files.get("attachment") if is_multipart else None
        if attachment_file and attachment_file.filename:
            try:
                attachment_path = save_attachment(attachment_file, current_user["username"])
            except ValueError as ve:
                return jsonify({"success": False, "error": str(ve)}), 400

        # Database Insertion
        with Transaction() as cursor:
            cursor.execute("""
                INSERT INTO announcements (title, description, status, attachment_path, created_by, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sanitized_title, sanitized_description, status, attachment_path, current_user["username"], expires_at))
            
            new_id = cursor.lastrowid

        # Audit Event Logging
        log_audit_event(current_user["user_id"], "announcement_create", f"Announcement '{sanitized_title}' (ID: {new_id}) created.")

        return jsonify({
            "success": True,
            "message": "Announcement created successfully.",
            "announcement_id": new_id,
            "status": status,
            "has_attachment": attachment_path is not None
        }), 201

    except Exception as e:
        logger.error(f"Error creating announcement: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /announcements/ — List (RBAC scoped with Pagination)
# ---------------------------------------------------------------------------

@announcement_bp.route("/", methods=["GET"])
@token_required
def list_announcements(current_user):
    """
    Returns a paginated list of announcements.
    Scoped by roles:
      - Employees & Managers: only active & published announcements.
      - HR & Admins: all announcements with optional filters.
    """
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        
        filters = {
            "status": request.args.get("status"),
            "active_only": request.args.get("active_only"),
            "expired_only": request.args.get("expired_only"),
            "q": request.args.get("q")
        }

        result = get_announcements_paginated(current_user["role"], filters, page, limit)
        return jsonify({
            "success": True,
            **result
        }), 200

    except ValueError:
        return jsonify({"success": False, "error": "Invalid pagination parameters."}), 400
    except Exception as e:
        logger.error(f"Error listing announcements: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /announcements/dashboard — Widget payload (All authenticated users)
# ---------------------------------------------------------------------------

@announcement_bp.route("/dashboard", methods=["GET"])
@token_required
def dashboard_widget(current_user):
    """
    Dashboard announcement widget integration:
    Returns the latest 5 active published announcements, sorted newest first.
    Fields: id, title, created_at, created_by, short_description preview, has_attachment.
    """
    try:
        rows = execute_query("""
            SELECT id, title, description, created_by, created_at, expires_at, attachment_path
            FROM announcements
            WHERE status = 'published' AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 5
        """)

        announcements = []
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat()
            
            # Extract plain text short preview
            desc_stripped = re.sub(r'<[^<]+?>', '', r["description"]) if '<' in r["description"] else r["description"]
            short_preview = desc_stripped[:120] + "..." if len(desc_stripped) > 120 else desc_stripped
            
            announcements.append({
                "id": r["id"],
                "title": r["title"],
                "created_by": r["created_by"],
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
                "short_description": short_preview,
                "has_attachment": r["attachment_path"] is not None
            })

        return jsonify({
            "success": True,
            "count": len(announcements),
            "announcements": announcements,
            "empty_state": len(announcements) == 0,
            "message": "No new announcements" if len(announcements) == 0 else "Active announcements loaded successfully."
        }), 200

    except Exception as e:
        logger.error(f"Error fetching dashboard widget announcements: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /announcements/<id> — Single Announcement Detail
# ---------------------------------------------------------------------------

@announcement_bp.route("/<int:announcement_id>", methods=["GET"])
@token_required
def get_announcement(current_user, announcement_id):
    """
    Fetches the details of a single announcement.
    RBAC protection enforces that Employees/Managers cannot access draft/expired announcements.
    """
    try:
        row = execute_single("SELECT * FROM announcements WHERE id = %s", (announcement_id,))
        if not row:
            return jsonify({"success": False, "error": "Announcement not found."}), 404

        role = current_user["role"]
        
        # Scope protection for Employees and Managers
        if role in ("employee", "manager"):
            is_published = row["status"] == "published"
            is_not_expired = row["expires_at"] > datetime.now()
            if not is_published or not is_not_expired:
                return jsonify({"success": False, "error": "Access denied."}), 403

        # Convert Datetime to ISO format
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()

        return jsonify({
            "success": True,
            "announcement": row
        }), 200

    except Exception as e:
        logger.error(f"Error getting announcement {announcement_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# GET /announcements/<id>/attachment — Download attachment
# ---------------------------------------------------------------------------

@announcement_bp.route("/<int:announcement_id>/attachment", methods=["GET"])
@token_required
def download_announcement_attachment(current_user, announcement_id):
    """
    Allows authenticated users to download announcement attachments.
    Ensures same RBAC visibility boundaries as detail API.
    """
    try:
        row = execute_single("SELECT status, expires_at, attachment_path FROM announcements WHERE id = %s", (announcement_id,))
        if not row:
            return jsonify({"success": False, "error": "Announcement not found."}), 404

        role = current_user["role"]

        # Scope protection for Employees and Managers
        if role in ("employee", "manager"):
            is_published = row["status"] == "published"
            is_not_expired = row["expires_at"] > datetime.now()
            if not is_published or not is_not_expired:
                return jsonify({"success": False, "error": "Access denied."}), 403

        attachment_path = row.get("attachment_path")
        if not attachment_path:
            return jsonify({"success": False, "error": "No attachment attached to this announcement."}), 404

        if not os.path.exists(attachment_path):
            return jsonify({"success": False, "error": "Attachment file not found on the server."}), 404

        return send_file(
            os.path.abspath(attachment_path),
            as_attachment=True,
            download_name=os.path.basename(attachment_path)
        )

    except Exception as e:
        logger.error(f"Error downloading attachment for announcement {announcement_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# PUT /announcements/<id> — Update (HR / Admin only)
# ---------------------------------------------------------------------------

@announcement_bp.route("/<int:announcement_id>", methods=["PUT"])
@role_required(["hr"])
def update_announcement(current_user, announcement_id):
    """
    Updates fields of an existing announcement.
    Supports JSON or multipart/form-data (with attachment file).
    """
    try:
        row = execute_single("SELECT * FROM announcements WHERE id = %s", (announcement_id,))
        if not row:
            return jsonify({"success": False, "error": "Announcement not found."}), 404

        is_multipart = request.content_type and "multipart" in request.content_type
        data = request.form if is_multipart else (request.get_json(silent=True) or {})

        title = data.get("title")
        description = data.get("description")
        expires_at_str = data.get("expires_at")
        status = data.get("status")

        # Keep existing fields by default
        updated_title = sanitize_html(str(title).strip()) if title is not None else row["title"]
        updated_description = sanitize_html(str(description).strip()) if description is not None else row["description"]
        updated_status = str(status).strip().lower() if status is not None else row["status"]

        if updated_status not in ("draft", "published"):
            return jsonify({"success": False, "error": "Status must be 'draft' or 'published'."}), 400

        updated_expires_at = row["expires_at"]
        if expires_at_str is not None:
            expires_at_str = str(expires_at_str).strip()
            try:
                try:
                    updated_expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    updated_expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d")
                
                if updated_expires_at <= datetime.now():
                    return jsonify({"success": False, "error": "Expiration date must be in the future."}), 400
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "expires_at must be in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format."
                }), 400

        # File attachment update
        updated_attachment_path = row["attachment_path"]
        attachment_file = request.files.get("attachment") if is_multipart else None
        if attachment_file and attachment_file.filename:
            try:
                # Save new file
                new_path = save_attachment(attachment_file, current_user["username"])
                
                # Delete old file if existed
                if updated_attachment_path and os.path.exists(updated_attachment_path):
                    try:
                        os.remove(updated_attachment_path)
                    except OSError:
                        pass
                
                updated_attachment_path = new_path
            except ValueError as ve:
                return jsonify({"success": False, "error": str(ve)}), 400

        # Perform DB Update
        execute_query("""
            UPDATE announcements
            SET title = %s, description = %s, status = %s, attachment_path = %s, expires_at = %s, updated_by = %s
            WHERE id = %s
        """, (updated_title, updated_description, updated_status, updated_attachment_path, updated_expires_at, current_user["username"], announcement_id), commit=True)

        # Audit Event Logging
        log_audit_event(current_user["user_id"], "announcement_update", f"Announcement ID {announcement_id} updated.")

        return jsonify({
            "success": True,
            "message": "Announcement updated successfully.",
            "status": updated_status
        }), 200

    except Exception as e:
        logger.error(f"Error updating announcement {announcement_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# DELETE /announcements/<id> — Delete (HR / Admin only)
# ---------------------------------------------------------------------------

@announcement_bp.route("/<int:announcement_id>", methods=["DELETE"])
@role_required(["hr"])
def delete_announcement(current_user, announcement_id):
    """
    Deletes an existing announcement completely.
    Cleans up associated file attachment from the file system.
    """
    try:
        row = execute_single("SELECT title, attachment_path FROM announcements WHERE id = %s", (announcement_id,))
        if not row:
            return jsonify({"success": False, "error": "Announcement not found."}), 404

        # Delete database entry
        execute_query("DELETE FROM announcements WHERE id = %s", (announcement_id,), commit=True)

        # Clean up attachment file from disk
        attachment_path = row.get("attachment_path")
        if attachment_path and os.path.exists(attachment_path):
            try:
                os.remove(attachment_path)
                logger.info(f"Deleted orphan announcement attachment file: {attachment_path}")
            except OSError as ex:
                logger.error(f"Error removing deleted announcement attachment file: {ex}")

        # Audit Event Logging
        log_audit_event(current_user["user_id"], "announcement_delete", f"Announcement ID {announcement_id} ('{row['title']}') deleted.")

        return jsonify({
            "success": True,
            "message": "Announcement deleted successfully."
        }), 200

    except Exception as e:
        logger.error(f"Error deleting announcement {announcement_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500
