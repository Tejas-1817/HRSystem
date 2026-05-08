import jwt
from functools import wraps
from flask import request, jsonify
import hashlib
from app.config import Config
from app.models.database import execute_single

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
                "password_change_required": data.get("password_change_required", False)
            }
            # Force password change if required, unless calling the change-password or profile endpoint
            allowed_paths = ["/auth/change-password", "/auth/change-password/", "/auth/profile", "/auth/profile/"]
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
                    "password_change_required": data.get("password_change_required", False)
                }
                # Force password change if required, unless calling the change-password or profile endpoint
                allowed_paths = ["/auth/change-password", "/auth/change-password/", "/auth/profile", "/auth/profile/"]
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
            if current_user["role"] == "admin":
                return f(current_user=current_user, *args, **kwargs)

            if current_user["role"] not in allowed_roles:
                return jsonify({
                    "success": False,
                    "error": f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {current_user['role']}"
                }), 403

            return f(current_user=current_user, *args, **kwargs)
        return decorated
    return decorator
