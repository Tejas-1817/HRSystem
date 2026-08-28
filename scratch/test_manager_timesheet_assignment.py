import requests
from app.models.database import execute_single, execute_query

BASE_URL = "http://127.0.0.1:5001"

import jwt
from datetime import datetime, timedelta
from app.config import Config

def make_token(employee_name, role, user_id):
    payload = {
        "user_id": user_id,
        "username": f"{employee_name.lower()}@gmail.com",
        "role": role,
        "employee_name": employee_name,
        "password_change_required": False,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    t = jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")
    return t if isinstance(t, str) else t.decode("utf-8")

def test_flow():
    print("=== Testing Timesheet Manager Assignment & Approval Flow ===")
    
    # 1. Test GET /timesheets/managers
    token_emp = make_token("T_Kartik", "employee", 5)
        
    headers_emp = {"Authorization": f"Bearer {token_emp}"}
    r = requests.get(f"{BASE_URL}/timesheets/managers", headers=headers_emp)
    print(f"[1] GET /timesheets/managers status: {r.status_code}")
    managers = r.json().get("managers", [])
    print(f"    Managers found: {[m['employee_name'] for m in managers]}")
    assert len(managers) > 0, "No managers returned!"
    
    # Target manager: M_Priyanka
    chosen_manager = "M_Priyanka"
    
    # Clean up any test timesheets for today
    execute_query("DELETE FROM timesheets WHERE employee_name = 'T_Kartik' AND start_date = '2026-08-27' AND task = 'Manager Assignment Test'", commit=True)
    
    # 2. Submit timesheet with chosen manager
    payload = {
        "employee_name": "T_Kartik",
        "project": "HRMS Redesign",
        "manager_name": chosen_manager,
        "task": "Manager Assignment Test",
        "hours": 3.5,
        "start_date": "2026-08-27",
        "description": "Testing dynamic manager selection dropdown"
    }
    
    r = requests.post(f"{BASE_URL}/timesheets/", json=payload, headers=headers_emp)
    print(f"[2] POST /timesheets/ status: {r.status_code}, response: {r.json()}")
    assert r.status_code == 201, f"Failed to create timesheet: {r.text}"
    entry_id = r.json()["entry_id"]
    
    # Verify DB row
    row = execute_single("SELECT * FROM timesheets WHERE id = %s", (entry_id,))
    print(f"    DB row manager_name: {row.get('manager_name')}")
    assert row["manager_name"] == chosen_manager, "Manager name not saved in DB!"
    
    # 3. Log in as chosen manager (M_Priyanka) and check pending approvals
    token_priyanka = make_token("M_Priyanka", "manager", 2)
    headers_priyanka = {"Authorization": f"Bearer {token_priyanka}"}
    
    r_pending = requests.get(f"{BASE_URL}/timesheets/pending-approvals", headers=headers_priyanka)
    print(f"[3] M_Priyanka GET /timesheets/pending-approvals status: {r_pending.status_code}")
    pending_list = r_pending.json().get("pending_approvals", [])
    matching = [t for t in pending_list if t["id"] == entry_id]
    print(f"    Found entry {entry_id} in M_Priyanka's pending approvals: {bool(matching)}")
    assert len(matching) > 0, "Timesheet not found in assigned manager's pending approvals!"
    
    # 4. Check that M_Priyanka can view it in GET /timesheets/
    r_view = requests.get(f"{BASE_URL}/timesheets/", headers=headers_priyanka)
    view_list = r_view.json().get("timesheets", [])
    matching_view = [t for t in view_list if t["id"] == entry_id]
    print(f"[4] Found entry {entry_id} in M_Priyanka's /timesheets/ list: {bool(matching_view)}")
    assert len(matching_view) > 0, "Timesheet not visible in assigned manager's timesheet list!"
    
    # 5. M_Priyanka approves the timesheet
    r_app = requests.post(f"{BASE_URL}/timesheets/{entry_id}/approve", json={"comments": "Looks great, approved!"}, headers=headers_priyanka)
    print(f"[5] M_Priyanka approve timesheet status: {r_app.status_code}, response: {r_app.json()}")
    assert r_app.status_code == 200, f"Failed to approve timesheet: {r_app.text}"
    
    # Verify status in DB
    updated_row = execute_single("SELECT * FROM timesheets WHERE id = %s", (entry_id,))
    print(f"    Updated status in DB: {updated_row['status']}, approved_by: {updated_row['approved_by']}")
    assert updated_row["status"] == "approved", "Status was not updated to approved!"
    
    # Clean up test entry
    execute_query("DELETE FROM timesheets WHERE id = %s", (entry_id,), commit=True)
    print("\n✅ All tests passed successfully!")

if __name__ == "__main__":
    test_flow()
