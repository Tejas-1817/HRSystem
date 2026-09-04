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
                "user_id": data.get("user_id") or data.get("id"),
                "username": data.get("username", ""),
                "role": data.get("role", "employee"),
                "employee_name": data.get("employee_name") or data.get("username", ""),
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


# ─── Feature to Permission Key Mapping ──────────────────────────────────
FEATURE_PERMISSION_MAP = {
    # 1. Employee & Team Management
    "employee_team_management": {
        "view": ["employees.allocation_config", "team_members.allocation_config"],
        "manage": ["employees.create", "employees.update", "employees.delete", "team_members.create", "team_members.update", "team_members.delete"],
    },
    "employees": {
        "view": ["employees.allocation_config", "team_members.allocation_config"],
        "manage": ["employees.create", "employees.update", "employees.delete", "team_members.create", "team_members.update", "team_members.delete"],
    },
    "team_members": {
        "view": ["employees.allocation_config", "team_members.allocation_config"],
        "manage": ["employees.create", "employees.update", "employees.delete", "team_members.create", "team_members.update", "team_members.delete"],
    },
    # 2. Departments
    "departments": {
        "view": ["departments.create", "departments.update", "departments.deactivate"],
        "manage": ["departments.create", "departments.update", "departments.deactivate"],
    },
    # 3. Designations
    "designations": {
        "view": ["designations.create", "designations.update", "designations.deactivate"],
        "manage": ["designations.create", "designations.update", "designations.deactivate"],
    },
    # 4. Devices & Assets
    "devices": {
        "view": ["devices.view_all"],
        "manage": ["devices.create", "devices.update", "devices.assign", "devices.return", "devices.upload_image", "devices.delete", "devices.change_status"],
    },
    "devices_assets": {
        "view": ["devices.view_all"],
        "manage": ["devices.create", "devices.update", "devices.assign", "devices.return", "devices.upload_image", "devices.delete", "devices.change_status"],
    },
    # 5. Software / Catalog
    "software": {
        "view": ["devices.catalog_view"],
        "manage": ["devices.catalog_create", "devices.catalog_update"],
    },
    # 6. Inventory & Stock
    "inventory": {
        "view": ["devices.inventory_dashboard"],
        "manage": ["devices.stock_reconciliation"],
    },
    "inventory_stock": {
        "view": ["devices.inventory_dashboard"],
        "manage": ["devices.stock_reconciliation"],
    },
    # 7. Reimbursements / Expenses
    "reimbursements": {
        "view": ["reimbursements.stats", "reimbursements.history"],
        "manage": ["reimbursements.approve", "reimbursements.reject", "reimbursements.mark_paid"],
        "approve": ["reimbursements.approve", "reimbursements.reject"],
    },
    "expenses": {
        "view": ["reimbursements.stats", "reimbursements.history"],
        "manage": ["reimbursements.approve", "reimbursements.reject", "reimbursements.mark_paid"],
        "approve": ["reimbursements.approve", "reimbursements.reject"],
    },
    # 8. Announcements
    "announcements": {
        "view": ["announcements.create", "announcements.update", "announcements.delete"],
        "manage": ["announcements.create", "announcements.update", "announcements.delete"],
    },
    # 9. Holidays
    "holidays": {
        "view": ["holidays.create"],
        "manage": ["holidays.create"],
    },
    # 10. Policies
    "policies": {
        "view": ["policies.create", "policies.update", "policies.delete"],
        "manage": ["policies.create", "policies.update", "policies.delete"],
    },
    # 11. User Accounts
    "auth": {
        "view": ["auth.list_users"],
        "manage": ["auth.register", "auth.list_users"],
    },
    "user_accounts": {
        "view": ["auth.list_users"],
        "manage": ["auth.register", "auth.list_users"],
    },
    # 12. Bank Details
    "bank": {
        "view": ["bank.list_all", "bank.get_employee", "bank.list_pending"],
        "manage": ["bank.delete"],
        "approve": ["bank.verify"],
    },
    "bank_details": {
        "view": ["bank.list_all", "bank.get_employee", "bank.list_pending"],
        "manage": ["bank.delete"],
        "approve": ["bank.verify"],
    },
    # 13. Documents
    "documents": {
        "view": ["documents.employee_status", "documents.list_pending"],
        "manage": ["documents.verify", "documents.reject"],
        "approve": ["documents.verify", "documents.reject"],
    },
    # 14. Helpdesk
    "helpdesk": {
        "view": ["helpdesk.stats", "helpdesk.history"],
        "manage": ["helpdesk.update_status", "helpdesk.assign", "helpdesk.change_priority", "helpdesk.delete"],
    },
    # 15. Leave Management
    "leave": {
        "view": ["leave.view_all_balances", "leave.currently_on_leave", "leave.analytics"],
        "manage": ["leave.view_all_balances", "leave.currently_on_leave", "leave.analytics"],
        "approve": ["leave.view_all_balances", "leave.currently_on_leave"],
    },
    "leaves": {
        "view": ["leave.view_all_balances", "leave.currently_on_leave", "leave.analytics"],
        "manage": ["leave.view_all_balances", "leave.currently_on_leave", "leave.analytics"],
        "approve": ["leave.view_all_balances", "leave.currently_on_leave"],
    },
    "leave_management": {
        "view": ["leave.view_all_balances", "leave.currently_on_leave", "leave.analytics"],
        "manage": ["leave.view_all_balances", "leave.currently_on_leave", "leave.analytics"],
        "approve": ["leave.view_all_balances", "leave.currently_on_leave"],
    },
    # 16. Projects & Work
    "projects": {
        "view": ["projects.create", "projects.assign_employee"],
        "manage": ["projects.update", "projects.delete", "projects.remove_assignment", "projects.update_assignment"],
    },
    "project_records": {
        "view": ["projects.create"],
        "manage": ["projects.update", "projects.delete"],
    },
    "project_assignments": {
        "view": ["projects.assign_employee"],
        "manage": ["projects.remove_assignment", "projects.update_assignment"],
    },
    # 17. Reports & Analytics
    "reports": {
        "view": ["reports.resource_utilization", "reports.billing_ratio", "reports.over_allocated", "reports.project_billing"],
        "manage": ["reports.resource_utilization", "reports.billing_ratio", "reports.over_allocated", "reports.project_billing"],
    },
}

def normalize_role(role):
    if not role:
        return 'employee'
    r = str(role).lower().strip().replace(' ', '').replace('_', '')
    if r in ['superadmin', 'super_admin', 'super admin']:
        return 'superadmin'
    if r in ['teammember', 'team_member']:
        return 'employee'
    if r in ['onboardingcandidate', 'onboarding_candidate']:
        return 'onboarding_candidate'
    return str(role).lower().strip()

def has_permission(user_or_role, feature_or_key, action=None) -> bool:
    """
    Central permission resolver: evaluates whether a user or role has permission.
    Supports:
      1. Direct permission key check: has_permission(user, 'employees.update')
      2. Feature + Action check: has_permission(user, 'employee_team_management', 'manage')
    """
    role = user_or_role.get("role") if isinstance(user_or_role, dict) else str(user_or_role or "")
    role = normalize_role(role)
    
    cache = get_permissions_cache()
    if not cache:
        return False
        
    fk = str(feature_or_key).lower().strip()
    act = str(action).lower().strip() if action else None

    # 1. Direct permission key check
    if (role, fk) in cache:
        if cache.get((role, fk), False):
            return True
        # Synonym fallback between employee and team_member
        if role == 'employee' and cache.get(('team_member', fk), False):
            return True
        if role == 'team_member' and cache.get(('employee', fk), False):
            return True
        if not act:
            return False

    # 2. Feature + action bundle check
    if fk in FEATURE_PERMISSION_MAP:
        act_key = act if act else "view"
        perm_keys = FEATURE_PERMISSION_MAP[fk].get(act_key, [])
        for pk in perm_keys:
            if cache.get((role, pk), False):
                return True
            if role == 'employee' and cache.get(('team_member', pk), False):
                return True
            if role == 'team_member' and cache.get(('employee', pk), False):
                return True
        return False

    return False

def get_role_permissions_summary(role):
    """
    Returns full permissions and feature_actions dictionary for a role.
    """
    role = normalize_role(role)
    cache = get_permissions_cache() or {}
    
    granted_keys = {}
    for (r, pk), is_granted in cache.items():
        if r == role and is_granted:
            granted_keys[pk] = True
        elif (role == 'employee' and r == 'team_member' and is_granted) or (role == 'team_member' and r == 'employee' and is_granted):
            granted_keys[pk] = True
            
    feature_actions = {}
    for f_key, actions in FEATURE_PERMISSION_MAP.items():
        feature_actions[f_key] = {}
        for act_name, pk_list in actions.items():
            feature_actions[f_key][act_name] = any(granted_keys.get(pk, False) for pk in pk_list)
            
    return {
        "role": role,
        "permissions": granted_keys,
        "feature_actions": feature_actions
    }

def permission_required(permission_key_or_feature, action=None):
    """Decorator: requires the user's role to have the given permission granted."""
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

            if not has_permission(current_user, permission_key_or_feature, action):
                return jsonify({
                    "success": False,
                    "error": f"Access denied. Missing permission: {permission_key_or_feature}" + (f" ({action})" if action else "")
                }), 403

            return f(current_user=current_user, *args, **kwargs)
        return decorated
    return decorator


def role_required(allowed_roles, permission_key=None, action=None):
    """
    Decorator: checks token, role, and optional dynamic permission.
    """
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

            # Check dynamic permission if specified
            if permission_key:
                if not has_permission(current_user, permission_key, action):
                    return jsonify({
                        "success": False,
                        "error": f"Access denied. Missing permission: {permission_key}"
                    }), 403
                return f(current_user=current_user, *args, **kwargs)

            # Role check
            user_role = normalize_role(current_user["role"])
            allowed_roles_lower = [normalize_role(r) for r in allowed_roles]

            if user_role not in allowed_roles_lower and user_role != 'superadmin':
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
                "user_id": data.get("user_id") or data.get("id"),
                "username": data.get("username", ""),
                "role": normalize_role(data.get("role", "employee")),
                "employee_name": data.get("employee_name") or data.get("username", "")
            }
        except Exception:
            return jsonify({"success": False, "error": "Invalid or expired token."}), 401

        if current_user["role"] != "superadmin":
            return jsonify({"success": False, "error": "Access denied. Superadmin only."}), 403

        return f(current_user=current_user, *args, **kwargs)
    return decorated


def onboarding_required(f):
    """Decorator: requires a valid JWT with role == onboarding_candidate."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"success": False, "message": "Token is missing. Please login first.", "error_code": "UNAUTHORIZED"}), 401

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

        if current_user["role"] != "onboarding_candidate":
            return jsonify({"success": False, "message": "Access denied.", "error_code": "FORBIDDEN"}), 403

        return f(current_user=current_user, *args, **kwargs)
    return decorated
