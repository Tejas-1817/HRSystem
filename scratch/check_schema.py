
import sys
import os
sys.path.append(os.getcwd())
from app.models.database import execute_query

def check_timesheets_schema():
    try:
        columns = execute_query("DESCRIBE timesheets")
        print("Columns in 'timesheets' table:")
        for col in columns:
            print(f"  - {col['Field']} ({col['Type']})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_timesheets_schema()
