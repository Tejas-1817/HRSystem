import requests
import sys
import os

# Configuration
BASE_URL = "http://localhost:5001"
ADMIN_USER = {"username": "admin@hr.com", "password": "Admin@123"}
HR_USER = {"username": "saurabh@gmail.com", "password": "Saurabh@123"} # Based on previous search results

def get_token(username, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if resp.status_code == 200:
        return resp.json()["token"]
    return None

def test_admin_privileges():
    print("--- 🔍 Starting Super Admin Privilege Verification ---")
    
    admin_token = get_token(ADMIN_USER["username"], ADMIN_USER["password"])
    hr_token = get_token(HR_USER["username"], HR_USER["password"])
    
    if not admin_token:
        print("❌ Failed to login as Admin")
        return

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    hr_headers = {"Authorization": f"Bearer {hr_token}"}

    # 1. Admin accessing HR-only route
    print("\n[Admin-to-HR Bypass Check]")
    policy_resp = requests.get(f"{BASE_URL}/reports/policies", headers=admin_headers)
    if policy_resp.status_code == 200:
        print("✅ Admin successfully accessed HR-only /policies endpoint.")
    else:
        print(f"❌ Admin blocked from HR-only endpoint (Status: {policy_resp.status_code})")

    # 2. Admin accessing Admin-only route
    print("\n[Admin-to-Admin Access Check]")
    audit_resp = requests.get(f"{BASE_URL}/auth/admin/audit-logs", headers=admin_headers)
    if audit_resp.status_code == 200:
        print("✅ Admin successfully accessed Admin-only /audit-logs endpoint.")
        print(f"   Found {len(audit_resp.json().get('logs', []))} log entries.")
    else:
        print(f"❌ Admin blocked from Admin-only endpoint (Status: {audit_resp.status_code})")

    # 3. HR accessing Admin-only route (Should FAIL)
    print("\n[Non-Admin Restriction Check]")
    fail_resp = requests.get(f"{BASE_URL}/auth/admin/audit-logs", headers=hr_headers)
    if fail_resp.status_code == 403:
        print("✅ Correctly blocked HR from Admin-only endpoint.")
    else:
        print(f"❌ Security Issue: HR accessed Admin-only endpoint (Status: {fail_resp.status_code})")

    # 4. Admin resetting a password
    print("\n[Admin Functionality Check: Password Reset]")
    # Get a user id to reset (e.g. Saurabh's id)
    user_list_resp = requests.get(f"{BASE_URL}/auth/users", headers=admin_headers)
    users = user_list_resp.json().get("users", [])
    test_user = next((u for u in users if u["username"] == HR_USER["username"]), None)
    
    if test_user:
        reset_resp = requests.post(f"{BASE_URL}/auth/admin/users/{test_user['id']}/reset-password", headers=admin_headers)
        if reset_resp.status_code == 200:
            print(f"✅ Admin successfully reset password for user '{test_user['username']}'.")
        else:
            print(f"❌ Admin failed to reset password (Status: {reset_resp.status_code})")
    else:
        print("⚠️ Could not find test user for password reset check.")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    test_admin_privileges()
