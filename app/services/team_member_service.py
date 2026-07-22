"""
Team Member Service Layer

This service provides modern terminology for team member operations.
It acts as the primary service layer using enterprise-grade terminology.

For backward compatibility with legacy code, see employee_service.py

Usage:
    from app.services.team_member_service import create_team_member_record, update_team_member_role
"""

from werkzeug.security import generate_password_hash
import re
from datetime import datetime
from app.models.database import execute_query, execute_single, Transaction
from app.services.leave_service import allocate_default_leaves
from app.utils.helpers import generate_unique_username, cascade_rename_employee, log_audit_event
from app.utils.display_name_service import strip_all_prefixes
from app.config.terminology import get_message, get_label, get_audit_event
from app.config.constants import (
    is_valid_gender, is_valid_employment_type,
    TEAM_MEMBER_CODE_PREFIX, TEAM_MEMBER_CODE_FORMAT,
    MAX_DESIGNATION_LENGTH, MAX_DEPARTMENT_LENGTH,
    MAX_ADDRESS_LENGTH, MAX_EMPLOYMENT_TYPE_LENGTH,
)
import logging

logger = logging.getLogger(__name__)

DEFAULT_TEMP_PASSWORD = "Welcome@123"


# ═════════════════════════════════════════════════════════════════════════
# PRIMARY SERVICE FUNCTIONS (Team Member terminology)
# ═════════════════════════════════════════════════════════════════════════

def generate_team_member_code(cursor):
    """
    Generate a unique team member code in TM-YYYY-NNNN format.
    
    Example: TM-2026-0001, TM-2026-0002
    
    Args:
        cursor: Database cursor (must be from an active transaction)
    
    Returns:
        Unique team member code string
    """
    year = datetime.now().year
    prefix = TEAM_MEMBER_CODE_PREFIX
    pattern = f"{prefix}-{year}-%"
    
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
    
    return TEAM_MEMBER_CODE_FORMAT.format(
        prefix=prefix, year=year, number=next_num
    )


def validate_team_member_fields(data):
    """
    Validate the new enterprise HR fields before insertion.
    
    Args:
        data: Dictionary containing team member fields
    
    Raises:
        ValueError: If any field fails validation
    """
    # Validate gender
    gender = data.get("gender")
    if gender and not is_valid_gender(gender):
        raise ValueError(
            f"Invalid gender: '{gender}'. "
            f"Allowed values: Male, Female, Other, Prefer Not to Say"
        )
    
    # Validate employment_type
    emp_type = data.get("employment_type")
    if emp_type and not is_valid_employment_type(emp_type):
        raise ValueError(
            f"Invalid employment type: '{emp_type}'. "
            f"Allowed values: Full Time, Intern, Contract Based, Part Time, Freelancer, Temporary"
        )
    
    # Validate field lengths
    designation = data.get("designation")
    if designation and len(designation) > MAX_DESIGNATION_LENGTH:
        raise ValueError(
            f"Designation must not exceed {MAX_DESIGNATION_LENGTH} characters"
        )
    
    department = data.get("department")
    if department and len(department) > MAX_DEPARTMENT_LENGTH:
        raise ValueError(
            f"Department must not exceed {MAX_DEPARTMENT_LENGTH} characters"
        )
    
    address = data.get("address")
    if address and len(address) > MAX_ADDRESS_LENGTH:
        raise ValueError(
            f"Address must not exceed {MAX_ADDRESS_LENGTH} characters"
        )


def create_team_member_record(data, role, cursor, with_user=True, created_by=None, user_id=0):
    """
    Core logic to create a team member record and optionally a linked user account.
    
    This is the primary service function using modern "Team Member" terminology.
    Internal database field names remain unchanged for production stability.
    
    Must be called within a database transaction.
    
    Args:
        data: Dictionary containing team member details (name, email, etc.)
        role: User role (admin, hr, manager, team_member)
        cursor: Database cursor (must be from an active transaction)
        with_user: Whether to create associated user account
        created_by: System ID of the user creating this team member
    
    Returns:
        Tuple of (team_member_system_id, original_name)
    
    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Strip ALL known role prefixes (including A_, HR_, duplicates like A_A_)
    raw_name = data.get("name", "") or data.get("team_member_name", "") or data.get("employee_name", "")
    clean_name = strip_all_prefixes(raw_name)
    
    if not clean_name:
        raise ValueError(get_message("required_field", field="Team Member name"))
    
    # Generate unique system name (e.g., Kartik or Kartik_1)
    team_member_id = generate_unique_username(clean_name, role, cursor)
    
    logger.info(f"Creating team member record for {clean_name} as {team_member_id} (Role: {role})")
    
    # Extract dates/fields (support multiple naming conventions for compatibility)
    dob = data.get("date_of_birth") or data.get("dob") or data.get("birthDate")
    dob = dob if dob else None
    
    doj = data.get("date_of_joining") or data.get("doj") or data.get("joiningDate")
    doj = doj if doj else None
    
    email = data.get("email") or data.get("username")
    
    if not email:
        raise ValueError(get_message("required_field", field="Email") + " (required for team member creation and login setup)")
    
    # Validate new enterprise HR fields
    validate_team_member_fields(data)
    
    # Extract new HR fields
    designation = data.get("designation")
    designation = designation if designation else None
    
    department = data.get("department")
    department = department if department else None
    
    gender = data.get("gender")
    gender = gender if gender else None
    
    address = data.get("address")
    address = address if address else None
    
    employment_type = data.get("employment_type")
    employment_type = employment_type if employment_type else None
    
    salary = data.get("salary")
    salary = salary if salary not in ["", None] else None
    
    phone = data.get("phone")
    phone = phone if phone else None
    
    # Auto-generate team member code
    team_member_code = generate_team_member_code(cursor)
    
    # 1. Insert team member record (uses "employee" table for production stability)
    cursor.execute("""
        INSERT INTO employee 
        (name, email, phone, salary, date_of_birth, date_of_joining, photo, pdf_file, docx_file,
         designation, department, gender, address, employment_type, team_member_code, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        team_member_id, email, phone,
        salary, dob, doj, data.get("photo_path"), 
        data.get("pdf_path"), data.get("docx_path"),
        designation, department,
        gender, address,
        employment_type, team_member_code, created_by
    ))
    
    # 2. Allocate leaves
    allocate_default_leaves(team_member_id, cursor)

    # 3. Create User Account (Login Credentials) with sanitized email as username
    if with_user:
        sanitized_username = email.strip().lower()
        logger.info(f"Generating login account for {sanitized_username}")
        hashed_password = generate_password_hash(DEFAULT_TEMP_PASSWORD)
        # Fetch the integer ID of the newly created employee to link the user account
        cursor.execute("SELECT id FROM employee WHERE name = %s", (team_member_id,))
        emp_row = cursor.fetchone()
        employee_pk = emp_row['id'] if isinstance(emp_row, dict) else emp_row[0]

        cursor.execute("""
            INSERT INTO users (
                username, password, role, employee_name, password_change_required, is_active,
                email, password_hash, employee_id
            )
            VALUES (%s, %s, %s, %s, TRUE, TRUE, %s, %s, %s)
        """, (
            sanitized_username, hashed_password, role, team_member_id,
            sanitized_username, hashed_password, employee_pk
        ))
    
    # 4. Log audit event with modern terminology
    log_audit_event(
        user_id,
        event_type="team_member_created",
        description=get_audit_event("entity_created", name=clean_name)
    )
    
    logger.info(
        f"Team member created: {team_member_id} | Code: {team_member_code} | "
        f"Dept: {department} | Designation: {designation} | Type: {employment_type}"
    )
    
    return team_member_id, clean_name


def update_team_member_role(actor_user_id, target_user_id, new_role):
    """
    Update users role and ensure team member status consistency.
    Includes guardrail: only superadmin can assign or modify admin/superadmin roles.
    """
    valid_roles = ["employee", "manager", "hr", "admin", "team_member", "superadmin"]
    if new_role not in valid_roles:
        raise ValueError("Invalid role provided")

    with Transaction() as cursor:
        target = execute_single("SELECT role, employee_name FROM users WHERE id = %s", (target_user_id,))
        if not target:
            raise ValueError("User not found")
        old_role = target["role"]
        system_id = target["employee_name"]
        
        actor = execute_single("SELECT role FROM users WHERE id = %s", (actor_user_id,))
        if not actor:
            raise ValueError("Actor user not found")
        actor_role = actor["role"]
        
        if (old_role in ['admin', 'superadmin'] or new_role in ['admin', 'superadmin']) and actor_role != 'superadmin':
            raise ValueError("Only superadmin can modify or assign admin/superadmin roles.")
            
        if old_role == new_role:
            return {
                "success": True, 
                "message": f"Entity already has this role.", 
                "no_change": True,
                "reauth_required": False
            }
        logger.info(f"Updating team member role: {system_id} ({old_role}) -> ({new_role})")

        # 3. Atomic Updates: Authentication & Profile
        # Because we no longer use prefixed names, the system_id remains exactly the same!
        # There is NO NEED to cascade rename across 15+ tables.
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
            f"{get_label('entity')} Role Updated", 
            get_message("role_updated", 
                       entity=get_label('entity'),
                       old_role=old_role.upper(), 
                       new_role=new_role.upper())
        ))

        # 6. Security Audit Logging
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (actor_user_id, "role_change", 
              get_audit_event("entity_role_changed", 
                            name=system_id) + f" ({old_role} → {new_role})"))

        return {
            "success": True,
            "message": get_message("updated_with_name", name=system_id),
            "data": {
                "old_role": old_role,
                "new_role": new_role,
                "old_id": system_id,
                "new_id": system_id,
                "reauth_required": True
            }
        }


def get_team_member(team_member_id: int):
    """
    Fetch team member details by ID.
    
    Args:
        team_member_id: Team member database ID
    
    Returns:
        Team member record or None
    """
    return execute_single(
        "SELECT * FROM employee WHERE id = %s",
        (team_member_id,)
    )


def get_team_member_by_name(team_member_system_id: str):
    """
    Fetch team member details by system ID (e.g., T_Kartik).
    
    Args:
        team_member_system_id: Team member system identifier (e.g., T_Kartik)
    
    Returns:
        Team member record or None
    """
    return execute_single(
        "SELECT * FROM employee WHERE name = %s",
        (team_member_system_id,)
    )


def list_team_members(role_filter=None, status_filter=None, limit=None, offset=0):
    """
    List all team members with optional filters.
    
    Args:
        role_filter: Filter by role (admin, hr, manager, team_member)
        status_filter: Filter by status (working, bench, over_allocated)
        limit: Maximum number of results
        offset: Result offset for pagination
    
    Returns:
        List of team member records
    """
    query = "SELECT * FROM employee WHERE 1=1"
    params = []
    
    if role_filter:
        query += " AND role = %s"
        params.append(role_filter)
    
    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)
    
    query += " ORDER BY name ASC"
    
    if limit:
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
    
    return execute_query(query, params)


def update_team_member(team_member_id: int, update_data: dict, updated_by: str = None):
    """
    Update team member profile information.
    
    Args:
        team_member_id: Team member database ID
        update_data: Dictionary of fields to update
        updated_by: System ID of the user making the update
    
    Returns:
        Updated team member record
    """
    allowed_fields = [
        'email', 'phone', 'salary', 'date_of_birth', 'date_of_joining', 'photo',
        'designation', 'department', 'gender', 'address','reporting_manager', 'employment_type',
    ]
    
    # Filter to allowed fields
    updates = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if not updates:
        raise ValueError("No valid fields to update")
    
    # Validate new HR fields if present
    validate_team_member_fields(updates)
    
    # Add updated_by audit field
    if updated_by:
        updates['updated_by'] = updated_by
    
    # Build dynamic UPDATE query
    set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
    query = f"UPDATE employee SET {set_clause}, updated_at = NOW() WHERE id = %s"
    params = list(updates.values()) + [team_member_id]
    
    execute_query(query, params, commit=True)
    
    # Log audit event
    log_audit_event(
        event_type="team_member_updated",
        description=get_audit_event("entity_updated") + f" (ID: {team_member_id})"
    )
    
    return get_team_member(team_member_id)


def delete_team_member(team_member_id: int, admin_id: int):
    """
    Soft delete a team member (preserves audit trail).
    
    Args:
        team_member_id: Team member database ID
        admin_id: Admin ID performing the deletion
    
    Returns:
        Success status
    """
    with Transaction() as cursor:
        # Get team member info before deletion
        cursor.execute("SELECT name FROM employee WHERE id = %s", (team_member_id,))
        team_member = cursor.fetchone()
        
        if not team_member:
            raise ValueError(get_message("not_found"))
        
        # Soft delete (set is_deleted flag if exists, or just mark inactive)
        cursor.execute(
            "UPDATE employee SET deleted_at = NOW() WHERE id = %s",
            (team_member_id,)
        )
        
        # Audit log
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (admin_id, "team_member_deleted", 
              get_audit_event("entity_deleted", name=team_member['name'])))
    
    return {"success": True, "message": get_message("deleted_success")}


# ═════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY WRAPPERS
# ═════════════════════════════════════════════════════════════════════════

# Export functions with both old and new names for transition period
create_employee_record = create_team_member_record
update_employee_role = update_team_member_role
