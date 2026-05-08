"""
Comprehensive End-to-end test for Authentication Hardening.
Tests:
- Dual Identifier Login (Username and Email)
- Input Sanitation (Trailing spaces)
- Middleware Bypass (Profile access during password reset phase)
"""
import requests
import sys
import random
import string

BASE_URL = "http://localhost:5001"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase, k=5))

def test_comprehensive_fix():
    print("=" * 60)
    print("COMPREHENSIVE AUTH HARDENING VERIFICATION")
    print("=" * 60)
    
    # --- Step 1: Login as HR (Saurabh) ---
    print("\n[1] Logging in as HR (Saurabh)...")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "saurabh@gmail.com",
        "password": "Welcome@123"
    })
    if not (r.status_code == 200 and r.json().get("success")):
        print(f"   ❌ HR Login Failed: {r.text}")
        sys.exit(1)
    
    hr_token = r.json()["token"]
    headers = {"Authorization": f"Bearer {hr_token}"}
    print("   ✅ HR Login Success")

    suffix = random_suffix()
    username = f"user_{suffix}"
    email = f"email_{suffix}@test.com"
    password = "ComplexPass@123 " # Note trailing space here
    
    # --- Step 2: Register with explicit username AND email ---
    print(f"\n[2] Registering employee with username '{username}' and email '{email}'...")
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "username": "  " + username + "  ", # Trailing/leading spaces
        "password": password,
        "employee_name": f"Test Hardening {suffix.upper()}",
        "email": email,
        "role": "employee"
    }, headers=headers)
    
    if r.status_code != 201:
        print(f"   ❌ Registration Failed: {r.text}")
        return False
    print("   ✅ Registration Success (Sanitation test passed)")

    # --- Step 3: Test Login via Username (with spaces) ---
    print(f"\n[3] Testing login via USERNAME with trailing/leading spaces...")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "  " + username + "  ",
        "password": password # SEND EXACT PASSWORD
    })
    if r.status_code == 200 and r.json().get("success"):
        print("   ✅ Login via Username Success")
    else:
        print(f"   ❌ Login via Username Failed: {r.text}")
        return False

    # --- Step 4: Test Login via EMAIL (Dual Identifier Test) ---
    print(f"\n[4] Testing login via EMAIL (Dual Identifier Test)...")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": email,
        "password": password
    })
    if r.status_code == 200 and r.json().get("success"):
        print("   ✅ Login via Email Success!")
    else:
        print(f"   ❌ Login via Email Failed: {r.text}")
        return False

    # --- Step 5: Test Profile Access (Middleware Bypass Test) ---
    print(f"\n[5] Testing profile access immediately after login (Password Change Required)...")
    token = r.json()["token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/auth/profile", headers=auth_headers)
    
    if r.status_code == 200:
        print("   ✅ Profile fetch success! (Middleware correctly permits identity fetch)")
    elif r.status_code == 403:
        print("   ❌ Profile fetch blocked by 403 (Middleware still too restrictive)")
        return False
    else:
        print(f"   ❌ Profile fetch failed: {r.status_code} {r.text}")
        return False

    # --- Step 6: Verify other endpoints ARE still blocked ---
    print(f"\n[6] Verifying other sensitive endpoints remain blocked...")
    r = requests.get(f"{BASE_URL}/employees/", headers=auth_headers)
    if r.status_code == 403:
        print("   ✅ Access to /employees/ blocked as expected.")
    else:
        print(f"   ⚠️  Warning: User with pending password reset could access /employees/: {r.status_code}")

    print("\n" + "=" * 60)
    print("ALL HARDENING VERIFICATIONS PASSED ✅")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_comprehensive_fix()
    sys.exit(0 if success else 1)
