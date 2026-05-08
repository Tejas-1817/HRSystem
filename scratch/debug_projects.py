from app import create_app
from app.models.database import execute_query

def debug_project_assignments():
    app = create_app()
    with app.app_context():
        print("Checking all projects:")
        projects = execute_query("SELECT id, project_id, name FROM projects")
        for p in projects:
            print(p)
            
        print("\nChecking all assignments:")
        assignments = execute_query("SELECT * FROM project_assignments")
        for a in assignments:
            print(a)
            
        print("\nChecking assignments for Kartik (employee):")
        #kartik is T_Kartik
        kartik_projects = execute_query("""
            SELECT p.name, pa.employee_name 
            FROM projects p
            JOIN project_assignments pa ON p.id = pa.project_id
            WHERE pa.employee_name = 'T_Kartik'
        """)
        print(f"Kartik's projects: {kartik_projects}")

if __name__ == "__main__":
    debug_project_assignments()
