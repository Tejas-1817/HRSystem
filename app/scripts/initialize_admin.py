import sys
import os
import mysql.connector
from werkzeug.security import generate_password_hash

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import Config
from app.models.database import get_connection, Transaction
from app.services.employee_service import create_employee_record

def initialize_super_admin(username, password, name):
    """
    Creates the first Super Admin account.
    """
    try:
        with Transaction() as cursor:
            # 1. Check if admin already exists
            cursor.execute("SELECT id FROM users WHERE role = 'admin'")
            if cursor.fetchone():
                print("⚠️  A Super Admin already exists in the system.")
                return False

            data = {
                "name": name,
                "email": username,
                "phone": "0000000000",
                "salary": 0
            }
            
            # 2. Create employee record (A_ John)
            employee_name, original_name = create_employee_record(data, "admin", cursor, with_user=False)
            
            # 3. Create user credentials with 'admin' role
            hashed_password = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (username, original_name, password, role, employee_name, password_change_required)
                VALUES (%s, %s, %s, 'admin', %s, FALSE)
            """, (username, original_name, hashed_password, employee_name))
            
            print(f"✅ Super Admin '{username}' created successfully as '{employee_name}'.")
            return True

    except Exception as e:
        print(f"❌ Error creating Super Admin: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize Super Admin")
    parser.add_argument("--username", required=True, help="Admin username (email)")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", required=True, help="Admin full name")
    
    args = parser.parse_args()
    initialize_super_admin(args.username, args.password, args.name)
