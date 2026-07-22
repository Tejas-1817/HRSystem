import sys
import os
from werkzeug.security import generate_password_hash

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.models.database import Transaction

def reset_superadmin(new_password):
    try:
        with Transaction() as cursor:
            # 1. Fetch existing superadmins
            cursor.execute("SELECT id, username FROM users WHERE role = 'superadmin'")
            superadmins = cursor.fetchall()
            
            if not superadmins:
                print("❌ No superadmin found in the system.")
                return

            hashed_password = generate_password_hash(new_password)
            
            print("Found the following superadmin accounts:")
            for admin in superadmins:
                # fetchall() returns dictionary if cursor(dictionary=True), otherwise tuple.
                # In HRSystem, get_connection usually sets dictionary=True.
                admin_id = admin['id'] if isinstance(admin, dict) else admin[0]
                username = admin['username'] if isinstance(admin, dict) else admin[1]
                
                print(f" - {username}")
                # 2. Update their password
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, admin_id))
                
            print(f"\n✅ Password successfully updated to '{new_password}' for all superadmins!")
            
    except Exception as e:
        print(f"❌ Error resetting Super Admin: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reset Super Admin Password")
    parser.add_argument("--password", required=True, help="New password for superadmins")
    args = parser.parse_args()
    
    reset_superadmin(args.password)
