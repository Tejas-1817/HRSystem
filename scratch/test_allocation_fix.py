import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = f"http://localhost:{os.getenv('PORT', 5001)}"

def test_allocation_fix():
    # 1. Login as HR
    login_data = {"username": "riya@gmail.com", "password": "Riya@123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.json()}")
        return
    
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Kartik's employee ID (He is T_Kartik)
    emp_resp = requests.get(f"{BASE_URL}/employees/", headers=headers)
    kartik = next((e for e in emp_resp.json()["employees"] if e["name"] == "T_Kartik"), None)
    if not kartik:
        print("T_Kartik not found.")
        return
    
    print(f"Initial State for T_Kartik: {kartik['total_utilization']}% utilization, {kartik['remaining_availability']}% availability")

    # 3. Update Project 1 assignment to 50%
    # Project 1 ID is 1 (Employee Records)
    update_data = {"project_id": 1, "employee_name": "T_Kartik", "billable_percentage": 50}
    requests.put(f"{BASE_URL}/projects/assign", json=update_data, headers=headers)
    
    # 4. Verify 50/50
    emp_resp = requests.get(f"{BASE_URL}/employees/{kartik['id']}", headers=headers)
    kartik_updated = emp_resp.json()["employee"]
    print(f"Post-Update State: {kartik_updated['total_utilization']}% utilization, {kartik_updated['remaining_availability']}% availability")
    
    if kartik_updated['total_utilization'] == 50.0 and kartik_updated['remaining_availability'] == 50.0:
        print("Success! 50% utilization detected.")
    else:
        print(f"Failure! Expected 50/50 but got {kartik_updated['total_utilization']}/{kartik_updated['remaining_availability']}")

    # 5. Add second assignment (Project 2: Payroll System, at 30%)
    assign_data = {"project_id": 2, "employee_name": "T_Kartik", "billable_percentage": 30}
    requests.post(f"{BASE_URL}/projects/assign", json=assign_data, headers=headers)
    
    # 6. Verify 80/20
    emp_resp = requests.get(f"{BASE_URL}/employees/{kartik['id']}", headers=headers)
    kartik_final = emp_resp.json()["employee"]
    print(f"Final State (Project 1: 50%, Project 2: 30%): {kartik_final['total_utilization']}% utilization, {kartik_final['remaining_availability']}% availability")
    
    if kartik_final['total_utilization'] == 80.0 and kartik_final['remaining_availability'] == 20.0:
        print("Success! Combined utilization of 80% detected.")
    else:
        print(f"Failure! Expected 80/20 but got {kartik_final['total_utilization']}/{kartik_final['remaining_availability']}")

if __name__ == "__main__":
    test_allocation_fix()
