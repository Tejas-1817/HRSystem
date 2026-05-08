import requests
import json

BASE_URL = "http://localhost:5001"

def login(username, password):
    print(f"\nAttempting login for {username}...")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json()}")
    return res.json().get("token") if res.status_code == 200 else None

def test_auth_issues():
    # 1. Login as HR (Assuming default credentials from seed or similar)
    # Note: Using riya@gmail.com which is HR in seed
    hr_token = login("riya@gmail.com", "Welcome@123")
    if not hr_token:
        print("Failed to login as HR. Check seed data.")
        return

    headers = {"Authorization": f"Bearer {hr_token}"}

    # 2. Test Case A: Add employee via /employees/ (The way HR usually does it)
    print("\n--- Test Case A: Add employee via /employees/ ---")
    emp_payload = {
        "employee_name": "Test Login A",
        "email": "testA@example.com",
        "role": "employee"
    }
    res_a = requests.post(f"{BASE_URL}/employees/", headers=headers, json=emp_payload)
    print(f"Add Employee Status: {res_a.status_code}")
    print(f"Add Employee Response: {res_a.json()}")

    # Try to login with default password
    login("testA@example.com", "Welcome@123")

    # 3. Test Case B: Add employee via /auth/register
    print("\n--- Test Case B: Add employee via /auth/register ---")
    reg_payload = {
        "username": "testB@example.com",
        "password": "Password123!",
        "employee_name": "Test Login B",
        "role": "employee"
    }
    res_b = requests.post(f"{BASE_URL}/auth/register", headers=headers, json=reg_payload)
    print(f"Register Status: {res_b.status_code}")
    print(f"Register Response: {res_b.json()}")

    # Try to login with provided password
    login("testB@example.com", "Password123!")

if __name__ == "__main__":
    test_auth_issues()
