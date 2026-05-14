"""
Centralized Terminology Management

This module provides a single source of truth for enterprise terminology,
enabling consistent branding across the entire backend system while
supporting easy migration and future rebranding efforts.

Usage:
    from app.config.terminology import TERMINOLOGY, get_label, format_message
    
    # Get singular/plural labels
    label = get_label("entity")  # "Team Member"
    plural = get_label("entity_plural")  # "Team Members"
    
    # Format messages with terminology
    message = format_message("not_found")  # "{Team Member} not found"
"""

from typing import Dict, Any, Optional


class TerminologyConfig:
    """
    Enterprise-grade terminology configuration supporting:
    - Global branding control
    - i18n readiness
    - Backward compatibility
    - Scalable terminology expansion
    """
    
    # ─────────────────────────────────────────────────────────────────────
    # ENTITY LABELS (Primary terminology)
    # ─────────────────────────────────────────────────────────────────────
    ENTITY_LABELS = {
        # Current terminology (Team Member)
        "entity": "Team Member",
        "entity_plural": "Team Members",
        "entity_singular": "Team Member",
        "entity_lowercase": "team member",
        "entity_lowercase_plural": "team members",
        "entity_title_case": "TeamMember",
        "entity_snake_case": "team_member",
        "entity_kebab_case": "team-member",
        
        # Legacy terminology (for backward compatibility)
        "legacy_entity": "Employee",
        "legacy_entity_plural": "Employees",
        "legacy_entity_lowercase": "employee",
        "legacy_entity_lowercase_plural": "employees",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # DATABASE & ORM FIELD MAPPING
    # ─────────────────────────────────────────────────────────────────────
    DATABASE_MAPPING = {
        # Table names (unchanged - production stability)
        "table_employee": "employee",
        "table_users": "users",
        
        # Field names (unchanged in DB - production stability)
        "field_employee_name": "employee_name",
        "field_name": "name",
        "field_email": "email",
        
        # ORM relationship aliases (can be updated in models)
        "orm_relationship_name": "team_members",
        "orm_relationship_singular": "team_member",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # API RESPONSE FIELD MAPPING
    # ─────────────────────────────────────────────────────────────────────
    API_RESPONSE_FIELDS = {
        # Field name mappings for JSON responses
        "employee_name": "teamMemberName",
        "employee_id": "teamMemberId",
        "employee_email": "teamMemberEmail",
        "employee_count": "teamMemberCount",
        "created_employee": "createdTeamMember",
        "updated_employee": "updatedTeamMember",
        "deleted_employee": "deletedTeamMember",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # API ENDPOINT PATHS
    # ─────────────────────────────────────────────────────────────────────
    API_ENDPOINTS = {
        # Primary modern endpoints
        "list_team_members": "/api/v1/team-members",
        "get_team_member": "/api/v1/team-members/<id>",
        "create_team_member": "/api/v1/team-members",
        "update_team_member": "/api/v1/team-members/<id>",
        "delete_team_member": "/api/v1/team-members/<id>",
        
        # Legacy endpoints (backward compatibility)
        "legacy_list_employees": "/api/v1/employees",
        "legacy_get_employee": "/api/v1/employees/<id>",
        "legacy_create_employee": "/api/v1/employees",
        "legacy_update_employee": "/api/v1/employees/<id>",
        "legacy_delete_employee": "/api/v1/employees/<id>",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # VALIDATION & ERROR MESSAGES
    # ─────────────────────────────────────────────────────────────────────
    MESSAGES = {
        # Not found errors
        "not_found": "{entity} not found",
        "not_found_with_id": "{entity} with ID {id} not found",
        
        # Validation errors
        "required_field": "{field} is required",
        "invalid_email": "Invalid email format",
        "duplicate_email": "Email already registered for a {entity}",
        
        # Creation messages
        "created_success": "{entity} created successfully",
        "created_with_name": "{entity} {name} created successfully",
        
        # Update messages
        "updated_success": "{entity} updated successfully",
        "updated_with_name": "{entity} {name} updated successfully",
        
        # Deletion messages
        "deleted_success": "{entity} deleted successfully",
        "deleted_with_name": "{entity} {name} deleted successfully",
        
        # Role/Permission messages
        "role_updated": "{entity} role updated from {old_role} to {new_role}",
        "permissions_denied": "You do not have permission to manage {entity_plural}",
        
        # Leave/Attendance messages
        "leave_approved": "Leave for {entity} {name} approved",
        "leave_rejected": "Leave for {entity} {name} rejected",
        "attendance_recorded": "Attendance for {entity} recorded",
        
        # Notification messages
        "welcome_message": "Welcome to the system, {entity}!",
        "profile_updated": "Your {entity} profile has been updated",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # EMAIL & NOTIFICATION TEMPLATES
    # ─────────────────────────────────────────────────────────────────────
    NOTIFICATION_TEMPLATES = {
        "subject_welcome": "Welcome to {company_name} - {entity} Portal",
        "subject_leave_approved": "Leave Approved - {entity}",
        "subject_timesheet_submitted": "Timesheet Submitted for Approval",
        "subject_new_task": "New Task Assigned",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # AUDIT & EVENT LOG LABELS
    # ─────────────────────────────────────────────────────────────────────
    AUDIT_EVENTS = {
        "entity_created": "{entity} created",
        "entity_updated": "{entity} updated",
        "entity_deleted": "{entity} deleted",
        "entity_role_changed": "{entity} role changed",
        "entity_leave_requested": "{entity} requested leave",
        "entity_timesheet_submitted": "{entity} submitted timesheet",
    }
    
    # ─────────────────────────────────────────────────────────────────────
    # DEPRECATED: Legacy field names for backward compatibility
    # ─────────────────────────────────────────────────────────────────────
    LEGACY_MAPPINGS = {
        # Maps old field names to new ones for migration
        "employee_name": "team_member_id",
        "employee_id": "team_member_id",
        "created_employee": "created_team_member",
    }


def get_label(key: str, default: Optional[str] = None) -> str:
    """
    Get a terminology label by key.
    
    Args:
        key: Label key (e.g., "entity", "entity_plural")
        default: Fallback value if key not found
    
    Returns:
        The label string
    
    Example:
        >>> get_label("entity")
        'Team Member'
        >>> get_label("entity_plural")
        'Team Members'
    """
    return TerminologyConfig.ENTITY_LABELS.get(key, default or key)


def get_message(key: str, **kwargs) -> str:
    """
    Get and format a message template with terminology substitution.
    
    Args:
        key: Message key
        **kwargs: Variables for template substitution
    
    Returns:
        Formatted message with terminology
    
    Example:
        >>> get_message("not_found")
        'Team Member not found'
        >>> get_message("created_with_name", name="John")
        'Team Member John created successfully'
    """
    template = TerminologyConfig.MESSAGES.get(key, key)
    
    # Auto-inject entity labels
    kwargs.setdefault("entity", get_label("entity"))
    kwargs.setdefault("entity_plural", get_label("entity_plural"))
    kwargs.setdefault("entity_lowercase", get_label("entity_lowercase"))
    
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # Return template as-is if substitution fails
        return template


def get_db_field(key: str, default: Optional[str] = None) -> str:
    """
    Get a database field mapping.
    
    Args:
        key: Database field key
        default: Fallback value
    
    Returns:
        The database field name
    """
    return TerminologyConfig.DATABASE_MAPPING.get(key, default or key)


def get_api_field(key: str, default: Optional[str] = None) -> str:
    """
    Get an API response field mapping.
    
    Args:
        key: API field key
        default: Fallback value
    
    Returns:
        The API field name
    """
    return TerminologyConfig.API_RESPONSE_FIELDS.get(key, default or key)


def get_endpoint(key: str, default: Optional[str] = None) -> str:
    """
    Get an API endpoint path.
    
    Args:
        key: Endpoint key
        default: Fallback value
    
    Returns:
        The endpoint path
    """
    return TerminologyConfig.API_ENDPOINTS.get(key, default or key)


def get_audit_event(event_type: str, **kwargs) -> str:
    """
    Get formatted audit event label.
    
    Args:
        event_type: Event type key
        **kwargs: Substitution variables
    
    Returns:
        Formatted audit event message
    """
    template = TerminologyConfig.AUDIT_EVENTS.get(event_type, event_type)
    kwargs.setdefault("entity", get_label("entity"))
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


# Export convenience object
TERMINOLOGY = TerminologyConfig()


# ═════════════════════════════════════════════════════════════════════════
# UTILITY CONSTANTS FOR COMMON USE CASES
# ═════════════════════════════════════════════════════════════════════════

# Common entity labels (for direct access)
ENTITY = get_label("entity")  # "Team Member"
ENTITY_PLURAL = get_label("entity_plural")  # "Team Members"
ENTITY_LOWERCASE = get_label("entity_lowercase")  # "team member"
ENTITY_SNAKE = get_label("entity_snake_case")  # "team_member"

# Common database fields
DB_FIELD_EMPLOYEE_NAME = get_db_field("field_employee_name")  # "employee_name"
DB_TABLE_EMPLOYEE = get_db_field("table_employee")  # "employee"
DB_TABLE_USERS = get_db_field("table_users")  # "users"

# Common API fields
API_FIELD_EMPLOYEE_NAME = get_api_field("employee_name")  # "teamMemberName"

# Common endpoints
ENDPOINT_LIST_TEAM_MEMBERS = get_endpoint("list_team_members")
ENDPOINT_GET_TEAM_MEMBER = get_endpoint("get_team_member")
