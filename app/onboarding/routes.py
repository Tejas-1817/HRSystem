from flask import request, jsonify
from werkzeug.security import generate_password_hash
import uuid
import re
import logging
import mysql.connector
from app.models.database import execute_query, execute_single, Transaction
from app.api.middleware.auth import token_required, role_required
from app.onboarding import onboarding_bp

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
                INSERT INTO users (email, password_hash, role, is_active, username, password)
                VALUES (%s, %s, 'onboarding_candidate', TRUE, %s, %s)
            """, (personal_email, hashed_password, personal_email, hashed_password))
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

        return jsonify({
            "success": True,
            "total": total,
            "page": page,
            "per_page": per_page,
            "data": rows,
        }), 200

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

        return jsonify({
            "success": True,
            "joinee": joinee,
            "declaration": {
                "status": declaration["status"] if declaration else None,
                "submitted_at": declaration["submitted_at"] if declaration else None,
            },
            "documents": documents,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching joinee {joinee_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500
