from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import re
import logging
import hashlib
from datetime import datetime, timedelta
from app.config import Config
from app.models.database import get_connection, execute_query, execute_single, Transaction
from app.api.middleware.auth import token_required, role_required, onboarding_required
from app.utils.helpers import generate_unique_username, cascade_rename_employee, log_audit_event
from app.services.leave_service import allocate_default_leaves
from app.services.employee_service import create_employee_record, update_employee_role
import mysql.connector
import uuid
from app.utils.email_service import send_reset_email
from app.utils.display_name_service import get_display_name, get_clean_name, enrich_record_with_display_name

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["POST"])
@role_required(["hr"])
def register(current_user):
    try:
        data = request.get_json()
        required = ("username", "password", "employee_name")
        username = data.get("username", "").strip()
        password = data.get("password")
        email = data.get("email", "").strip().lower() # Normalize email
        if not password or not username:
             return jsonify({"success": False, "error": "Username and password are required"}), 400
             
        role = data.get("role", "employee")
        hashed_password = generate_password_hash(password)

        with Transaction() as cursor:
            # 1. Create employee record and allocate leaves (atomic)
            employee_name, original_name = create_employee_record(data, role, cursor, with_user=False)

            # 2. Create user credentials with sanitized username
            cursor.execute("""
                INSERT INTO users (username, original_name, password, role, employee_name, password_change_required, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
            """, (username, original_name, hashed_password, role, employee_name))
            
            # 3. Trigger Welcome Notification
            welcome_title = "Welcome to Altzor Digital Solutions Pvt.Ltd!"
            welcome_message = f"Welcome to the company, {data.get('employee_name')}! Your account has been successfully created. We're excited to have you onboard."
            cursor.execute("""
                INSERT INTO notifications (employee_name, title, message, type)
                VALUES (%s, %s, %s, 'welcome_notification')
            """, (employee_name, welcome_title, welcome_message))

        logger.info(f"User {data.get('username')} registered successfully as {employee_name}")
        return jsonify({
            "success": True, 
            "message": "User registered successfully with leave balance allocated", 
            "employee_name": employee_name
        }), 201

    except mysql.connector.IntegrityError as e:
        logger.warning(f"Registration conflict for {data.get('username')}: {e}")
        return jsonify({"success": False, "error": "Username or email already exists"}), 409
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json() or {}
        login_id = (data.get("email") or data.get("username") or "").strip().lower()
        password = data.get("password", "") # Passwords should NOT be stripped
        
        if not login_id or not password:
            return jsonify({"success": False, "error": "Missing email/username or password"}), 400

        # Dual-read: query by both new email column and legacy username column
        query = """
            SELECT u.*, COALESCE(e.name, u.employee_name) as employee_name
            FROM users u
            LEFT JOIN employee e ON u.employee_id = e.id
            WHERE (u.email = %s OR u.username = %s)
            AND (u.is_active IS NULL OR u.is_active = TRUE)
            LIMIT 1
        """
        user = execute_single(query, (login_id, login_id))

        if not user:
            return jsonify({"success": False, "error": "Invalid email/username or password"}), 401

        # Dual-read password: try password_hash first, fallback to password
        stored_hash = user.get("password_hash") or user.get("password")
        if not stored_hash or not check_password_hash(stored_hash, password):
            return jsonify({"success": False, "error": "Invalid email/username or password"}), 401

        # JWT username = email (new), fallback to username (legacy)
        jwt_username = user.get("email") or user.get("username") or ""
        jwt_employee_name = user.get("employee_name") or ""

        # ── Onboarding-specific enrichment ────────────────────────────────
        is_onboarding = (user.get("role") == "onboarding_candidate")
        onboarding_jwt_claims = {}
        onboarding_response = {"is_onboarding": False}

        if is_onboarding:
            from app.services.onboarding_service import get_joinee_by_user_id
            joinee = get_joinee_by_user_id(user["id"])
            if joinee:
                onboarding_jwt_claims = {
                    "joinee_id": joinee["id"],
                    "onboarding_status": joinee["onboarding_status"],
                }
                onboarding_response = {
                    "is_onboarding": True,
                    "joinee_id": joinee["id"],
                    "onboarding_status": joinee["onboarding_status"],
                    "temp_password_changed": bool(joinee["temp_password_changed"]),
                }
        # ─────────────────────────────────────────────────────────────────

        jwt_payload = {
            "user_id": user["id"],
            "username": jwt_username,
            "role": user["role"],
            "employee_name": jwt_employee_name,
            "password_change_required": bool(user.get("password_change_required", False)),
            "exp": datetime.utcnow() + timedelta(hours=8),
            **onboarding_jwt_claims,
        }
        token = jwt.encode(jwt_payload, Config.JWT_SECRET, algorithm="HS256")

        if isinstance(token, bytes): token = token.decode("utf-8")

        # Resolve clean display names for the response
        clean_name = get_clean_name(jwt_employee_name) if jwt_employee_name else jwt_username

        response_user = {
            "id": user["id"],
            "username": jwt_username,
            "role": user["role"],
            "employee_name": jwt_employee_name,
            "full_name": clean_name,
            "display_name": get_display_name(clean_name, user["role"]),
            "password_change_required": user.get("password_change_required", False),
            **onboarding_response,
        }

        return jsonify({
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": response_user,
        }), 200
    except mysql.connector.Error as db_err:
        logger.error(f"Database error during login: {db_err}")
        return jsonify({"success": False, "error": "Service temporarily unavailable. Please try again later."}), 503
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password(current_user):
    try:
        data = request.get_json()
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not new_password or not confirm_password:
            return jsonify({"success": False, "error": "New password and confirmation are required"}), 400
        if new_password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match"}), 400
        if len(new_password) < 8 or not re.search(r"[A-Z]", new_password) or not re.search(r"[@$!%*?&]", new_password):
            return jsonify({"success": False, "error": "Password requirements not met"}), 400

        # 🔥 Password Reuse Prevention
        user = execute_single("SELECT password FROM users WHERE id=%s", (current_user["user_id"],))
        if check_password_hash(user["password"], new_password):
            return jsonify({"success": False, "error": "New password cannot be the same as your current password"}), 400

        hashed_password = generate_password_hash(new_password)

        # Atomic transaction: update password + mark temp password changed for onboarding
        with Transaction() as cursor:
            cursor.execute(
                "UPDATE users SET password=%s, password_change_required=FALSE WHERE id=%s",
                (hashed_password, current_user["user_id"])
            )

            # Mark temp_password_changed for onboarding candidates
            if current_user["role"] == "onboarding_candidate":
                from app.services.onboarding_service import mark_temp_password_changed
                mark_temp_password_changed(current_user["user_id"], cursor=cursor)

        # 🔥 Audit Logging
        log_audit_event(current_user["user_id"], "password_change", "User updated their password successfully.")

        # Build refreshed JWT with onboarding claims preserved
        new_jwt_payload = {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "role": current_user["role"],
            "employee_name": current_user["employee_name"],
            "password_change_required": False,
        }
        # Carry forward onboarding claims if present
        if current_user.get("joinee_id"):
            new_jwt_payload["joinee_id"] = current_user["joinee_id"]
        if current_user.get("onboarding_status"):
            new_jwt_payload["onboarding_status"] = current_user["onboarding_status"]

        new_token = jwt.encode(new_jwt_payload, Config.JWT_SECRET, algorithm="HS256")

        return jsonify({"success": True, "message": "Password updated", "token": new_token}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route("/profile", methods=["GET"])
@token_required
def get_profile(current_user):
    try:
        query = """
            SELECT u.id, u.username, u.role, u.employee_name, u.is_active, u.created_at as account_created_at,
                   e.salary, e.date_of_birth, e.date_of_joining, e.phone, e.photo, e.status, e.allow_over_allocation,
                   COALESCE(lb_sum.total, 0) as total_leaves, 
                   COALESCE(lb_sum.used, 0) as used_leaves, 
                   COALESCE(lb_sum.remaining, 0) as remaining_leaves,
                   COALESCE(util.total_utilization, 0) as total_utilization,
                   GREATEST(0, 100 - COALESCE(util.total_utilization, 0)) as remaining_availability
            FROM users u
            LEFT JOIN employee e ON u.employee_name = e.name
            LEFT JOIN (
                SELECT employee_name, 
                       SUM(total_leaves) as total, 
                       SUM(used_leaves) as used, 
                       SUM(total_leaves - used_leaves) as remaining
                FROM leave_balance
                GROUP BY employee_name
            ) lb_sum ON u.employee_name = lb_sum.employee_name
            LEFT JOIN (
                SELECT pa.employee_name, SUM(pa.billable_percentage) as total_utilization
                FROM project_assignments pa
                JOIN projects p ON pa.project_id = p.id
                WHERE p.status NOT IN ('completed', 'closed', 'cancelled')
                GROUP BY pa.employee_name
            ) util ON u.employee_name = util.employee_name
            WHERE u.id = %s
        """
        user_data = execute_single(query, (current_user["user_id"],))
        if not user_data:
            return jsonify({"success": False, "error": "User not found"}), 404

        # Use the serializer from employee_routes (dynamic import to avoid circular dependencies)
        from app.api.routes.employee_routes import serialize_employee
        from app.services.leave_service import get_employee_balance, allocate_default_leaves
        
        # Auto-allocate if missing
        if user_data.get("total_leaves") == 0:
            has_records = execute_single("SELECT 1 FROM leave_balance WHERE employee_name = %s LIMIT 1", (user_data["employee_name"],))
            if not has_records:
                allocate_default_leaves(user_data["employee_name"])
                # Refresh summary data
                updated_lb = execute_single("""
                    SELECT SUM(total_leaves) as total, SUM(used_leaves) as used, SUM(total_leaves - used_leaves) as remaining
                    FROM leave_balance WHERE employee_name = %s
                """, (user_data["employee_name"],))
                if updated_lb:
                    user_data["total_leaves"] = updated_lb["total"]
                    user_data["used_leaves"] = updated_lb["used"]
                    user_data["remaining_leaves"] = updated_lb["remaining"]

        # Fetch detailed breakdown for the "Pro Add-On" dashboard requirement
        detailed_balance = get_employee_balance(user_data["employee_name"])

        return jsonify({
            "success": True, 
            "user": serialize_employee(user_data),
            "leave_balance": detailed_balance
        }), 200
    except Exception as e:
        logger.error(f"Error fetching profile: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route("/users", methods=["GET"])
@role_required(["hr"])
def get_all_users(current_user):
    users = execute_query("SELECT id, username, original_name, role, employee_name, is_active, created_at FROM users ORDER BY role, username")
    # Enrich each user with full_name and display_name
    for u in users:
        enrich_record_with_display_name(u, name_field="employee_name", role_field="role")
    return jsonify({"success": True, "users": users}), 200

@auth_bp.route("/users/<int:user_id>/role", methods=["PATCH"])
@role_required(["admin"])
def update_user_role(current_user, user_id):
    try:
        data = request.get_json()
        new_role = data.get("role")
        
        result = update_employee_role(current_user["user_id"], user_id, new_role)
        
        if result.get("no_change"):
            return jsonify(result), 200
            
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating role: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500

# --- Super Admin Management Endpoints ---

@auth_bp.route("/admin/audit-logs", methods=["GET"])
@role_required(["admin"])
def get_audit_logs(current_user):
    """View all system activity logs (Admin only)."""
    try:
        logs = execute_query("""
            SELECT al.*, u.username, u.role, u.employee_name 
            FROM audit_logs al 
            JOIN users u ON al.user_id = u.id 
            ORDER BY al.created_at DESC 
            LIMIT 500
        """)
        return jsonify({"success": True, "logs": logs}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@role_required(["admin"])
def admin_reset_password(current_user, user_id):
    """Force reset any user's password (Admin only)."""
    try:
        from app.services.employee_service import DEFAULT_TEMP_PASSWORD
        user = execute_single("SELECT id, username, employee_name FROM users WHERE id=%s", (user_id,))
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404
        
        hashed_password = generate_password_hash(DEFAULT_TEMP_PASSWORD)
        execute_query("UPDATE users SET password=%s, password_change_required=TRUE WHERE id=%s", (hashed_password, user_id), commit=True)
        
        log_audit_event(current_user["user_id"], "admin_password_reset", f"Admin forced password reset for {user['username']} ({user['employee_name']})")
        
        return jsonify({"success": True, "message": f"Password reset to default for {user['username']}"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Step 1 of password recovery.
    Generates a secure token and sends a reset link to the user's email.
    """
    try:
        data = request.get_json() or {}
        email = data.get("email", "").strip().lower()
        
        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        # Find user by email (linked via employee table)
        query = """
            SELECT u.id, u.username, u.employee_name 
            FROM users u
            JOIN employee e ON u.employee_name = e.name
            WHERE e.email = %s AND u.is_active = TRUE
            LIMIT 1
        """
        user = execute_single(query, (email,))
        
        # Security: Always return success message even if email doesn't exist
        # This prevents "Email Enumeration" attacks.
        generic_msg = "If an account with that email exists, we've sent a password reset link."
        
        if user:
            # Generate secure token (UUID) and 30-min expiry
            token = str(uuid.uuid4())
            expiry = datetime.now() + timedelta(minutes=30)
            
            # Save to DB
            execute_query(
                "UPDATE users SET reset_token=%s, reset_token_expiry=%s WHERE id=%s",
                (token, expiry, user["id"]),
                commit=True
            )
            
            # Construct reset link using centralized frontend URL config
            reset_link = f"{Config.FRONTEND_URL}/reset-password?token={token}"
            
            # Send email
            send_reset_email(email, reset_link)
            
            # Log audit event
            log_audit_event(user["id"], "forgot_password_request", f"Password reset requested for {user['username']}")

        return jsonify({"success": True, "message": generic_msg}), 200

    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Step 2 of password recovery.
    Validates the token and updates the user's password.
    """
    try:
        data = request.get_json() or {}
        token = data.get("token")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")
        
        if not all([token, new_password, confirm_password]):
            return jsonify({"success": False, "error": "All fields are required"}), 400
            
        if new_password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match"}), 400

        # Password complexity check (8+ chars, capital, special)
        if len(new_password) < 8 or not re.search(r"[A-Z]", new_password) or not re.search(r"[@$!%*?&]", new_password):
            return jsonify({"success": False, "error": "Password must be 8+ chars and include a capital and a special character"}), 400

        # Find user by token and check expiry
        user = execute_single(
            "SELECT id, username FROM users WHERE reset_token=%s AND reset_token_expiry > %s",
            (token, datetime.now())
        )
        
        if not user:
            return jsonify({"success": False, "error": "Invalid or expired reset token"}), 400

        # Hash new password
        hashed_password = generate_password_hash(new_password)
        
        # Update password and CLEAR token (single-use)
        execute_query(
            "UPDATE users SET password=%s, reset_token=NULL, reset_token_expiry=NULL, password_change_required=FALSE WHERE id=%s",
            (hashed_password, user["id"]),
            commit=True
        )
        
        # Log audit event
        log_audit_event(user["id"], "password_reset_success", f"User {user['username']} successfully reset their password via token.")

        return jsonify({"success": True, "message": "Password has been reset successfully. You can now login."}), 200

    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout(current_user):
    """
    Secure Logout: Blacklists the current token until its natural expiry.
    """
    try:
        # Extract token from header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "Invalid token format"}), 400
            
        token = auth_header.split(" ")[1]
        
        # Calculate hash for storage
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Decode to get expiry (we can decode without validation here since middleware already validated it)
        # But for safety, let's just get the 'exp' field.
        decoded = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
        expires_at = datetime.fromtimestamp(decoded["exp"])
        
        # Add to blacklist
        execute_query(
            "INSERT INTO token_blacklist (token_hash, expires_at) VALUES (%s, %s)",
            (token_hash, expires_at),
            commit=True
        )
        
        # Log audit event
        log_audit_event(current_user["user_id"], "logout", f"User {current_user['username']} logged out successfully.")
        
        return jsonify({
            "success": True, 
            "message": "Logged out successfully. Session invalidated."
        }), 200
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# ONBOARDING PROFILE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@auth_bp.route("/onboarding-profile", methods=["GET"])
@onboarding_required
def get_onboarding_profile(current_user):
    """GET /auth/onboarding-profile

    Returns the full onboarding profile for the authenticated onboarding
    candidate.  Initialises the onboarding dashboard with joinee details,
    declaration status, and uploaded documents.

    Authorization: role == onboarding_candidate (enforced by @onboarding_required).
    """
    try:
        from app.services.onboarding_service import get_onboarding_profile as fetch_profile

        profile = fetch_profile(current_user["user_id"])

        if not profile:
            return jsonify({
                "success": False,
                "message": "Onboarding profile not found.",
                "error_code": "ONBOARDING_NOT_FOUND"
            }), 404

        return jsonify({"success": True, **profile}), 200

    except Exception as e:
        logger.error(f"Error fetching onboarding profile: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500
