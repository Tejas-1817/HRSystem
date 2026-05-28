"""
Department & Designation Service Layer
──────────────────────────────────────
CRUD operations for dynamic department and designation management.
HR/Admin users can create, update, and deactivate departments/designations
from the settings panel without code changes.

Usage:
    from app.services.department_service import (
        list_departments, create_department,
        list_designations, create_designation,
    )
"""

import logging
from app.models.database import execute_query, execute_single, Transaction
from app.utils.helpers import log_audit_event

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# DEPARTMENT OPERATIONS
# ═════════════════════════════════════════════════════════════════════════

def list_departments(active_only=True):
    """
    List all departments, optionally filtering to active-only.

    Args:
        active_only: If True, only return active departments.

    Returns:
        List of department records.
    """
    if active_only:
        return execute_query(
            "SELECT id, name, description, is_active, created_by, created_at, updated_at "
            "FROM departments WHERE is_active = TRUE ORDER BY name ASC"
        )
    return execute_query(
        "SELECT id, name, description, is_active, created_by, created_at, updated_at "
        "FROM departments ORDER BY name ASC"
    )


def get_department(department_id):
    """Fetch a single department by ID."""
    return execute_single(
        "SELECT * FROM departments WHERE id = %s",
        (department_id,)
    )


def get_department_by_name(name):
    """Fetch a department by name (case-insensitive)."""
    return execute_single(
        "SELECT * FROM departments WHERE LOWER(name) = LOWER(%s)",
        (name.strip(),)
    )


def create_department(name, description=None, created_by=None):
    """
    Create a new department.

    Args:
        name: Department name (must be unique)
        description: Optional description
        created_by: System ID of the user creating this department

    Returns:
        The created department record

    Raises:
        ValueError: If department name is empty or already exists
    """
    if not name or not name.strip():
        raise ValueError("Department name is required")

    name = name.strip()

    # Check uniqueness
    existing = get_department_by_name(name)
    if existing:
        raise ValueError(f"Department '{name}' already exists")

    dept_id = execute_query(
        "INSERT INTO departments (name, description, created_by) VALUES (%s, %s, %s)",
        (name, description, created_by),
        commit=True
    )

    logger.info(f"Department created: {name} (by {created_by})")
    return get_department(dept_id)


def update_department(department_id, data, updated_by=None):
    """
    Update a department's details.

    Args:
        department_id: Department database ID
        data: Dictionary of fields to update (name, description, is_active)
        updated_by: System ID of the user making the update

    Returns:
        Updated department record

    Raises:
        ValueError: If department not found or invalid data
    """
    existing = get_department(department_id)
    if not existing:
        raise ValueError("Department not found")

    allowed_fields = {'name', 'description', 'is_active'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        raise ValueError("No valid fields to update")

    # Check name uniqueness if name is being changed
    if 'name' in updates:
        new_name = updates['name'].strip()
        if not new_name:
            raise ValueError("Department name cannot be empty")
        conflict = execute_single(
            "SELECT id FROM departments WHERE LOWER(name) = LOWER(%s) AND id != %s",
            (new_name, department_id)
        )
        if conflict:
            raise ValueError(f"Department '{new_name}' already exists")
        updates['name'] = new_name

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [department_id]

    execute_query(
        f"UPDATE departments SET {set_clause} WHERE id = %s",
        tuple(values),
        commit=True
    )

    logger.info(f"Department updated: ID {department_id} (by {updated_by})")
    return get_department(department_id)


def deactivate_department(department_id, deactivated_by=None):
    """
    Soft-deactivate a department (sets is_active = FALSE).

    Args:
        department_id: Department database ID
        deactivated_by: System ID of the admin

    Returns:
        Success status dict
    """
    existing = get_department(department_id)
    if not existing:
        raise ValueError("Department not found")

    execute_query(
        "UPDATE departments SET is_active = FALSE WHERE id = %s",
        (department_id,),
        commit=True
    )

    logger.info(f"Department deactivated: {existing['name']} (by {deactivated_by})")
    return {"success": True, "message": f"Department '{existing['name']}' deactivated"}


def is_valid_department_dynamic(name):
    """
    Check if a department name exists in the dynamic departments table.
    Falls back to static list if the table is empty or inaccessible.
    """
    if not name:
        return True
    try:
        result = execute_single(
            "SELECT id FROM departments WHERE LOWER(name) = LOWER(%s) AND is_active = TRUE",
            (name.strip(),)
        )
        return result is not None
    except Exception:
        # Fallback to static validation
        from app.config.constants import is_valid_department
        return is_valid_department(name)


# ═════════════════════════════════════════════════════════════════════════
# DESIGNATION OPERATIONS
# ═════════════════════════════════════════════════════════════════════════

def list_designations(active_only=True, department_id=None):
    """
    List all designations with optional filters.

    Args:
        active_only: If True, only return active designations
        department_id: Filter by department (optional)

    Returns:
        List of designation records
    """
    query = (
        "SELECT d.id, d.name, d.department_id, d.description, d.is_active, "
        "d.created_by, d.created_at, d.updated_at, "
        "dept.name AS department_name "
        "FROM designations d "
        "LEFT JOIN departments dept ON d.department_id = dept.id "
        "WHERE 1=1"
    )
    params = []

    if active_only:
        query += " AND d.is_active = TRUE"

    if department_id:
        query += " AND d.department_id = %s"
        params.append(department_id)

    query += " ORDER BY d.name ASC"

    return execute_query(query, params if params else None)


def get_designation(designation_id):
    """Fetch a single designation by ID."""
    return execute_single(
        "SELECT d.*, dept.name AS department_name "
        "FROM designations d "
        "LEFT JOIN departments dept ON d.department_id = dept.id "
        "WHERE d.id = %s",
        (designation_id,)
    )


def get_designation_by_name(name):
    """Fetch a designation by name (case-insensitive)."""
    return execute_single(
        "SELECT * FROM designations WHERE LOWER(name) = LOWER(%s)",
        (name.strip(),)
    )


def create_designation(name, department_id=None, description=None, created_by=None):
    """
    Create a new designation.

    Args:
        name: Designation title (must be unique)
        department_id: Optional FK to departments table
        description: Optional description
        created_by: System ID of the creator

    Returns:
        Created designation record

    Raises:
        ValueError: If name empty/duplicate or department_id invalid
    """
    if not name or not name.strip():
        raise ValueError("Designation name is required")

    name = name.strip()

    # Check uniqueness
    existing = get_designation_by_name(name)
    if existing:
        raise ValueError(f"Designation '{name}' already exists")

    # Validate department_id if provided
    if department_id:
        dept = get_department(department_id)
        if not dept:
            raise ValueError(f"Department with ID {department_id} not found")

    desig_id = execute_query(
        "INSERT INTO designations (name, department_id, description, created_by) "
        "VALUES (%s, %s, %s, %s)",
        (name, department_id, description, created_by),
        commit=True
    )

    logger.info(f"Designation created: {name} (by {created_by})")
    return get_designation(desig_id)


def update_designation(designation_id, data, updated_by=None):
    """
    Update a designation's details.

    Args:
        designation_id: Designation database ID
        data: Dictionary of fields to update
        updated_by: System ID of the user making the update

    Returns:
        Updated designation record
    """
    existing = get_designation(designation_id)
    if not existing:
        raise ValueError("Designation not found")

    allowed_fields = {'name', 'department_id', 'description', 'is_active'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        raise ValueError("No valid fields to update")

    # Check name uniqueness
    if 'name' in updates:
        new_name = updates['name'].strip()
        if not new_name:
            raise ValueError("Designation name cannot be empty")
        conflict = execute_single(
            "SELECT id FROM designations WHERE LOWER(name) = LOWER(%s) AND id != %s",
            (new_name, designation_id)
        )
        if conflict:
            raise ValueError(f"Designation '{new_name}' already exists")
        updates['name'] = new_name

    # Validate department_id if provided
    if 'department_id' in updates and updates['department_id']:
        dept = get_department(updates['department_id'])
        if not dept:
            raise ValueError(f"Department with ID {updates['department_id']} not found")

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [designation_id]

    execute_query(
        f"UPDATE designations SET {set_clause} WHERE id = %s",
        tuple(values),
        commit=True
    )

    logger.info(f"Designation updated: ID {designation_id} (by {updated_by})")
    return get_designation(designation_id)


def deactivate_designation(designation_id, deactivated_by=None):
    """
    Soft-deactivate a designation (sets is_active = FALSE).
    """
    existing = get_designation(designation_id)
    if not existing:
        raise ValueError("Designation not found")

    execute_query(
        "UPDATE designations SET is_active = FALSE WHERE id = %s",
        (designation_id,),
        commit=True
    )

    logger.info(f"Designation deactivated: {existing['name']} (by {deactivated_by})")
    return {"success": True, "message": f"Designation '{existing['name']}' deactivated"}


def is_valid_designation_dynamic(name):
    """
    Check if a designation name exists in the dynamic designations table.
    Falls back to static list if the table is empty.
    """
    if not name:
        return True
    try:
        result = execute_single(
            "SELECT id FROM designations WHERE LOWER(name) = LOWER(%s) AND is_active = TRUE",
            (name.strip(),)
        )
        return result is not None
    except Exception:
        from app.config.constants import is_valid_designation
        return is_valid_designation(name)
