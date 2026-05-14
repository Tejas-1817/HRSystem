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
from app.models.database import execute_query, execute_single, Transaction
from app.services.leave_service import allocate_default_leaves
from app.utils.helpers import generate_unique_username, cascade_rename_employee, log_audit_event
from app.config.terminology import get_message, get_label, get_audit_event
import logging

logger = logging.getLogger(__name__)

DEFAULT_TEMP_PASSWORD = "Welcome@123"


# ═════════════════════════════════════════════════════════════════════════
# PRIMARY SERVICE FUNCTIONS (Team Member terminology)
# ═════════════════════════════════════════════════════════════════════════

def create_team_member_record(data, role, cursor, with_user=True):
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
    
    Returns:
        Tuple of (team_member_system_id, original_name)
    
    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Strip any prefix the frontend may have added
    original_name = re.sub(r'^[HMT]_', '', data.get("name", "") or data.get("team_member_name", "") or data.get("employee_name", ""))
    
    if not original_name:
        raise ValueError(get_message("required_field", field="Team Member name"))
    
    # Generate unique system name (e.g., T_Kartik)
    team_member_id = generate_unique_username(original_name, role, cursor)
    
    logger.info(f"Creating team member record for {original_name} as {team_member_id} (Role: {role})")
    
    # Extract dates/fields (support multiple naming conventions for compatibility)
    dob = data.get("date_of_birth") or data.get("dob") or data.get("birthDate")
    doj = data.get("date_of_joining") or data.get("doj") or data.get("joiningDate")
    email = data.get("email") or data.get("username")
    
    if not email:
        raise ValueError(get_message("required_field", field="Email") + " (required for team member creation and login setup)")
    
    # 1. Insert team member record (uses "employee" table for production stability)
    # Note: Database table names remain unchanged to avoid migration burden
    cursor.execute("""
        INSERT INTO employee 
        (name, original_name, email, phone, salary, date_of_birth, date_of_joining, photo, pdf_file, docx_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        team_member_id, original_name, email, data.get("phone"),
        data.get("salary"), dob, doj, data.get("photo_path"), 
        data.get("pdf_path"), data.get("docx_path")
    ))
    
    # 2. Allocate leaves
    allocate_default_leaves(team_member_id, cursor)

    # 3. Create User Account (Login Credentials) with sanitized email as username
    if with_user:
        sanitized_username = email.strip().lower()
        logger.info(f"Generating login account for {sanitized_username}")
        hashed_password = generate_password_hash(DEFAULT_TEMP_PASSWORD)
        cursor.execute("""
            INSERT INTO users (username, original_name, password, role, employee_name, password_change_required, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
        """, (sanitized_username, original_name, hashed_password, role, team_member_id))
    
    # 4. Log audit event with modern terminology
    log_audit_event(
        event_type="team_member_created",
        description=get_audit_event("entity_created", name=original_name)
    )
    
    return team_member_id, original_name


def update_team_member_role(admin_id, team_member_id, new_role):
    """
    Updates a team member's role with full atomic integrity.
    
    Handles prefix-based naming changes (e.g., T_ -> M_) across the entire system.
    Returns success status and a flag indicating if the user must re-authenticate.
    
    Args:
        admin_id: ID of the admin making the change
        team_member_id: ID of the team member whose role is being updated
        new_role: New role to assign (admin, hr, manager, team_member)
    
    Returns:
        Dictionary with success status, message, and role change details
    
    Raises:
        ValueError: If role is invalid or team member not found
    """
    valid_roles = ['admin', 'hr', 'manager', 'team_member', 'employee']  # Include 'employee' for backward compat
    if new_role not in valid_roles:
        raise ValueError(f"Invalid role: {new_role}. Must be one of {', '.join(valid_roles)}")

    with Transaction() as cursor:
        # 1. Fetch current state
        cursor.execute("SELECT id, role, employee_name, original_name FROM users WHERE id=%s", (team_member_id,))
        user = cursor.fetchone()
        
        if not user:
            raise ValueError(get_message("not_found"))
        
        old_role = user['role']
        old_team_member_id = user['employee_name']
        original_name = user['original_name']

        # 2. Early exit if no change needed
        if old_role == new_role:
            return {
                "success": True, 
                "message": f"{get_label('entity')} already has this role.", 
                "no_change": True,
                "reauth_required": False
            }

        # 3. Generate new prefixed system identity
        new_team_member_id = generate_unique_username(original_name, new_role, cursor)
        
        logger.info(f"Updating team member role: {old_team_member_id} ({old_role}) -> {new_team_member_id} ({new_role})")

        # 4. Atomic Updates: Authentication & Profile
        cursor.execute("UPDATE users SET role=%s, employee_name=%s WHERE id=%s", 
                      (new_role, new_team_member_id, team_member_id))
        cursor.execute("UPDATE employee SET role=%s, name=%s WHERE name=%s", 
                      (new_role, new_team_member_id, old_team_member_id))

        # 5. Global Data Consistency: Cascade Rename
        cascade_rename_employee(old_team_member_id, new_team_member_id, cursor)

        # 6. Compliance & Audit: Role History
        cursor.execute("""
            INSERT INTO role_history (employee_name, old_role, new_role, changed_by_user_id, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (new_team_member_id, old_role, new_role, admin_id, 
              f"Role updated by Admin {admin_id}"))

        # 7. Lifecycle Event: Internal Notification
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, 'security_alert')
        """, (
            new_team_member_id, 
            f"{get_label('entity')} Role Updated", 
            get_message("role_updated", 
                       entity=get_label('entity'),
                       old_role=old_role.upper(), 
                       new_role=new_role.upper())
        ))

        # 8. Audit Logging with modern terminology
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (admin_id, "role_change", 
              get_audit_event("entity_role_changed", 
                            name=original_name) + f" ({old_role} → {new_role})"))

        return {
            "success": True,
            "message": get_message("updated_with_name", name=original_name),
            "data": {
                "old_role": old_role,
                "new_role": new_role,
                "old_id": old_team_member_id,
                "new_id": new_team_member_id,
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


def update_team_member(team_member_id: int, update_data: dict):
    """
    Update team member profile information.
    
    Args:
        team_member_id: Team member database ID
        update_data: Dictionary of fields to update
    
    Returns:
        Updated team member record
    """
    allowed_fields = ['email', 'phone', 'salary', 'date_of_birth', 'date_of_joining', 'photo']
    
    # Filter to allowed fields
    updates = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if not updates:
        raise ValueError("No valid fields to update")
    
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
        cursor.execute("SELECT name, original_name FROM employee WHERE id = %s", (team_member_id,))
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
              get_audit_event("entity_deleted", name=team_member['original_name'])))
    
    return {"success": True, "message": get_message("deleted_success")}


# ═════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY WRAPPERS
# ═════════════════════════════════════════════════════════════════════════

# Export functions with both old and new names for transition period
create_employee_record = create_team_member_record
update_employee_role = update_team_member_role
