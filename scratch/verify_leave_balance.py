#!/usr/bin/env python3
"""
Verification test for Leave Balance Display.
"""
import requests
import json
import sys

BASE = "http://localhost:5001"
ADMIN = {"username": "admin@hrms.com", "password": "Admin@123"}
EMP_EMAIL = "raj@gmail.com"

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

print("\n--- Starting Leave Balance Verification ---")

# 1. Login as Admin
admin_token = login(ADMIN)
if not admin_token:
    print(f"{FAIL} Could not login as Admin.")
    sys.exit(1)
print(f"{PASS} Admin Login")

# 2. Check Dashboard (Profile) for Leave Balance Breakdown
print("\n--- Checking Dashboard /profile Endpoint ---")
r = requests.get(f"{BASE}/auth/profile", headers=hdr(admin_token))
data = r.json()

if run_test("Profile returns 200", r.status_code == 200, str(data)):
    user = data.get("user", {})
    run_test("Summary total_leaves present", "total_leaves" in user, f"Keys: {list(user.keys())}")
    run_test("Summary total_leaves is float (not 0 if data exists)", user.get("total_leaves", 0) > 0)
    
    # Pro Add-On Check
    lb_breakdown = data.get("leave_balance", [])
    run_test("Detailed leave_balance breakdown present", len(lb_breakdown) > 0)
    if lb_breakdown:
        first = lb_breakdown[0]
        run_test("Breakdown has float values", isinstance(first.get("used_leaves"), (int, float)))
        print(f"  ℹ️  Sample breakdown: {first['leave_type']}: {first['remaining_leaves']} remaining")

# 3. Check All Balances (HR/Manager access)
print("\n--- Checking Global /leaves/balance/all Endpoint ---")
r = requests.get(f"{BASE}/leaves/balance/all", headers=hdr(admin_token))
data = r.json()
run_test("Global balances returns 200", r.status_code == 200)
run_test("Global balances has data", len(data.get("balances", {})) > 0)

print("\n--- Verification Complete ---")
