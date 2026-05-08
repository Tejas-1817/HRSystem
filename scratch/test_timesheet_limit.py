import requests
import json

BASE_URL = "http://localhost:5001"

def get_token(username, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    return r.json().get("token")

def test_daily_limit():
    print("=== Testing 24-Hour Daily Timesheet Limit ===")
    
    # Use Raj (Employee)
    token = get_token("raj@gmail.com", "Welcome@123")
    headers = {"Authorization": f"Bearer {token}"}
    test_date = "2026-05-01" # Future date so it doesn't conflict with existing data
    
    # Clean up any existing data for this test date
    from app.models.database import execute_query
    execute_query("DELETE FROM timesheets WHERE employee_name = 'T_Raj' AND start_date = %s", (test_date,), commit=True)

    # 1. Try to add 25 hours in one entry
    print("\n[1] Attempting to add 25 hours in a single entry...")
    payload = {
        "project": "Internal",
        "task": "Test Limit",
        "hours": 25,
        "start_date": test_date
    }
    r = requests.post(f"{BASE_URL}/timesheets/", json=payload, headers=headers)
    print(f"Response: {r.status_code} - {r.json()}")
    assert r.status_code == 400
    assert "cannot exceed 24 hours" in r.json()["error"]

    # 2. Add 10 hours successfully
    print("\n[2] Adding 10 hours (should succeed)...")
    payload["hours"] = 10
    r = requests.post(f"{BASE_URL}/timesheets/", json=payload, headers=headers)
    print(f"Response: {r.status_code} - {r.json()}")
    assert r.status_code == 201
    entry_id = execute_single("SELECT id FROM timesheets WHERE employee_name='T_Raj' AND start_date=%s", (test_date,))["id"]

    # 3. Try to add 15 more hours (Total 25)
    print("\n[3] Attempting to add 15 more hours (Total 10 + 15 = 25)...")
    payload["hours"] = 15
    payload["task"] = "Task 2"
    r = requests.post(f"{BASE_URL}/timesheets/", json=payload, headers=headers)
    print(f"Response: {r.status_code} - {r.json()}")
    assert r.status_code == 400
    assert "already logged 10.0 hours" in r.json()["error"]

    # 4. Try to update the 10-hour entry to 25 hours
    print("\n[4] Attempting to update the existing 10-hour entry to 25 hours...")
    r = requests.put(f"{BASE_URL}/timesheets/{entry_id}", json={"hours": 25}, headers=headers)
    print(f"Response: {r.status_code} - {r.json()}")
    assert r.status_code == 400

    # 5. Test Weekly Save Bulk Validation
    print("\n[5] Testing Weekly Save validation...")
    weekly_payload = {
        "start_date": "2026-05-04", # A Monday
        "rows": [
            {"project": "P1", "task": "T1", "mon": 15, "tue": 8, "wed": 8, "thu": 8, "fri": 8},
            {"project": "P2", "task": "T2", "mon": 10, "tue": 0, "wed": 0, "thu": 0, "fri": 0}
        ],
        "submit": False
    }
    # Mon total = 15 + 10 = 25
    r = requests.post(f"{BASE_URL}/timesheets/weekly/save", json=weekly_payload, headers=headers)
    print(f"Response: {r.status_code} - {r.json()}")
    assert r.status_code == 400
    assert "exceeds 24 hours (25.0)" in r.json()["error"]

    print("\n✅ All 24-hour limit tests PASSED!")

if __name__ == "__main__":
    from app.models.database import execute_single
    test_daily_limit()
