import requests
import json
import time

BASE_URL = "http://localhost:5001"

def login(username, password):
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    return res.json().get("token")

def test_delete_project():
    token = login("riya@gmail.com", "Welcome@123")
    if not token:
        print("Login failed")
        return
    
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a dummy project
    print("Creating temporary project...")
    p_res = requests.post(f"{BASE_URL}/projects/", headers=headers, json={"name": f"Temp Delete {int(time.time())}"})
    p_data = p_res.json()
    internal_id = p_data.get("id")
    print(f"Project created with Internal ID: {internal_id}")

    # 2. Assign someone to it
    print("Assigning T_Kartik to project...")
    requests.post(f"{BASE_URL}/projects/assign", headers=headers, json={
        "project_id": internal_id,
        "employee_name": "T_Kartik"
    })

    # 3. Create a unique test employee
    print("\nCreating test employee 'SingleProjectUser'...")
    unique_user = f"user_{int(time.time())}"
    reg_res = requests.post(f"{BASE_URL}/auth/register", headers=headers, json={
        "username": unique_user,
        "password": "Password@123",
        "employee_name": "SingleProjectUser",
        "email": f"{unique_user}@example.com",
        "role": "employee"
    })
    if reg_res.status_code != 201:
        print(f"Registration failed: {reg_res.json()}")
        return
    
    user_name = reg_res.json().get("employee_name")
    print(f"Registered as: {user_name}")
    
    # Assign to our temp project
    requests.post(f"{BASE_URL}/projects/assign", headers=headers, json={
        "project_id": internal_id,
        "employee_name": user_name
    })

    # 4. Check status
    emp = requests.get(f"{BASE_URL}/employees/", headers=headers).json()["employees"]
    user = next(e for e in emp if e["name"] == user_name)
    print(f"Employee status before delete: {user['status']}")

    # 5. Delete Project
    print(f"Deleting project {internal_id}...")
    d_res = requests.delete(f"{BASE_URL}/projects/{internal_id}", headers=headers)
    print(f"Delete Result: {d_res.status_code}, {d_res.json()}")

    # 6. Verify employee status sync (Should be bench now)
    emp = requests.get(f"{BASE_URL}/employees/", headers=headers).json()["employees"]
    user = next(e for e in emp if e["name"] == user_name)
    print(f"Employee status after delete: {user['status']}")
    
    if user['status'] == 'bench':
        print("\n✅ Verification Successful: Employee correctly reverted to 'bench'.")
    else:
        print("\n❌ Verification Failed: Employee status incorrect.")

if __name__ == "__main__":
    test_delete_project()
