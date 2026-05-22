import requests
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

BASE_URL = f"http://localhost:{os.getenv('PORT', 5001)}"

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "starterdata"),
        user=os.getenv("DB_USER", "tejas"),
        password=os.getenv("DB_PASS", "password123")
    )

def verify_export():
    # 1. Test Employee Export (raj@gmail.com)
    print("\n--- 1. Testing Employee Export (T_Raj) ---")
    login_data_emp = {"username": "raj@gmail.com", "password": "Raj@123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data_emp)
    if resp.status_code != 200:
        print(f"❌ Employee Login failed: {resp.json()}")
        return
    token_emp = resp.json().get("token")
    headers_emp = {"Authorization": f"Bearer {token_emp}"}

    # Retrieve current user details to get user_id for verification
    profile_resp = requests.get(f"{BASE_URL}/auth/profile", headers=headers_emp)
    emp_user_id = profile_resp.json().get("data", {}).get("id")
    print(f"Logged in as T_Raj (user_id={emp_user_id})")

    export_resp = requests.get(f"{BASE_URL}/timesheets/export", headers=headers_emp)
    if export_resp.status_code == 200:
        print("✅ Employee Export Success!")
        print(f"   Content-Type: {export_resp.headers.get('Content-Type')}")
        print(f"   Filename: {export_resp.headers.get('Content-Disposition')}")
        filepath = os.path.join(os.path.dirname(__file__), "test_export_result.xlsx")
        with open(filepath, "wb") as f:
            f.write(export_resp.content)
        print(f"   Saved to {filepath}")
    else:
        print(f"❌ Employee Export failed: {export_resp.status_code} - {export_resp.text}")
        return

    # 2. Test Manager Export (tejas@gmail.com)
    print("\n--- 2. Testing Manager Export (M_Tejas) ---")
    login_data_mgr = {"username": "tejas@gmail.com", "password": "Tejas@123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data_mgr)
    if resp.status_code != 200:
        # Try fallback password
        login_data_mgr = {"username": "tejas@gmail.com", "password": "password123"}
        resp = requests.post(f"{BASE_URL}/auth/login", json=login_data_mgr)
        if resp.status_code != 200:
            print(f"❌ Manager Login failed: {resp.json()}")
            return
            
    token_mgr = resp.json().get("token")
    headers_mgr = {"Authorization": f"Bearer {token_mgr}"}
    
    profile_resp = requests.get(f"{BASE_URL}/auth/profile", headers=headers_mgr)
    mgr_user_id = profile_resp.json().get("data", {}).get("id")
    print(f"Logged in as Manager M_Tejas (user_id={mgr_user_id})")

    # Manager exports employee T_Raj
    export_resp = requests.get(f"{BASE_URL}/timesheets/export?employee_name=T_Raj", headers=headers_mgr)
    if export_resp.status_code == 200:
        print("✅ Manager Export of T_Raj Success!")
    else:
        print(f"❌ Manager Export of T_Raj failed: {export_resp.status_code} - {export_resp.text}")

    # 3. Check Audit Logs in Database
    print("\n--- 3. Verifying Audit Logs in Database ---")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM audit_logs 
            WHERE event_type = 'timesheet_export' 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        logs = cursor.fetchall()
        if logs:
            print("✅ Audit log entries found:")
            for log in logs:
                print(f"   [ID: {log['id']}] User ID: {log['user_id']} | Event: {log['event_type']} | Desc: {log['description']} | Created: {log['created_at']}")
        else:
            print("❌ No 'timesheet_export' audit log entries found in database.")
    except Exception as e:
        print(f"Error reading audit logs: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    verify_export()
