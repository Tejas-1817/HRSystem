from app.models.database import execute_query

print("=== users table with role = 'manager' ===")
for u in execute_query("SELECT id, employee_name, username, email, role, is_active FROM users WHERE role = 'manager'"):
    print(u)

print("\n=== employee table records with role or designation ===")
for e in execute_query("""
    SELECT e.id, e.name, e.designation, e.department, u.role 
    FROM employee e 
    LEFT JOIN users u ON e.name = u.employee_name
"""):
    print(e)
