import logging
from app.models.database import execute_query, execute_single

logger = logging.getLogger(__name__)

def sync_employee_status(employee_name, cursor=None):
    """
    Automatically determine and update employee status based on active assignments.
    - over_allocated: Total billable allocation > 100%
    - working: Assigned to at least one project (0 < Sum <= 100%)
    - bench: Not assigned to any project.
    """
    try:
        # Calculate total billable allocation sum
        query = "SELECT SUM(billable_percentage) as total_utilization FROM project_assignments WHERE employee_name = %s"
        util_data = execute_single(query, (employee_name,), cursor=cursor)
        total_util = util_data["total_utilization"] or 0

        if total_util > 100:
            new_status = 'over_allocated'
        elif total_util > 0:
            new_status = 'working'
        else:
            new_status = 'bench'
        
        # Update employee status
        execute_query(
            "UPDATE employee SET status = %s WHERE name = %s",
            (new_status, employee_name),
            commit=(cursor is None),
            cursor=cursor
        )
        
        logger.info(f"Updated status for {employee_name} to {new_status} (Utilization: {total_util}%)")
        return {
            "status": new_status,
            "total_utilization": int(total_util)
        }
    except Exception as e:
        logger.error(f"Failed to sync employee status for {employee_name}: {e}")
        return None

def get_employee_utilization(employee_name):
    """Fetch current total utilization for a specific employee."""
    query = "SELECT SUM(billable_percentage) as total FROM project_assignments WHERE employee_name = %s"
    row = execute_single(query, (employee_name,))
    return int(row["total"] or 0)

def get_utilization_report():
    """Returns a summary of working vs bench employees."""
    total_employees = execute_single("SELECT COUNT(*) as count FROM employee")["count"]
    working_count = execute_single("SELECT COUNT(*) as count FROM employee WHERE status = 'working'")["count"]
    bench_count = total_employees - working_count
    
    return {
        "total": total_employees,
        "working": working_count,
        "bench": bench_count,
        "working_percentage": round((working_count / total_employees * 100), 2) if total_employees > 0 else 0
    }

def get_over_allocation_report():
    """Returns a list of employees who are currently over-allocated."""
    query = """
        SELECT name, email, status, allow_over_allocation 
        FROM employee 
        WHERE status = 'over_allocated'
    """
    rows = execute_query(query)
    for row in rows:
        row["current_utilization"] = get_employee_utilization(row["name"])
    
    return rows

def get_billing_ratio_report():
    """Returns billable vs non-billable ratio among assigned employees."""
    query = """
        SELECT 
            SUM(CASE WHEN is_billable = TRUE THEN 1 ELSE 0 END) as billable,
            SUM(CASE WHEN is_billable = FALSE THEN 1 ELSE 0 END) as non_billable
        FROM project_assignments
    """
    row = execute_single(query)
    billable = row["billable"] or 0
    non_billable = row["non_billable"] or 0
    total = billable + non_billable
    
    return {
        "billable": billable,
        "non_billable": non_billable,
        "total_assignments": total,
        "billable_ratio": round((billable / total * 100), 2) if total > 0 else 0
    }

def get_project_revenue_estimation():
    """
    Estimates revenue based on project type:
    - Fixed Cost: Flat project budget (placeholder logic as budget isn't in DB yet, using count)
    - T&M: Hours from timesheets * rate (placeholder rate)
    """
    # This is a conceptual implementation as full pricing data isn't in the provided schema.
    # We will return counts of projects by type and aggregated hours for T&M.
    
    tm_hours = execute_single("""
        SELECT SUM(t.hours) as total_hours
        FROM timesheets t
        JOIN projects p ON t.project = p.name
        WHERE p.project_type = 'tm' AND t.status = 'approved'
    """)["total_hours"] or 0
    
    fixed_count = execute_single("SELECT COUNT(*) as count FROM projects WHERE project_type = 'fixed'")["count"]
    tm_count = execute_single("SELECT COUNT(*) as count FROM projects WHERE project_type = 'tm'")["count"]
    
    return {
        "tm_projects": {
            "count": tm_count,
            "total_approved_hours": tm_hours,
            "estimated_revenue": tm_hours * 50  # Placeholder rate of $50/hr
        },
        "fixed_projects": {
            "count": fixed_count,
            "estimated_revenue_base": fixed_count * 5000 # Placeholder average project value
        }
    }
