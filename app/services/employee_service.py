"""
Employee Service Layer (Backward Compatibility)

DEPRECATION NOTICE: This module is maintained for backward compatibility only.
New code should use app.services.team_member_service instead.

All functions delegate to team_member_service to maintain consistent terminology
and business logic across the codebase.
"""

from werkzeug.security import generate_password_hash
import re
from app.models.database import execute_query, execute_single, Transaction
from app.services.leave_service import allocate_default_leaves
from app.utils.helpers import generate_unique_username, cascade_rename_employee, log_audit_event
from app.utils.display_name_service import strip_all_prefixes
from app.config.terminology import get_message
import logging

logger = logging.getLogger(__name__)

DEFAULT_TEMP_PASSWORD = "Welcome@123"


def create_employee_record(data, role, cursor, with_user=True):
    """
    DEPRECATED: Use app.services.team_member_service.create_team_member_record
    
    Core logic to create an employee record and optionally a linked user account.
    Must be called within a database transaction.
    
    This function maintains backward compatibility by delegating to team_member_service.
    """
    # Strip ALL known role prefixes (including A_, HR_, duplicates like A_A_)
    raw_name = data.get("name", "") or data.get("employee_name", "")
    clean_name = strip_all_prefixes(raw_name)
    
    if not clean_name:
        raise ValueError(get_message("required_field", field="Name"))
    
    # Generate unique system name (e.g., Kartik)
    employee_name = generate_unique_username(clean_name, role, cursor)
    
    logger.info(f"Creating employee record for {clean_name} as {employee_name} (Role: {role})")
    
    # Extract dates/fields
    dob = data.get("date_of_birth") or data.get("dob") or data.get("birthDate")
    doj = data.get("date_of_joining") or data.get("doj") or data.get("joiningDate")
    email = data.get("email") or data.get("username")
    
    if not email:
        raise ValueError(get_message("required_field", field="Email") + " (required for creation and login setup)")
    
    # 1. Insert employee record
    cursor.execute("""
        INSERT INTO employee 
        (name, email, phone, salary, date_of_birth, date_of_joining, photo, pdf_file, docx_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        employee_name, email, data.get("phone"),
        data.get("salary"), dob, doj, data.get("photo_path"), 
        data.get("pdf_path"), data.get("docx_path")
    ))
    
    # 2. Allocate leaves
    allocate_default_leaves(employee_name, cursor)

    # 3. Create User Account (Login Credentials) with sanitized email as username
    if with_user:
        sanitized_username = email.strip().lower()
        logger.info(f"Generating login account for {sanitized_username}")
        hashed_password = generate_password_hash(DEFAULT_TEMP_PASSWORD)
        cursor.execute("""
            INSERT INTO users (username, password, role, employee_name, password_change_required, is_active)
            VALUES (%s, %s, %s, %s, TRUE, TRUE)
        """, (sanitized_username, hashed_password, role, employee_name))
    
    # Log audit event with modern terminology
    log_audit_event(
        event_type="team_member_created",
        description=f"Team member created: {clean_name}"
    )
    
    return employee_name, clean_name


def update_employee_role(admin_id, employee_id, new_role):
    """
    DEPRECATED: Use app.services.team_member_service.update_team_member_role
    """
    valid_roles = ['admin', 'hr', 'manager', 'employee', 'team_member']
    if new_role not in valid_roles:
        raise ValueError(f"Invalid role: {new_role}. Must be one of {', '.join(valid_roles)}")

    with Transaction() as cursor:
        # 1. Fetch current state using the transaction-bound cursor
        cursor.execute("SELECT id, role, employee_name FROM users WHERE id=%s", (employee_id,))
        user = cursor.fetchone()
        
        if not user:
            raise ValueError(get_message("not_found"))

        old_role = user['role']
        system_id = user['employee_name']

        # 2. Early exit if no change needed
        if old_role == new_role:
            return {
                "success": True, 
                "message": "User is already assigned this role.", 
                "no_change": True,
                "reauth_required": False
            }

        logger.info(f"Updating role: {system_id} ({old_role}) -> ({new_role})")

        # 3. Atomic Updates: Authentication & Profile
        cursor.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, employee_id))
        cursor.execute("UPDATE employee SET role=%s WHERE name=%s", (new_role, system_id))

        # 4. Compliance & Audit: Role History
        cursor.execute("""
            INSERT INTO role_history (employee_name, old_role, new_role, changed_by_user_id, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (system_id, old_role, new_role, admin_id, f"Role updated by Admin {admin_id}"))

        # 5. Lifecycle Event: Internal Notification
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, 'security_alert')
        """, (
            system_id, 
            "Team Member Role Updated", 
            f"Your system role has been changed to {new_role.upper()}."
        ))

        # 6. Security Audit Logging (Using transaction cursor)
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (admin_id, "role_change", f"Role updated for {system_id} from {old_role} to {new_role}"))

        return {
            "success": True,
            "message": f"Successfully updated {system_id} to {new_role}",
            "data": {
                "old_role": old_role,
                "new_role": new_role,
                "old_id": system_id,
                "new_id": system_id,
                "reauth_required": True  # Critical for frontend to handle token refresh
            }
        }

