import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = f"http://localhost:{os.getenv('PORT', 5001)}"

def test_role_visibility():
    print("--- 🔍 Starting Role Visibility Verification ---")
    
    # 1. Login as HR (Riya)
    login_data = {"username": "riya@gmail.com", "password": "Riya@123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.json()}")
        return
    
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Check /employees/
    print("\n[Step 1] Checking /employees/ (All employees)...")
    emp_resp = requests.get(f"{BASE_URL}/employees/", headers=headers)
    if emp_resp.status_code == 200:
        employees = emp_resp.json()["employees"]
        if employees:
            missing_roles = [e["name"] for e in employees if "role" not in e or e["role"] is None]
            if not missing_roles:
                print(f"✅ All {len(employees)} employees have roles.")
                print(f"Example roles: {[e['role'] for e in employees[:3]]}")
            else:
                print(f"❌ {len(missing_roles)} employees missing roles: {missing_roles}")
        else:
            print("⚠️ No employees found.")
    else:
        print(f"❌ Employees list request failed: {emp_resp.json()}")

    # 3. Check /employees/<id>
    print("\n[Step 2] Checking /employees/<id> (Single employee)...")
    # Fetch Kartik (ID 1 usually)
    single_emp_resp = requests.get(f"{BASE_URL}/employees/1", headers=headers)
    if single_emp_resp.status_code == 200:
        emp = single_emp_resp.json()["employee"]
        if "role" in emp and emp["role"] is not None:
            print(f"✅ Single employee detailed view has role: {emp['role']}")
        else:
            print(f"❌ Single employee view missing role.")
    else:
        print(f"❌ Single employee request failed: {single_emp_resp.json()}")

    print("\nVerification complete.")

if __name__ == "__main__":
    test_role_visibility()
