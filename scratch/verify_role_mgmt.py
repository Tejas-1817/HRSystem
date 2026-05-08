#!/usr/bin/env python3
"""
Verification test for Secure Role Management.
"""
import requests
import json
import sys

BASE = "http://localhost:5001"
ADMIN = {"username": "admin@hrms.com", "password": "Admin@123"}
HR = {"username": "riya@gmail.com", "password": "Riya@123"}
EMP_EMAIL = "kartik@gmail.com"

PASS = "\033[92m✅  PASS\033[0m"
FAIL = "\033[91m❌  FAIL\033[0m"

def login(creds):
    r = requests.post(f"{BASE}/auth/login", json=creds)
    data = r.json()
    if not data.get("success"):
        return None
    return data.get("token")

def hdr(tok): return {"Authorization": f"Bearer {tok}"}

def run_test(label, condition, detail=""):
    icon = PASS if condition else FAIL
    print(f"  {icon}  {label}")
    if detail and not condition: print(f"         → {detail}")
    return condition

print("\n--- Starting Role Management Verification ---")

# 1. Login as Admin
admin_token = login(ADMIN)
if not admin_token:
    print(f"{FAIL} Could not login as Admin. Make sure server is running.")
    sys.exit(1)
print(f"{PASS} Admin Login")

# 2. Find a target employee
r = requests.get(f"{BASE}/auth/users", headers=hdr(admin_token))
users = r.json().get("users", [])
target = next((u for u in users if u["username"] == EMP_EMAIL), None)

if not target:
    print(f"{FAIL} Target employee {EMP_EMAIL} not found.")
    sys.exit(1)

target_id = target["id"]
old_name = target["employee_name"]
print(f"  ℹ️  Targeting User ID {target_id} ({old_name})")

# 3. Try to change role as HR (Should fail)
# Note: I need an HR token. I'll assume Riya@123 works or skip if it fails.
hr_token = login(HR)
if hr_token:
    r = requests.put(f"{BASE}/employees/{target_id}/role", json={"role": "manager"}, headers=hdr(hr_token))
    run_test("HR role change blocked (403)", r.status_code == 403, f"Status: {r.status_code}")
else:
    print("  ⚠️  Skipping HR block test (could not login as HR)")

# 4. Change role as Admin (Should succeed)
print("\n--- Performing Role Change (Employee -> Manager) ---")
r = requests.put(f"{BASE}/employees/{target_id}/role", json={"role": "manager"}, headers=hdr(admin_token))
data = r.json()
is_ok = run_test("Admin role change successful (200)", r.status_code == 200, str(data))

if is_ok:
    new_name = data.get("new_username")
    print(f"  ℹ️  New employee name: {new_name}")
    
    # 5. Verify Database Consistency (Cascade)
    r = requests.get(f"{BASE}/auth/profile", headers=hdr(admin_token)) # Just a check
    
    # Check if history is recorded
    # I'll check audit logs since I don't have a direct history API yet
    r = requests.get(f"{BASE}/auth/admin/audit-logs", headers=hdr(admin_token))
    logs = r.json().get("logs", [])
    has_audit = any("role_change" in log["event_type"] and new_name in log["description"] for log in logs)
    run_test("Audit log entry created", has_audit)

    # 6. Verify Cascade (Check notifications or leaves)
    # We'll check if a notification was created for the new name
    # Admin can't see all notifications easily without an admin API, but let's check if the user exists
    r = requests.get(f"{BASE}/auth/users", headers=hdr(admin_token))
    users = r.json().get("users", [])
    updated_user = next((u for u in users if u["id"] == target_id), None)
    run_test("User role updated in DB", updated_user and updated_user["role"] == "manager")
    run_test("User employee_name updated in DB", updated_user and updated_user["employee_name"] == new_name)

print("\n--- Verification Complete ---")
