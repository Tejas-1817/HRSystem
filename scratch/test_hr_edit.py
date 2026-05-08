import requests
import json

BASE_URL = "http://localhost:5001"

def login(username, password):
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    return res.json().get("token")

def test_hr_edit():
    token = login("riya@gmail.com", "Welcome@123")
    if not token:
        print("Login failed")
        return
    
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch a project
    res = requests.get(f"{BASE_URL}/projects/", headers=headers)
    projects = res.json()["projects"]
    if not projects:
        print("No projects found")
        return
    
    pj = projects[0]
    pj_id = pj["id"]
    print(f"Testing edit for project ID {pj_id} ({pj['name']})")
    print(f"Current Manager Name: {pj.get('assigned_manager_name')}")

    # pj[0] in seed is managed by M_Tejas.
    # Let's try to update it and assign H_Riya (HR role) as its manager.
    print(f"\nHR (riya@gmail.com) attempting to assign H_Riya (HR role) as manager of Project {pj_id}...")
    payload = {
        "name": pj["name"] + " (Modified)",
        "manager_name": "H_Riya" 
    }
    update_res = requests.put(f"{BASE_URL}/projects/{pj_id}", headers=headers, json=payload)
    print(f"Update Result Status: {update_res.status_code}")
    print(f"Update Result Body: {update_res.json()}")

    if update_res.status_code == 200:
        print("\n✅ Verification Successful: HR can now manage project assignments involving HR roles.")
    else:
        print("\n❌ Verification Failed: Project update rejected.")

if __name__ == "__main__":
    test_hr_edit()
