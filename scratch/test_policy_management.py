import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = f"http://localhost:{os.getenv('PORT', 5001)}"

def test_policy_management():
    print("--- 🔍 Starting Policy Management Verification ---")
    
    # 1. Login as HR (Saurabh)
    login_data = {"username": "saurabh@gmail.com", "password": "Saurabh@123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if resp.status_code != 200:
        print(f"❌ HR Login failed: {resp.json()}")
        return
    token_hr = resp.json()["token"]
    headers_hr = {"Authorization": f"Bearer {token_hr}"}
    
    # 2. Login as Employee (Raj)
    login_data_emp = {"username": "raj@gmail.com", "password": "Raj@123"}
    resp_emp = requests.post(f"{BASE_URL}/auth/login", json=login_data_emp)
    if resp_emp.status_code != 200:
        print(f"❌ Employee Login failed: {resp_emp.json()}")
        return
    token_emp = resp_emp.json()["token"]
    headers_emp = {"Authorization": f"Bearer {token_emp}"}
    
    # [Step 1] HR Creates a Policy
    print("\n[Step 1] HR creating a policy...")
    new_policy = {
        "category": "IT",
        "title": "Device Security",
        "content": "All laptops must be encrypted."
    }
    create_resp = requests.post(f"{BASE_URL}/reports/policies", json=new_policy, headers=headers_hr)
    if create_resp.status_code == 201:
        print("✅ Policy created successfully by HR.")
    else:
        print(f"❌ Failed to create policy: {create_resp.json()}")
        return

    # [Step 2] Fetch policies to get the ID
    get_resp = requests.get(f"{BASE_URL}/reports/policies", headers=headers_hr)
    policies = get_resp.json()["policies"]
    test_policy = next((p for p in policies if p["title"] == "Device Security"), None)
    if not test_policy:
        print("❌ Could not find the newly created policy.")
        return
    policy_id = test_policy["id"]
    print(f"Found policy ID: {policy_id}")

    # [Step 3] HR Updates the Policy
    print("\n[Step 2] HR updating a policy...")
    update_data = {"content": "All laptops and mobile devices must be encrypted."}
    update_resp = requests.put(f"{BASE_URL}/reports/policies/{policy_id}", json=update_data, headers=headers_hr)
    if update_resp.status_code == 200:
        print("✅ Policy updated successfully by HR.")
    else:
        print(f"❌ Failed to update policy: {update_resp.json()}")

    # [Step 4] Employee tries to Update (Should Fail)
    print("\n[Step 3] Employee attempting to update policy (Expected Fail)...")
    fail_update = requests.put(f"{BASE_URL}/reports/policies/{policy_id}", json=update_data, headers=headers_emp)
    if fail_update.status_code == 403:
        print("✅ Access denied for Employee (Correct behavior).")
    else:
        print(f"❌ Security Flaw: Employee was able to access update API (Code: {fail_update.status_code})")

    # [Step 5] HR Deactivates/Deletes the Policy
    print("\n[Step 4] HR deactivating a policy...")
    del_resp = requests.delete(f"{BASE_URL}/reports/policies/{policy_id}", headers=headers_hr)
    if del_resp.status_code == 200:
        print("✅ Policy deactivated successfully by HR.")
    else:
        print(f"❌ Failed to deactivate policy: {del_resp.json()}")

    # Final Check
    final_get = requests.get(f"{BASE_URL}/reports/policies", headers=headers_hr)
    final_policies = final_get.json()["policies"]
    if not any(p["id"] == policy_id for p in final_policies):
        print("✅ Policy is no longer in active list.")
    else:
        print("❌ Policy still appears in active list.")

    print("\nVerification complete.")

if __name__ == "__main__":
    test_policy_management()
