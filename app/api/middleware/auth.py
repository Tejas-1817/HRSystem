import jwt
from functools import wraps
from flask import request, jsonify
import hashlib
from app.config import Config
from app.models.database import execute_single, execute_query

# ─── Permission Cache ──────────────────────────────────────────────────
_permissions_cache = None

def get_permissions_cache():
    global _permissions_cache
    if _permissions_cache is None:
        refresh_permissions_cache()
    return _permissions_cache

def refresh_permissions_cache():
    global _permissions_cache
    rows = execute_query("""
        SELECT rp.role, p.permission_key, rp.is_granted 
        FROM role_permissions rp
        JOIN permissions p ON rp.permission_id = p.id
    """)
    new_cache = {}
    for r in rows:
        new_cache[(r['role'], r['permission_key'])] = bool(r['is_granted'])
    _permissions_cache = new_cache

# ───────────────────────────────────────────────────────────────────────


def token_required(f):
    """Decorator: requires a valid JWT token. Injects current_user dict into the function."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"success": False, "error": "Token is missing. Please login first."}), 401

        # Security: Check if token is blacklisted
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        blacklisted = execute_single("SELECT id FROM token_blacklist WHERE token_hash = %s", (token_hash,))
        if blacklisted:
            return jsonify({"success": False, "error": "Token has been invalidated (logged out). Please login again."}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "role": data["role"],
                "employee_name": data["employee_name"],
                "password_change_required": data.get("password_change_required", False),
                "joinee_id": data.get("joinee_id"),
                "onboarding_status": data.get("onboarding_status"),
            }
            # Force password change if required, unless calling the change-password or profile endpoint
            allowed_paths = ["/auth/change-password", "/auth/change-password/", "/auth/profile", "/auth/profile/", "/auth/onboarding-profile", "/auth/onboarding-profile/"]
            if current_user["password_change_required"] and request.path not in allowed_paths:
                return jsonify({
                    "success": False, 
                    "error": "Password change required. Please update your password to continue.",
                    "password_change_required": True
                }), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "error": "Token has expired. Please login again."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"success": False, "error": "Invalid token. Please login again."}), 401

        return f(current_user=current_user, *args, **kwargs)
    return decorated


def role_required(allowed_roles):
    """Decorator: requires user to have one of the allowed roles (manager, hr, employee)."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

            if not token:
                return jsonify({"success": False, "error": "Token is missing. Please login first."}), 401

            # Security: Check if token is blacklisted
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            blacklisted = execute_single("SELECT id FROM token_blacklist WHERE token_hash = %s", (token_hash,))
            if blacklisted:
                return jsonify({"success": False, "error": "Token has been invalidated (logged out). Please login again."}), 401

            try:
                data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
                current_user = {
                    "user_id": data["user_id"],
                    "username": data["username"],
                    "role": data["role"],
                    "employee_name": data["employee_name"],
                    "password_change_required": data.get("password_change_required", False),
                    "joinee_id": data.get("joinee_id"),
                    "onboarding_status": data.get("onboarding_status"),
                }
                # Force password change if required, unless calling the change-password or profile endpoint
                allowed_paths = ["/auth/change-password", "/auth/change-password/", "/auth/profile", "/auth/profile/", "/auth/onboarding-profile", "/auth/onboarding-profile/"]
                if current_user["password_change_required"] and request.path not in allowed_paths:
                    return jsonify({
                        "success": False, 
                        "error": "Password change required. Please update your password to continue.",
                        "password_change_required": True
                    }), 403
            except jwt.ExpiredSignatureError:
                return jsonify({"success": False, "error": "Token has expired. Please login again."}), 401
            except jwt.InvalidTokenError:
                return jsonify({"success": False, "error": "Invalid token. Please login again."}), 401

            # Role Bypass for Super Admin
            if current_user["role"] == "superadmin":
                return f(current_user=current_user, *args, **kwargs)

            if current_user["role"] not in allowed_roles:
                return jsonify({
                    "success": False,
                    "error": f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {current_user['role']}"
                }), 403

            return f(current_user=current_user, *args, **kwargs)
        return decorated
    return decorator


def superadmin_required(f):
    """Decorator: strictly requires the superadmin role. Never touches DB permissions."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # We can reuse token_required's validation by composing or just replicating the logic.
        # But since we just need the decoded token:
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"success": False, "error": "Token is missing. Please login first."}), 401

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if execute_single("SELECT id FROM token_blacklist WHERE token_hash = %s", (token_hash,)):
            return jsonify({"success": False, "error": "Token has been invalidated (logged out). Please login again."}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "role": data["role"],
                "employee_name": data["employee_name"]
            }
        except Exception:
            return jsonify({"success": False, "error": "Invalid or expired token."}), 401

        if current_user["role"] != "superadmin":
            return jsonify({"success": False, "error": "Access denied. Superadmin only."}), 403

        return f(current_user=current_user, *args, **kwargs)
    return decorated


def permission_required(permission_key):
    """Decorator: requires the user's role to have the given permission_key granted."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

            if not token:
                return jsonify({"success": False, "error": "Token is missing. Please login first."}), 401

            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if execute_single("SELECT id FROM token_blacklist WHERE token_hash = %s", (token_hash,)):
                return jsonify({"success": False, "error": "Token has been invalidated (logged out). Please login again."}), 401

            try:
                data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
                current_user = {
                    "user_id": data["user_id"],
                    "username": data["username"],
                    "role": data["role"],
                    "employee_name": data["employee_name"],
                    "password_change_required": data.get("password_change_required", False)
                }
                if current_user["password_change_required"]:
                    return jsonify({"success": False, "error": "Password change required.", "password_change_required": True}), 403
            except Exception:
                return jsonify({"success": False, "error": "Invalid or expired token."}), 401

            # Bypass for superadmin
            if current_user["role"] == "superadmin":
                return f(current_user=current_user, *args, **kwargs)

            # Check cache for this role + permission
            cache = get_permissions_cache()
            is_granted = cache.get((current_user["role"], permission_key), False)

            if not is_granted:
                return jsonify({
                    "success": False,
                    "error": f"Access denied. Missing permission: {permission_key}"
                }), 403

            return f(current_user=current_user, *args, **kwargs)
        return decorated
    return decorator



def onboarding_required(f):
    """Decorator: requires a valid JWT with role == onboarding_candidate.

    Combines token validation (including blacklist check) with an explicit
    role gate.  Any other role receives 403 Forbidden.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"success": False, "message": "Token is missing. Please login first.", "error_code": "UNAUTHORIZED"}), 401

        # Security: Check if token is blacklisted
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        blacklisted = execute_single("SELECT id FROM token_blacklist WHERE token_hash = %s", (token_hash,))
        if blacklisted:
            return jsonify({"success": False, "message": "Token has been invalidated (logged out). Please login again.", "error_code": "UNAUTHORIZED"}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "role": data["role"],
                "employee_name": data["employee_name"],
                "password_change_required": data.get("password_change_required", False),
                "joinee_id": data.get("joinee_id"),
                "onboarding_status": data.get("onboarding_status"),
            }
        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "message": "Token has expired. Please login again.", "error_code": "UNAUTHORIZED"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"success": False, "message": "Invalid token. Please login again.", "error_code": "UNAUTHORIZED"}), 401

        # Role gate: only onboarding_candidate may proceed
        if current_user["role"] != "onboarding_candidate":
            return jsonify({"success": False, "message": "Access denied.", "error_code": "FORBIDDEN"}), 403

        return f(current_user=current_user, *args, **kwargs)
    return decorated
