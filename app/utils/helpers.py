import re
from datetime import datetime

def format_role_name(name, role):
    """
    Cleans any existing role prefix and applies the correct one:
    HR -> H_, Manager -> M_, Employee -> T_
    Note: For production, use generate_unique_username which checks DB.
    """
    if not name:
        return name
    
    # Remove existing role prefixes if present (handle H_, M_, T_)
    name = re.sub(r'^[HMT]_', '', name)
    
    prefix_map = {
        'admin': 'A_',
        'hr': 'H_',
        'manager': 'M_',
        'employee': 'T_'
    }
    
    prefix = prefix_map.get(role.lower(), 'T_')
    return f"{prefix}{name}"


def generate_unique_username(name, role, cursor):
    """
    Generates a unique prefixed username.
    Example: T_Omkar, T_Omkar_1, etc.
    """
    clean_name = re.sub(r'^[HMT]_', '', name)
    
    prefix_map = {
        'admin': 'A_',
        'hr': 'H_',
        'manager': 'M_',
        'employee': 'T_'
    }
    prefix = prefix_map.get(role.lower(), 'T_')
    base_username = f"{prefix}{clean_name}"
    
    # Check uniqueness in users table
    cursor.execute("SELECT employee_name FROM users WHERE employee_name = %s", (base_username,))
    if not cursor.fetchone():
        return base_username
    
    # Not unique, append suffix
    i = 1
    while True:
        candidate = f"{base_username}_{i}"
        cursor.execute("SELECT employee_name FROM users WHERE employee_name = %s", (candidate,))
        if not cursor.fetchone():
            return candidate
        i += 1


def cascade_rename_employee(old_name, new_name, cursor):
    """
    Updates the employee name across all related tables to maintain consistency.
    """
    tables = [
        ("attendance", "employee_name"),
        ("leaves", "employee_name"),
        ("leave_balance", "employee_name"),
        ("timesheets", "employee_name"),
        ("timesheets", "manager_name"),
        ("project_assignments", "employee_name"),
        ("project_assignments", "assigned_by"),
        ("notifications", "employee_name"),
        ("projects", "manager_name"),
        ("payslips", "employee_name"),
        ("employee_documents", "employee_name"),
        ("employee_documents", "verified_by"),
        ("policies", "updated_by"),
        ("employee", "name"),
        ("users", "employee_name")
    ]
    
    for table, col in tables:
        # Check if table exists first to avoid errors (simplified)
        query = f"UPDATE {table} SET {col} = %s WHERE {col} = %s"
        cursor.execute(query, (new_name, old_name))


def generate_project_id(cursor):
    """
    Generates a unique project ID in the format PROJ-YYYY-XXX.
    Example: PROJ-2026-001
    """
    year = datetime.now().year
    cursor.execute("SELECT project_id FROM projects WHERE project_id LIKE %s ORDER BY id DESC LIMIT 1", (f"PROJ-{year}-%",))
    last_id = cursor.fetchone()

    # Handle dictionary cursor or tuple cursor
    last_val = None
    if last_id:
        if isinstance(last_id, dict):
            last_val = last_id.get('project_id')
        else:
            last_val = last_id[0]

    if last_val:
        last_num = int(last_val.split('-')[-1])
        new_num = str(last_num + 1).zfill(3)
    else:
        new_num = "001"

    return f"PROJ-{year}-{new_num}"
    
def get_working_days_count(start_date, end_date):
    """
    Calculates the number of working days (Mon-Fri) between two dates (inclusive).
    Accepts both date objects and strings in YYYY-MM-DD format.
    """
    from datetime import date, timedelta
    
    sd = start_date if isinstance(start_date, date) else datetime.strptime(str(start_date), "%Y-%m-%d").date()
    ed = end_date if isinstance(end_date, date) else datetime.strptime(str(end_date), "%Y-%m-%d").date()
    
    count = 0
    curr = sd
    while curr <= ed:
        if curr.weekday() < 5: # Monday is 0, Sunday is 6
            count += 1
        curr += timedelta(days=1)
    return count

def log_audit_event(user_id, event_type, description, commit=True):
    """
    Centralized logging for security-sensitive events.
    Records the event in the audit_logs table.
    """
    from app.models.database import execute_query
    try:
        execute_query(
            "INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)",
            (user_id, event_type, description),
            commit=commit
        )
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to log audit event: {e}")
        return False
