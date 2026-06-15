from flask import request, jsonify
from werkzeug.security import generate_password_hash
import uuid
import re
import logging
import mysql.connector
from app.models.database import execute_query, execute_single, Transaction
from app.api.middleware.auth import token_required, role_required, onboarding_required
from app.onboarding import onboarding_bp
from app.services import declaration_service
from app.services import document_service
from app.services import dashboard_service
from app.utils.json_util import safe_jsonify

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _validate_joinee_payload(data):
    errors = {}

    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        errors["full_name"] = "Full name is required"

    phone = (data.get("phone") or "").strip()
    if not phone:
        errors["phone"] = "Phone number is required"

    personal_email = (data.get("personal_email") or "").strip().lower()
    if not personal_email:
        errors["personal_email"] = "Personal email is required"
    elif not EMAIL_RE.match(personal_email):
        errors["personal_email"] = "Invalid email format"

    temp_password = data.get("temp_password") or ""
    if not temp_password:
        errors["temp_password"] = "Temporary password is required"
    elif len(temp_password) < 8:
        errors["temp_password"] = "Temporary password must be at least 8 characters"

    return errors, {
        "full_name": full_name,
        "phone": phone,
        "personal_email": personal_email,
        "temp_password": temp_password,
        "joining_date": data.get("joining_date"),
        "assigned_role": data.get("assigned_role"),
        "assigned_department": data.get("assigned_department"),
    }


@onboarding_bp.route("/joinees", methods=["POST"])
@role_required(["hr", "admin"])
def create_joinee(current_user):
    try:
        data = request.get_json() or {}

        errors, cleaned = _validate_joinee_payload(data)
        if errors:
            return jsonify({"success": False, "error": "Validation failed", "errors": errors}), 400

        personal_email = cleaned["personal_email"]

        # Check uniqueness in users table
        existing_user = execute_single(
            "SELECT id FROM users WHERE email = %s", (personal_email,)
        )
        if existing_user:
            return jsonify({
                "success": False,
                "error": "A user with this email already exists in the system"
            }), 409

        # Check uniqueness in onboarding_joinee table
        existing_joinee = execute_single(
            "SELECT id FROM onboarding_joinee WHERE personal_email = %s", (personal_email,)
        )
        if existing_joinee:
            return jsonify({
                "success": False,
                "error": "A joinee with this email is already in the onboarding pipeline"
            }), 409

        person_id = str(uuid.uuid4())
        hashed_password = generate_password_hash(cleaned["temp_password"])

        with Transaction() as cursor:
            # Insert into users table
            cursor.execute("""
                INSERT INTO users (email, password_hash, role, is_active, username, password, employee_name)
                VALUES (%s, %s, 'onboarding_candidate', TRUE, %s, %s, %s)
            """, (personal_email, hashed_password, personal_email, hashed_password, cleaned["full_name"]))
            user_id = cursor.lastrowid

            # Insert into onboarding_joinee
            cursor.execute("""
                INSERT INTO onboarding_joinee
                    (person_id, full_name, phone, personal_email,
                     active_login_email, onboarding_status,
                     joining_date, assigned_role, assigned_department,
                     created_by_user_id, user_id)
                VALUES (%s, %s, %s, %s, %s, 'PENDING', %s, %s, %s, %s, %s)
            """, (
                person_id,
                cleaned["full_name"],
                cleaned["phone"],
                personal_email,
                personal_email,
                cleaned.get("joining_date") or None,
                cleaned.get("assigned_role"),
                cleaned.get("assigned_department"),
                current_user["user_id"],
                user_id,
            ))
            joinee_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO onboarding_audit_log
                    (joinee_id, action, new_value, performed_by, notes)
                VALUES (%s, 'JOINEE_CREATED', %s, %s, %s)
            """, (joinee_id, personal_email, current_user["user_id"],
                  f"Joinee created by {current_user.get('username', 'HR')}"))

        return jsonify({
            "success": True,
            "message": "Joinee created successfully",
            "joinee_id": joinee_id,
            "person_id": person_id,
            "full_name": cleaned["full_name"],
            "personal_email": personal_email,
            "onboarding_status": "PENDING",
        }), 201

    except mysql.connector.IntegrityError as e:
        logger.warning(f"Joinee creation conflict: {e}")
        return jsonify({"success": False, "error": "A record with this email already exists"}), 409
    except Exception as e:
        logger.error(f"Error creating joinee: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@onboarding_bp.route("/joinees", methods=["GET"])
@role_required(["hr", "admin"])
def list_joinees(current_user):
    try:
        status_filter = request.args.get("status")
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        offset = (page - 1) * per_page

        where_clause = ""
        params = []
        if status_filter:
            where_clause = "WHERE oj.onboarding_status = %s"
            params.append(status_filter.upper())

        count_query = f"SELECT COUNT(*) as total FROM onboarding_joinee oj {where_clause}"
        count_result = execute_single(count_query, tuple(params))
        total = count_result["total"] if count_result else 0

        data_query = f"""
            SELECT oj.id, oj.person_id, oj.full_name, oj.phone,
                   oj.personal_email, oj.company_email, oj.active_login_email,
                   oj.onboarding_status, oj.joining_date, oj.assigned_role,
                   oj.assigned_department, oj.created_at
            FROM onboarding_joinee oj
            {where_clause}
            ORDER BY oj.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        rows = execute_query(data_query, tuple(params)) or []

        return safe_jsonify({
            "success": True,
            "total": total,
            "page": page,
            "per_page": per_page,
            "data": rows,
        }, 200)

    except Exception as e:
        logger.error(f"Error listing joinees: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@onboarding_bp.route("/joinees/<int:joinee_id>", methods=["GET"])
@token_required
def get_joinee(current_user,joinee_id):
    try:
        joinee = execute_single("""
            SELECT oj.* FROM onboarding_joinee oj WHERE oj.id = %s
        """, (joinee_id,))

        if not joinee:
            return jsonify({"success": False, "error": "Joinee not found"}), 404

        # RBAC: hr/admin can view any; onboarding_candidate can only view their own
        user_role = current_user.get("role", "")
        if user_role not in ("hr", "admin"):
            if user_role == "onboarding_candidate":
                user_id = current_user.get("user_id")
                if joinee.get("user_id") != user_id:
                    return jsonify({"success": False, "error": "Access denied"}), 403
            else:
                return jsonify({"success": False, "error": "Access denied"}), 403

        # Get declaration status
        declaration = execute_single("""
            SELECT status, submitted_at, hr_notes
            FROM onboarding_declaration
            WHERE joinee_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (joinee_id,))

        # Get documents (without file_path for security)
        documents = execute_query("""
            SELECT id, document_type, document_label, verification_status, uploaded_at
            FROM onboarding_documents
            WHERE joinee_id = %s
            ORDER BY uploaded_at DESC
        """, (joinee_id,)) or []

        return safe_jsonify({
            "success": True,
            "joinee": joinee,
            "declaration": {
                "status": declaration["status"] if declaration else None,
                "submitted_at": declaration["submitted_at"] if declaration else None,
            },
            "documents": documents,
        }, 200)

    except Exception as e:
        logger.error(f"Error fetching joinee {joinee_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ═══════════════════════════════════════════════════════════════════════════
# DECLARATION APIs
# ═══════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────
# API 1 — POST /onboarding/declaration  (Save / Update)
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/declaration", methods=["POST"])
@onboarding_required
def save_declaration(current_user):
    """
    Create or update the onboarding declaration for the authenticated
    candidate.  Accepts the full declaration payload including education,
    employment, and references arrays.

    - joinee_id is extracted from JWT (never from request body).
    - If no declaration exists → INSERT with status DRAFT.
    - If declaration exists with status DRAFT or CHANGES_REQUESTED → UPDATE.
    - If declaration is APPROVED → 403 Forbidden.
    - References are replaced atomically on every save.
    """
    try:
        joinee_id = current_user.get("joinee_id")
        if not joinee_id:
            return jsonify({
                "success": False,
                "message": "Joinee identity could not be resolved from token."
            }), 403

        data = request.get_json() or {}

        # ── Validate ──────────────────────────────────────────────────
        errors, cleaned = declaration_service.validate_declaration_payload(
            data, is_submit=False
        )
        if errors:
            return jsonify({
                "success": False,
                "message": "Validation failed",
                "errors": errors,
            }), 400

        references = cleaned.get("references") or []

        # ── Transactional save ────────────────────────────────────────
        with Transaction() as cursor:
            existing = declaration_service.get_declaration_by_joinee(
                joinee_id, cursor=cursor
            )

            if existing:
                # Block modification of approved declarations
                if existing["status"] == "APPROVED":
                    return jsonify({
                        "success": False,
                        "message": "Declaration already approved and cannot be modified."
                    }), 403

                # Only DRAFT or CHANGES_REQUESTED can be updated
                if existing["status"] not in ("DRAFT", "CHANGES_REQUESTED"):
                    return jsonify({
                        "success": False,
                        "message": (
                            f"Declaration with status '{existing['status']}' "
                            f"cannot be modified."
                        ),
                    }), 400

                declaration_id = existing["id"]
                declaration_service.update_declaration(
                    declaration_id, cleaned, cursor
                )
                declaration_service.replace_references(
                    declaration_id, joinee_id, references, cursor
                )
            else:
                # First-time save → INSERT
                declaration_id = declaration_service.insert_declaration(
                    joinee_id, cleaned, cursor
                )
                declaration_service.replace_references(
                    declaration_id, joinee_id, references, cursor
                )

        # ── Re-fetch and respond ──────────────────────────────────────
        result = declaration_service.build_declaration_response(joinee_id)
        return jsonify({
            "success": True,
            "message": "Declaration saved successfully.",
            "declaration": result,
        }), 200

    except mysql.connector.Error as e:
        logger.error(f"Database error saving declaration: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error saving declaration: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────
# API 2 — POST /onboarding/declaration/submit
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/declaration/submit", methods=["POST"])
@onboarding_required
def submit_declaration(current_user):
    """
    Submit the candidate's declaration for HR review.

    - No request body required.
    - Declaration must exist with status DRAFT or CHANGES_REQUESTED.
    - Minimum 3 professional references are required.
    - Updates onboarding_joinee status from PENDING → DOCUMENTS_SUBMITTED.
    - Creates an audit log entry.
    """
    try:
        joinee_id = current_user.get("joinee_id")
        if not joinee_id:
            return jsonify({
                "success": False,
                "message": "Joinee identity could not be resolved from token."
            }), 403

        with Transaction() as cursor:
            # ── Fetch existing declaration ────────────────────────────
            existing = declaration_service.get_declaration_by_joinee(
                joinee_id, cursor=cursor
            )

            if not existing:
                return jsonify({
                    "success": False,
                    "message": "No declaration found. Please save a declaration first."
                }), 400

            if existing["status"] not in ("DRAFT", "CHANGES_REQUESTED"):
                return jsonify({
                    "success": False,
                    "message": (
                        f"Declaration with status '{existing['status']}' "
                        f"cannot be submitted."
                    ),
                }), 400

            declaration_id = existing["id"]

            # ── Validate minimum references ───────────────────────────
            refs = declaration_service.get_references_by_declaration(
                declaration_id, cursor=cursor
            )
            if len(refs) < declaration_service.MIN_REFERENCES_ON_SUBMIT:
                return jsonify({
                    "success": False,
                    "message": (
                        f"Minimum {declaration_service.MIN_REFERENCES_ON_SUBMIT} "
                        f"professional references are required for submission. "
                        f"Currently {len(refs)} provided."
                    ),
                }), 400

            # ── Update declaration status ─────────────────────────────
            declaration_service.submit_declaration(declaration_id, cursor)

            # ── Update onboarding_joinee status if still PENDING ──────
            cursor.execute(
                """
                UPDATE onboarding_joinee
                SET    onboarding_status = 'DOCUMENTS_SUBMITTED'
                WHERE  id = %s AND onboarding_status = 'PENDING'
                """,
                (joinee_id,),
            )

            # ── Audit log ─────────────────────────────────────────────
            cursor.execute(
                """
                INSERT INTO onboarding_audit_log
                    (joinee_id, action, new_value, performed_by, notes)
                VALUES (%s, 'DECLARATION_SUBMITTED', 'SUBMITTED', %s, %s)
                """,
                (
                    joinee_id,
                    current_user["user_id"],
                    f"Declaration submitted by candidate (user_id={current_user['user_id']})",
                ),
            )

        return jsonify({
            "success": True,
            "message": "Declaration submitted successfully.",
        }), 200

    except mysql.connector.Error as e:
        logger.error(f"Database error submitting declaration: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error submitting declaration: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────
# API 3 — GET /onboarding/declaration
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/declaration", methods=["GET"])
@role_required(["onboarding_candidate", "hr"])
def get_declaration(current_user):
    """
    Retrieve the full declaration for a joinee.

    - onboarding_candidate: automatically uses joinee_id from JWT.
    - hr / admin: requires ?joinee_id=<id> query parameter.
    - Returns declaration with education, employment, references arrays,
      and workflow status fields.
    """
    try:
        role = current_user.get("role", "")

        if role == "onboarding_candidate":
            joinee_id = current_user.get("joinee_id")
            if not joinee_id:
                return jsonify({
                    "success": False,
                    "message": "Joinee identity could not be resolved from token."
                }), 403
        else:
            # hr or admin
            joinee_id = request.args.get("joinee_id", type=int)
            if not joinee_id:
                return jsonify({
                    "success": False,
                    "message": "Query parameter 'joinee_id' is required for HR/admin access."
                }), 400

        result = declaration_service.build_declaration_response(joinee_id)

        return jsonify({
            "success": True,
            "declaration": result,  # None if no declaration exists
        }), 200

    except Exception as e:
        logger.error(f"Error fetching declaration: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────
# API 4 — PUT /onboarding/declaration/<joinee_id>/review
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/declaration/<int:joinee_id>/review", methods=["PUT"])
@role_required(["hr"])
def review_declaration(current_user, joinee_id):
    """
    HR reviews a submitted declaration — either approves or requests changes.

    Request body:
        {
            "status": "APPROVED" | "CHANGES_REQUESTED",
            "hr_notes": "string (required when status = CHANGES_REQUESTED)"
        }

    On APPROVED:
        - If all onboarding_documents are also APPROVED → set
          onboarding_joinee.onboarding_status = VERIFIED.
    On CHANGES_REQUESTED:
        - Sets onboarding_joinee.onboarding_status = CHANGES_REQUESTED.

    Creates an audit log entry.
    """
    try:
        data = request.get_json() or {}
        new_status = (data.get("status") or "").strip().upper()
        hr_notes = (data.get("hr_notes") or "").strip()

        # ── Validate status ───────────────────────────────────────────
        allowed_statuses = ("APPROVED", "CHANGES_REQUESTED")
        if new_status not in allowed_statuses:
            return jsonify({
                "success": False,
                "message": (
                    f"Invalid status '{new_status}'. "
                    f"Allowed values: {', '.join(allowed_statuses)}"
                ),
            }), 400

        if new_status == "CHANGES_REQUESTED" and not hr_notes:
            return jsonify({
                "success": False,
                "message": "hr_notes is required when requesting changes."
            }), 400

        # ── Fetch declaration ─────────────────────────────────────────
        existing = declaration_service.get_declaration_by_joinee(joinee_id)
        if not existing:
            return jsonify({
                "success": False,
                "message": "No declaration found for this joinee."
            }), 404

        if existing["status"] != "SUBMITTED":
            return jsonify({
                "success": False,
                "message": "Only submitted declarations can be reviewed."
            }), 400

        declaration_id = existing["id"]
        hr_user_id = current_user["user_id"]

        # ── Transactional review ──────────────────────────────────────
        with Transaction() as cursor:
            declaration_service.review_declaration(
                declaration_id, new_status, hr_notes, hr_user_id, cursor
            )

            if new_status == "APPROVED":
                # Auto-verify joinee if all documents are also approved
                all_docs_ok = declaration_service.check_all_documents_approved(
                    joinee_id, cursor=cursor
                )
                if all_docs_ok:
                    cursor.execute(
                        """
                        UPDATE onboarding_joinee
                        SET    onboarding_status = 'VERIFIED'
                        WHERE  id = %s
                        """,
                        (joinee_id,),
                    )
            elif new_status == "CHANGES_REQUESTED":
                cursor.execute(
                    """
                    UPDATE onboarding_joinee
                    SET    onboarding_status = 'CHANGES_REQUESTED'
                    WHERE  id = %s
                    """,
                    (joinee_id,),
                )

            # ── Audit log ─────────────────────────────────────────────
            cursor.execute(
                """
                INSERT INTO onboarding_audit_log
                    (joinee_id, action, new_value, performed_by, notes)
                VALUES (%s, 'DECLARATION_REVIEWED', %s, %s, %s)
                """,
                (
                    joinee_id,
                    new_status,
                    hr_user_id,
                    hr_notes or f"Declaration {new_status.lower().replace('_', ' ')} by HR",
                ),
            )

        # ── Re-fetch and return updated declaration ───────────────────
        result = declaration_service.build_declaration_response(joinee_id)
        return jsonify({
            "success": True,
            "message": f"Declaration {new_status.lower().replace('_', ' ')} successfully.",
            "declaration": result,
        }), 200

    except mysql.connector.Error as e:
        logger.error(f"Database error reviewing declaration: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error reviewing declaration: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENT MANAGEMENT APIs
# ═══════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────
# API — POST /onboarding/documents/upload
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/documents/upload", methods=["POST"])
@onboarding_required
def upload_document(current_user):
    """
    Upload an onboarding document.

    - Role: onboarding_candidate only (enforced by @onboarding_required).
    - joinee_id is derived from JWT — never from the request.
    - Blocks uploads if declaration is already APPROVED.
    - Validates file type (jpeg, png, webp, pdf) and size (≤ 10 MB).
    - Saves to uploads/onboarding/<joinee_id>/.
    - Creates audit log entry.

    Request: multipart/form-data with fields: file, document_type, document_label
    """
    try:
        joinee_id = current_user.get("joinee_id")
        if not joinee_id:
            return jsonify({
                "success": False,
                "message": "Joinee identity could not be resolved from token."
            }), 403

        # ── Validate form fields ──────────────────────────────────────
        document_type = (request.form.get("document_type") or "").strip().upper()
        document_label = (request.form.get("document_label") or "").strip()

        if not document_type:
            return jsonify({
                "success": False,
                "message": "document_type is required."
            }), 400

        if document_type not in document_service.ALLOWED_DOCUMENT_TYPES:
            return jsonify({
                "success": False,
                "message": (
                    f"Invalid document_type '{document_type}'. "
                    f"Allowed: {', '.join(sorted(document_service.ALLOWED_DOCUMENT_TYPES))}"
                )
            }), 400

        if not document_label:
            return jsonify({
                "success": False,
                "message": "document_label is required."
            }), 400

        if len(document_label) > document_service.MAX_LABEL_LENGTH:
            return jsonify({
                "success": False,
                "message": f"document_label must not exceed {document_service.MAX_LABEL_LENGTH} characters."
            }), 400

        # ── Validate file presence ────────────────────────────────────
        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({
                "success": False,
                "message": "No file provided. 'file' field is required."
            }), 400

        # ── Check declaration status (block if APPROVED) ──────────────
        existing_decl = declaration_service.get_declaration_by_joinee(joinee_id)
        if existing_decl and existing_decl["status"] == "APPROVED":
            return jsonify({
                "success": False,
                "message": "Documents cannot be added after onboarding approval."
            }), 403

        # ── Validate file (type, MIME, size) ──────────────────────────
        try:
            document_service.validate_upload_file(file)
        except ValueError as ve:
            return jsonify({"success": False, "message": str(ve)}), 400

        # ── Save file to disk ─────────────────────────────────────────
        original_filename = file.filename
        stored_filename, file_path, file_size, mime_type = (
            document_service.save_onboarding_document(
                file, joinee_id, document_type
            )
        )

        # ── Transactional DB insert + audit log ───────────────────────
        with Transaction() as cursor:
            doc_id = document_service.insert_document_record(
                joinee_id=joinee_id,
                document_type=document_type,
                document_label=document_label,
                file_original_name=original_filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                cursor=cursor,
            )

            document_service.log_document_audit(
                joinee_id=joinee_id,
                action="DOCUMENT_UPLOADED",
                new_value=document_type,
                performed_by=current_user["user_id"],
                notes=f"Uploaded '{document_label}' ({original_filename})",
                cursor=cursor,
            )

        return jsonify({
            "success": True,
            "message": "Document uploaded successfully",
            "document_id": doc_id,
            "document_type": document_type,
            "document_label": document_label,
            "verification_status": "PENDING",
        }), 201

    except mysql.connector.Error as e:
        logger.error(f"Database error uploading document: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────
# API — GET /onboarding/documents
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/documents", methods=["GET"])
@role_required(["onboarding_candidate", "hr"])
def list_documents(current_user):
    """
    List onboarding documents.

    - onboarding_candidate: returns own documents (joinee_id from JWT).
    - hr / admin: requires ?joinee_id=<id> query parameter.
    - Never exposes file_path or internal storage paths.
    """
    try:
        role = current_user.get("role", "")

        if role == "onboarding_candidate":
            joinee_id = current_user.get("joinee_id")
            if not joinee_id:
                return jsonify({
                    "success": False,
                    "message": "Joinee identity could not be resolved from token."
                }), 403
        else:
            # hr or admin
            joinee_id = request.args.get("joinee_id", type=int)
            if not joinee_id:
                return jsonify({
                    "success": False,
                    "message": "Query parameter 'joinee_id' is required for HR/admin access."
                }), 400

        documents = document_service.get_documents_by_joinee(joinee_id)

        # Serialize dates for JSON response
        serialized = []
        for doc in documents:
            serialized.append(document_service.serialize_document(doc))

        return jsonify({
            "success": True,
            "count": len(serialized),
            "documents": serialized,
        }), 200

    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────
# API — PUT /onboarding/documents/<document_id>/verify
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/documents/<int:document_id>/verify", methods=["PUT"])
@role_required(["hr"])
def verify_document(current_user, document_id):
    """
    HR verifies (approves or rejects) an onboarding document.

    Request body:
        {
            "verification_status": "APPROVED" | "REJECTED",
            "rejection_reason": "Required when status is REJECTED"
        }

    After APPROVED:
        - Checks if ALL documents + declaration are APPROVED.
        - If yes, auto-sets onboarding_joinee.onboarding_status = VERIFIED.
    """
    try:
        data = request.get_json() or {}
        new_status = (data.get("verification_status") or "").strip().upper()
        rejection_reason = (data.get("rejection_reason") or "").strip()

        # ── Validate status ───────────────────────────────────────────
        allowed_statuses = ("APPROVED", "REJECTED")
        if new_status not in allowed_statuses:
            return jsonify({
                "success": False,
                "message": (
                    f"Invalid verification_status '{new_status}'. "
                    f"Allowed: {', '.join(allowed_statuses)}"
                )
            }), 400

        if new_status == "REJECTED" and not rejection_reason:
            return jsonify({
                "success": False,
                "message": "rejection_reason is required when status is REJECTED."
            }), 400

        # ── Fetch document ────────────────────────────────────────────
        document = document_service.get_document_by_id(document_id)
        if not document:
            return jsonify({
                "success": False,
                "message": "Document not found."
            }), 404

        joinee_id = document["joinee_id"]
        hr_user_id = current_user["user_id"]

        # ── Transactional update ──────────────────────────────────────
        with Transaction() as cursor:
            document_service.update_verification(
                document_id=document_id,
                status=new_status,
                rejection_reason=rejection_reason if new_status == "REJECTED" else None,
                verified_by=hr_user_id,
                cursor=cursor,
            )

            # Auto-verify joinee if all documents + declaration approved
            auto_verified = False
            if new_status == "APPROVED":
                auto_verified = document_service.check_and_auto_verify_joinee(
                    joinee_id, cursor
                )

            # Audit log
            document_service.log_document_audit(
                joinee_id=joinee_id,
                action="DOCUMENT_VERIFIED",
                new_value=new_status,
                performed_by=hr_user_id,
                notes=(
                    rejection_reason
                    if new_status == "REJECTED"
                    else f"Document {document['document_type']} approved by HR"
                ),
                cursor=cursor,
            )

            # If auto-verified, add a separate audit entry
            if auto_verified:
                document_service.log_document_audit(
                    joinee_id=joinee_id,
                    action="STATUS_CHANGED",
                    new_value="VERIFIED",
                    performed_by=hr_user_id,
                    notes="Auto-verified: all documents and declaration approved",
                    cursor=cursor,
                )

        # ── Fetch updated document for response ──────────────────────
        updated_doc = document_service.get_document_by_id(document_id)
        response_doc = document_service.serialize_document(updated_doc) if updated_doc else {}

        return jsonify({
            "success": True,
            "message": f"Document {new_status.lower()} successfully.",
            "document": response_doc,
            "auto_verified": auto_verified if new_status == "APPROVED" else False,
        }), 200

    except mysql.connector.Error as e:
        logger.error(f"Database error verifying document: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error verifying document: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────
# API — DELETE /onboarding/documents/<document_id>
# ─────────────────────────────────────────────────────────────────────────
@onboarding_bp.route("/documents/<int:document_id>", methods=["DELETE"])
@role_required(["onboarding_candidate", "hr"])
def delete_document(current_user, document_id):
    """
    Delete an onboarding document.

    - onboarding_candidate: may delete own documents only, and only if
      the document is NOT already APPROVED.
    - hr / admin: may delete any onboarding document.

    Workflow:
      1. Verify permissions
      2. Delete physical file from local storage
      3. Delete database record
      4. Create audit log
    """
    try:
        # ── Fetch document ────────────────────────────────────────────
        document = document_service.get_document_by_id(document_id)
        if not document:
            return jsonify({
                "success": False,
                "message": "Document not found."
            }), 404

        joinee_id = document["joinee_id"]
        role = current_user.get("role", "")

        # ── RBAC checks ───────────────────────────────────────────────
        if role == "onboarding_candidate":
            # Must be own document
            user_joinee_id = current_user.get("joinee_id")
            if joinee_id != user_joinee_id:
                return jsonify({
                    "success": False,
                    "message": "Access denied. You can only delete your own documents."
                }), 403

            # Cannot delete already-approved documents
            if document["verification_status"] == "APPROVED":
                return jsonify({
                    "success": False,
                    "message": "Cannot delete an approved document. Contact HR for assistance."
                }), 403

        # ── Delete physical file ──────────────────────────────────────
        document_service.delete_document_file(document.get("file_path"))

        # ── Transactional DB delete + audit log ───────────────────────
        with Transaction() as cursor:
            document_service.delete_document_record(document_id, cursor)

            document_service.log_document_audit(
                joinee_id=joinee_id,
                action="DOCUMENT_DELETED",
                new_value=document["document_type"],
                performed_by=current_user["user_id"],
                notes=(
                    f"Document '{document['document_label']}' deleted "
                    f"by {current_user.get('username', 'user')}"
                ),
                cursor=cursor,
            )

        return jsonify({
            "success": True,
            "message": "Document removed successfully."
        }), 200

    except mysql.connector.Error as e:
        logger.error(f"Database error deleting document: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500

# ═══════════════════════════════════════════════════════════════════════════
# HR DASHBOARD & VERIFICATION SUMMARY APIs
# ═══════════════════════════════════════════════════════════════════════════

@onboarding_bp.route("/stats", methods=["GET"])
@role_required(["hr"])
def get_onboarding_stats(current_user):
    """
    API 1: Get onboarding statistics for the HR dashboard.
    """
    try:
        stats = dashboard_service.get_dashboard_stats()
        return safe_jsonify(stats, 200)
    except Exception as e:
        logger.error(f"Error fetching onboarding stats: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500


@onboarding_bp.route("/joinees/<int:joinee_id>/summary", methods=["GET"])
@role_required(["hr"])
def get_joinee_summary(current_user, joinee_id):
    """
    API 2: Provide a complete onboarding review summary for a single joinee.
    """
    try:
        summary = dashboard_service.get_joinee_summary(joinee_id)
        if not summary:
            return jsonify({
                "success": False,
                "message": "Onboarding joinee not found.",
                "error_code": "JOINEE_NOT_FOUND"
            }), 404
            
        return safe_jsonify(summary, 200)
    except Exception as e:
        logger.error(f"Error fetching joinee summary for {joinee_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500
