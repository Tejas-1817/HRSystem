import requests
import json
import time

BASE_URL = "http://localhost:5001"

def test_forgot_password_flow():
    print("=== Testing Forgot Password Flow ===")
    
    # 1. Trigger forgot password for a known user (Saurabh)
    email = "saurabh@example.com"
    print(f"\n[1] Requesting password reset for {email}...")
    r = requests.post(f"{BASE_URL}/auth/forgot-password", json={"email": email})
    print(f"Response: {r.status_code} - {r.json()}")
    
    if r.status_code != 200:
        print("❌ Forgot password request failed")
        return

    # 2. Directly fetch token from DB for testing (since we can't 'read' the email)
    print("\n[2] Fetching reset token from database...")
    from app.models.database import execute_single
    user = execute_single("SELECT reset_token FROM users WHERE username = %s", ("saurabh@gmail.com",))
    token = user.get("reset_token")
    
    if not token:
        print("❌ Token not found in DB")
        return
    print(f"Token found: {token}")

    # 3. Reset password using the token
    new_password = "NewSecurePassword@2026"
    print(f"\n[3] Resetting password with token...")
    r = requests.post(f"{BASE_URL}/auth/reset-password", json={
        "token": token,
        "new_password": new_password,
        "confirm_password": new_password
    })
    print(f"Response: {r.status_code} - {r.json()}")
    
    if r.status_code != 200:
        print("❌ Password reset failed")
        return

    # 4. Verify token is cleared
    print("\n[4] Verifying token has been cleared (single-use)...")
    user_after = execute_single("SELECT reset_token FROM users WHERE username = %s", ("saurabh@gmail.com",))
    if user_after.get("reset_token") is None:
        print("✅ Token cleared successfully")
    else:
        print("❌ Token NOT cleared")

    # 5. Verify we can login with new password
    print("\n[5] Verifying login with new password...")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "saurabh@gmail.com",
        "password": new_password
    })
    print(f"Response: {r.status_code} - {r.json()}")
    if r.status_code == 200:
        print("✅ Login successful with new password!")
    else:
        print("❌ Login failed")

if __name__ == "__main__":
    test_forgot_password_flow()
