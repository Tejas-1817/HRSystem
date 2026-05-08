"""
End-to-end test for the authentication fix.
Tests both employee creation paths and verifies login works.
"""
import requests
import sys
import random
import string

BASE_URL = "http://localhost:5001"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase, k=5))

def test_auth_fix():
    print("=" * 60)
    print("AUTH FIX VERIFICATION TEST")
    print("=" * 60)
    
    # --- Step 1: Login as HR ---
    print("\n[1] Logging in as HR...")
    # Try common HR credentials
    hr_creds = None
    for username in ["saurabh@gmail.com", "kartik@gmail.com", "admin", "hr@company.com"]:
        r = requests.post(f"{BASE_URL}/auth/login", json={
            "username": username,
            "password": "Welcome@123"
        })
        if r.status_code == 200 and r.json().get("success"):
            hr_creds = r.json()
            print(f"   ✅ Logged in as HR: {username} (role: {hr_creds['user']['role']})")
            break
    
    if not hr_creds:
        # Try with a different password
        for username in ["kartik@gmail.com", "admin"]:
            r = requests.post(f"{BASE_URL}/auth/login", json={
                "username": username,
                "password": "Admin@123"
            })
            if r.status_code == 200 and r.json().get("success"):
                hr_creds = r.json()
                print(f"   ✅ Logged in as HR: {username} (role: {hr_creds['user']['role']})")
                break
    
    if not hr_creds:
        print("   ❌ Could not find HR credentials. Listing all users...")
        # Try to get users list some other way
        print("   Please provide HR login credentials.")
        sys.exit(1)
    
    hr_token = hr_creds["token"]
    headers = {"Authorization": f"Bearer {hr_token}"}
    
    suffix = random_suffix()
    
    # --- Step 2: Test /auth/register path (the one that was broken) ---
    print(f"\n[2] Testing POST /auth/register (was BROKEN)...")
    new_user_email = f"testuser_{suffix}@test.com"
    new_user_password = "TestPass@123"
    
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "username": new_user_email,
        "password": new_user_password,
        "employee_name": f"Test User {suffix.upper()}",
        "email": new_user_email,
        "role": "employee"
    }, headers=headers)
    
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.json()}")
    
    if r.status_code == 201:
        print("   ✅ Employee created via /auth/register")
    else:
        print("   ❌ FAILED to create employee via /auth/register!")
        return False
    
    # --- Step 3: Login as the newly created employee ---
    print(f"\n[3] Logging in as new employee ({new_user_email})...")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": new_user_email,
        "password": new_user_password
    })
    
    print(f"   Status: {r.status_code}")
    resp = r.json()
    print(f"   Response: {resp}")
    
    if r.status_code == 200 and resp.get("success"):
        print("   ✅ NEW EMPLOYEE CAN LOG IN! Bug is FIXED!")
        user = resp.get("user", {})
        print(f"   → Username: {user.get('username')}")
        print(f"   → Role: {user.get('role')}")
        print(f"   → Employee Name: {user.get('employee_name')}")
        print(f"   → Password Change Required: {user.get('password_change_required')}")
        
        if user.get("password_change_required"):
            print("   ✅ First-login password change enforcement is active")
        else:
            print("   ⚠️  password_change_required should be True for new employees")
    else:
        print("   ❌ NEW EMPLOYEE STILL CANNOT LOG IN!")
        return False
    
    # --- Step 4: Test /employees/ path (should still work) ---
    suffix2 = random_suffix()
    print(f"\n[4] Testing POST /employees/ (should still work)...")
    r = requests.post(f"{BASE_URL}/employees/", json={
        "employee_name": f"Test Employee {suffix2.upper()}",
        "email": f"emp_{suffix2}@test.com",
        "role": "employee"
    }, headers=headers)
    
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.json()}")
    
    if r.status_code == 201:
        print("   ✅ Employee created via /employees/")
        
        # Login with default password
        print(f"\n[5] Logging in as employee created via /employees/ (default password)...")
        r = requests.post(f"{BASE_URL}/auth/login", json={
            "username": f"emp_{suffix2}@test.com",
            "password": "Welcome@123"
        })
        print(f"   Status: {r.status_code}")
        if r.status_code == 200 and r.json().get("success"):
            print("   ✅ Employee from /employees/ path can also log in!")
        else:
            print(f"   ❌ Employee from /employees/ CANNOT log in: {r.json()}")
            return False
    else:
        print("   ❌ FAILED to create employee via /employees/!")
        return False
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_auth_fix()
    sys.exit(0 if success else 1)
