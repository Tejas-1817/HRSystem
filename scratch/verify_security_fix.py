import requests
import sys

BASE_URL = "http://localhost:5001"

def test_security_fix():
    print("🔍 Starting Security Fix Verification...")
    
    # 1. Login
    print("🔑 Logging in...")
    login_data = {"username": "tejas@gmail.com", "password": "Tejas@123"}
    r = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if r.status_code != 200:
        print(f"❌ Login failed: {r.text}")
        return
    
    token = r.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful.")

    # 2. Check Cache-Control headers
    print("📡 Checking Cache-Control headers on protected route...")
    r = requests.get(f"{BASE_URL}/auth/profile", headers=headers)
    cc = r.headers.get("Cache-Control")
    pragma = r.headers.get("Pragma")
    expires = r.headers.get("Expires")
    
    print(f"   Cache-Control: {cc}")
    print(f"   Pragma: {pragma}")
    print(f"   Expires: {expires}")
    
    if "no-store" in cc and "no-cache" in cc and pragma == "no-cache" and expires == "0":
        print("✅ Cache-Control headers are CORRECT.")
    else:
        print("❌ Cache-Control headers are MISSING or INCORRECT.")

    # 3. Access protected route
    if r.status_code == 200:
        print("✅ Initial access to protected route successful.")
    else:
        print(f"❌ Initial access failed: {r.text}")
        return

    # 4. Logout
    print("🚪 Logging out...")
    r = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
    if r.status_code == 200:
        print("✅ Logout API call successful.")
    else:
        print(f"❌ Logout API call failed: {r.text}")
        return

    # 5. Verify token is invalidated
    print("🚫 Verifying token invalidation (should return 401)...")
    r = requests.get(f"{BASE_URL}/auth/profile", headers=headers)
    if r.status_code == 401:
        print("✅ SUCCESS: Token is blacklisted and access is denied.")
        print(f"   Response: {r.json().get('error')}")
    else:
        print(f"❌ FAILURE: Token still works after logout! Status: {r.status_code}")

if __name__ == "__main__":
    test_security_fix()
