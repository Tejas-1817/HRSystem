from flask import Blueprint, request, jsonify
from app.api.middleware.auth import superadmin_required, refresh_permissions_cache
from app.models.database import execute_query, execute_single, Transaction
import logging

logger = logging.getLogger(__name__)
superadmin_bp = Blueprint('superadmin', __name__)

@superadmin_bp.route("/admin/permissions", methods=["GET"])
@superadmin_required
def get_permissions(current_user):
    """
    Returns full catalog grouped by module with grant matrix.
    """
    try:
        permissions = execute_query("SELECT * FROM permissions ORDER BY module, label")
        role_permissions = execute_query("SELECT * FROM role_permissions")
        
        # Structure the response: a list of modules, each containing permissions, each with a grant matrix
        modules = {}
        for p in permissions:
            mod = p["module"]
            if mod not in modules:
                modules[mod] = []
            
            # Find grants for this permission
            grants = {}
            for rp in role_permissions:
                if rp["permission_id"] == p["id"]:
                    grants[rp["role"]] = bool(rp["is_granted"])
                    
            modules[mod].append({
                "id": p["id"],
                "key": p["permission_key"],
                "label": p["label"],
                "description": p["description"],
                "route": p["route_reference"],
                "grants": grants
            })
            
        return jsonify({"success": True, "modules": modules}), 200
    except Exception as e:
        logger.error(f"Error fetching permissions: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

@superadmin_bp.route("/admin/permissions/<int:permission_id>/role/<string:role>", methods=["PATCH"])
@superadmin_required
def toggle_permission(current_user, permission_id, role):
    """
    Toggle a permission grant for a specific role.
    """
    try:
        data = request.get_json()
        is_granted = bool(data.get("is_granted"))
        
        with Transaction() as cursor:
            # Check current state
            cursor.execute("SELECT is_granted FROM role_permissions WHERE permission_id = %s AND role = %s", (permission_id, role))
            existing = cursor.fetchone()
            
            if not existing:
                return jsonify({"success": False, "error": "Permission or role not found"}), 404
                
            old_value = bool(existing["is_granted"])
            
            if old_value != is_granted:
                # Update
                cursor.execute("""
                    UPDATE role_permissions 
                    SET is_granted = %s, updated_by = %s 
                    WHERE permission_id = %s AND role = %s
                """, (is_granted, current_user["user_id"], permission_id, role))
                
                # Audit log
                cursor.execute("""
                    INSERT INTO role_permission_audit_log 
                    (role, permission_id, old_value, new_value, changed_by, changed_by_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (role, permission_id, old_value, is_granted, current_user["user_id"], current_user["employee_name"] or current_user["username"]))
                
        # Refresh the cache in process
        refresh_permissions_cache()
        
        return jsonify({"success": True, "message": "Permission updated successfully"}), 200
    except Exception as e:
        logger.error(f"Error toggling permission: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

@superadmin_bp.route("/admin/permissions/reset-defaults", methods=["POST"])
@superadmin_required
def reset_defaults(current_user):
    """
    Restore seeded defaults for a role (or all roles).
    This just runs the logic from run_025.py for the specific role.
    """
    try:
        data = request.get_json() or {}
        role = data.get("role")
        
        # Import the SEED_PERMISSIONS from our migration
        import sys, os
        # Path hack to import from migrations
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../database/migrations')))
        try:
            from run_025 import SEED_PERMISSIONS, CONFIGURABLE_ROLES
        except ImportError:
            return jsonify({"success": False, "error": "Seed data not found"}), 500
            
        roles_to_reset = [role] if role else CONFIGURABLE_ROLES
        
        with Transaction() as cursor:
            for p_key, module, label, route_ref, granted_roles in SEED_PERMISSIONS:
                cursor.execute("SELECT id FROM permissions WHERE permission_key = %s", (p_key,))
                p_id_res = cursor.fetchone()
                if not p_id_res:
                    continue
                perm_id = p_id_res["id"]
                
                for r in roles_to_reset:
                    is_granted = r in granted_roles
                    
                    cursor.execute("SELECT is_granted FROM role_permissions WHERE permission_id = %s AND role = %s", (perm_id, r))
                    existing = cursor.fetchone()
                    if existing:
                        old_value = bool(existing["is_granted"])
                        if old_value != is_granted:
                            cursor.execute("""
                                UPDATE role_permissions 
                                SET is_granted = %s, updated_by = %s 
                                WHERE permission_id = %s AND role = %s
                            """, (is_granted, current_user["user_id"], perm_id, r))
                            
                            cursor.execute("""
                                INSERT INTO role_permission_audit_log 
                                (role, permission_id, old_value, new_value, changed_by, changed_by_name)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (r, perm_id, old_value, is_granted, current_user["user_id"], current_user["employee_name"] or current_user["username"]))

        refresh_permissions_cache()
        
        return jsonify({"success": True, "message": "Defaults restored successfully"}), 200
    except Exception as e:
        logger.error(f"Error resetting permissions: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@superadmin_bp.route("/admin/permissions/audit-log", methods=["GET"])
@superadmin_required
def get_audit_log(current_user):
    """
    Returns the change history of permissions.
    """
    try:
        logs = execute_query("""
            SELECT l.*, p.permission_key, p.label, p.module
            FROM role_permission_audit_log l
            JOIN permissions p ON l.permission_id = p.id
            ORDER BY l.changed_at DESC
            LIMIT 200
        """)
        return jsonify({"success": True, "logs": logs}), 200
    except Exception as e:
        logger.error(f"Error fetching permission audit log: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
