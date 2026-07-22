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


def create_employee_record(data, role, cursor, with_user=True, created_by=None, user_id=0):
    """
    DEPRECATED: Use app.services.team_member_service.create_team_member_record
    
    Core logic to create an employee record and optionally a linked user account.
    Must be called within a database transaction.
    
    This function maintains backward compatibility by implementing the same logic
    as team_member_service, including the new enterprise HR fields.
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
    
    # Extract new HR fields (backward compat: these are optional)
    designation = data.get("designation")
    department = data.get("department")
    gender = data.get("gender")
    address = data.get("address")
    employment_type = data.get("employment_type")
    
    # Auto-generate team member code
    from datetime import datetime
    year = datetime.now().year
    pattern = f"TM-{year}-%"
    cursor.execute(
        "SELECT team_member_code FROM employee "
        "WHERE team_member_code LIKE %s "
        "ORDER BY team_member_code DESC LIMIT 1",
        (pattern,)
    )
    last = cursor.fetchone()
    if last:
        last_code = last['team_member_code'] if isinstance(last, dict) else last[0]
        try:
            last_num = int(last_code.split('-')[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    team_member_code = f"TM-{year}-{next_num:04d}"
    
    # 1. Insert employee record (with new HR fields)
    cursor.execute("""
        INSERT INTO employee 
        (name, email, phone, salary, date_of_birth, date_of_joining, photo, pdf_file, docx_file,
         designation, department, gender, address, employment_type, team_member_code, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        employee_name, email, data.get("phone"),
        data.get("salary"), dob, doj, data.get("photo_path"), 
        data.get("pdf_path"), data.get("docx_path"),
        designation, department, gender, address, employment_type,
        team_member_code, created_by
    ))
    
    # 2. Allocate leaves
    allocate_default_leaves(employee_name, cursor)

    # 3. Create User Account (Login Credentials) with sanitized email as username
    if with_user:
        sanitized_username = email.strip().lower()
        logger.info(f"Generating login account for {sanitized_username}")
        hashed_password = generate_password_hash(DEFAULT_TEMP_PASSWORD)
        # Fetch the integer ID of the newly created employee to link the user account
        cursor.execute("SELECT id FROM employee WHERE name = %s", (employee_name,))
        emp_row = cursor.fetchone()
        employee_pk = emp_row['id'] if isinstance(emp_row, dict) else emp_row[0]

        cursor.execute("""
            INSERT INTO users (
                username, password, role, employee_name, password_change_required, is_active,
                email, password_hash, employee_id
            )
            VALUES (%s, %s, %s, %s, TRUE, TRUE, %s, %s, %s)
        """, (
            sanitized_username, hashed_password, role, employee_name,
            sanitized_username, hashed_password, employee_pk
        ))
    
    # Log audit event with modern terminology
    log_audit_event(
        user_id,
        event_type="team_member_created",
        description=f"Team member created: {clean_name}"
    )
    
    return employee_name, clean_name


def update_employee_role(actor_user_id, target_user_id, new_role):
    """
    Update a user's role and ensure employee status consistency.
    Includes guardrail: only superadmin can assign or modify admin/superadmin roles.
    """
    valid_roles = ["employee", "manager", "hr", "admin", "team_member", "superadmin"]
    if new_role not in valid_roles:
        raise ValueError("Invalid role provided")

    with Transaction() as cursor:
        # Get target user's old role
        target = execute_single("SELECT role, employee_name FROM users WHERE id = %s", (target_user_id,))
        if not target:
            raise ValueError("Target user not found")
        old_role = target["role"]
        system_id = target["employee_name"]
        
        # Get actor user's role
        actor = execute_single("SELECT role FROM users WHERE id = %s", (actor_user_id,))
        if not actor:
            raise ValueError("Actor user not found")
        actor_role = actor["role"]
        
        if (old_role in ['admin', 'superadmin'] or new_role in ['admin', 'superadmin']) and actor_role != 'superadmin':
            raise ValueError("Only superadmin can modify or assign admin/superadmin roles.")

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
        cursor.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, target_user_id))
        cursor.execute("UPDATE employee SET role=%s WHERE name=%s", (new_role, system_id))

        # 4. Compliance & Audit: Role History
        cursor.execute("""
            INSERT INTO role_history (employee_name, old_role, new_role, changed_by_user_id, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (system_id, old_role, new_role, actor_user_id, f"Role updated by Admin {actor_user_id}"))

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
        """, (actor_user_id, "role_change", f"Role updated for {system_id} from {old_role} to {new_role}"))

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

