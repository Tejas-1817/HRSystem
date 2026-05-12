from werkzeug.security import generate_password_hash
import re
from app.models.database import execute_query, execute_single, Transaction
from app.services.leave_service import allocate_default_leaves
from app.utils.helpers import generate_unique_username, cascade_rename_employee, log_audit_event
import logging

logger = logging.getLogger(__name__)

DEFAULT_TEMP_PASSWORD = "Welcome@123"

def create_employee_record(data, role, cursor, with_user=True):
    """
    Core logic to create an employee record and optionally a linked user account.
    Must be called within a database transaction.
    """
    # Strip any prefix the frontend may have added
    original_name = re.sub(r'^[HMT]_', '', data.get("name", "") or data.get("employee_name", ""))
    
    if not original_name:
        raise ValueError("Employee name is required")
    
    # Generate unique system name (e.g., T_Kartik)
    employee_name = generate_unique_username(original_name, role, cursor)
    
    logger.info(f"Creating employee record for {original_name} as {employee_name} (Role: {role})")
    
    # Extract dates/fields
    dob = data.get("date_of_birth") or data.get("dob") or data.get("birthDate")
    doj = data.get("date_of_joining") or data.get("doj") or data.get("joiningDate")
    email = data.get("email") or data.get("username")
    
    if not email:
        raise ValueError("Email is required for employee creation and login setup")
    
    # 1. Insert employee record
    cursor.execute("""
        INSERT INTO employee 
        (name, original_name, email, phone, salary, date_of_birth, date_of_joining, photo, pdf_file, docx_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        employee_name, original_name, email, data.get("phone"),
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
            INSERT INTO users (username, original_name, password, role, employee_name, password_change_required, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
        """, (sanitized_username, original_name, hashed_password, role, employee_name))
    
    return employee_name, original_name


def update_employee_role(admin_id, employee_id, new_role):
    """
    Updates an employee's role with full atomic integrity.
    Handles prefix-based naming changes (e.g. T_ -> M_) across the entire system.
    Returns success status and a flag indicating if the user must re-authenticate.
    """
    valid_roles = ['admin', 'hr', 'manager', 'employee']
    if new_role not in valid_roles:
        raise ValueError(f"Invalid role: {new_role}. Must be one of {', '.join(valid_roles)}")

    with Transaction() as cursor:
        # 1. Fetch current state using the transaction-bound cursor
        cursor.execute("SELECT id, role, employee_name, original_name FROM users WHERE id=%s", (employee_id,))
        user = cursor.fetchone()
        
        if not user:
            raise ValueError("Employee user account not found.")

        old_role = user['role']
        old_employee_name = user['employee_name']
        original_name = user['original_name']

        # 2. Early exit if no change needed
        if old_role == new_role:
            return {
                "success": True, 
                "message": "User is already assigned this role.", 
                "no_change": True,
                "reauth_required": False
            }

        # 3. Generate new prefixed system identity (e.g. T_Kartik -> M_Kartik)
        new_employee_name = generate_unique_username(original_name, new_role, cursor)
        
        logger.info(f"ARCHITECT_LOG: Transitioning {old_employee_name} ({old_role}) -> {new_employee_name} ({new_role})")

        # 4. Atomic Updates: Authentication & Profile
        # Update users table (Role & System ID)
        cursor.execute("UPDATE users SET role=%s, employee_name=%s WHERE id=%s", (new_role, new_employee_name, employee_id))
        
        # Update employee table (Role & Primary Name)
        cursor.execute("UPDATE employee SET role=%s, name=%s WHERE name=%s", (new_role, new_employee_name, old_employee_name))

        # 5. Global Data Consistency: Cascade Rename
        # This updates all 15+ linked tables (Leaves, Timesheets, etc.)
        cascade_rename_employee(old_employee_name, new_employee_name, cursor)

        # 6. Compliance & Audit: Role History
        cursor.execute("""
            INSERT INTO role_history (employee_name, old_role, new_role, changed_by_user_id, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (new_employee_name, old_role, new_role, admin_id, f"Role escalated/changed by Admin {admin_id}"))

        # 7. Lifecycle Event: Internal Notification
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, 'security_alert')
        """, (
            new_employee_name, 
            "Access Role Updated", 
            f"Your system role has been changed to {new_role.upper()}. Your new system ID is {new_employee_name}."
        ))

        # 8. Security Audit Logging (Using transaction cursor)
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (admin_id, "RBAC_UPDATE", f"Admin changed role for {original_name} from {old_role} to {new_role}"))

        # If we reach here, Transaction.__exit__ will call self.conn.commit()
        return {
            "success": True,
            "message": f"Successfully updated {original_name} to {new_role}",
            "data": {
                "old_role": old_role,
                "new_role": new_role,
                "old_id": old_employee_name,
                "new_id": new_employee_name,
                "reauth_required": True  # Critical for frontend to handle token refresh
            }
        }

