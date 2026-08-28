import requests, jwt
from datetime import datetime, timedelta
from app.config import Config
from app.models.database import execute_single

BASE_URL = "http://127.0.0.1:5001"

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

def test_role_change():
    print("=== Testing Edit Employee Role Functionality ===")
    
    # 1. Generate HR token
    hr_token = make_token("H_Saurabh", "hr", 4)
    headers = {"Authorization": f"Bearer {hr_token}"}
    
    # Find employee T_Atharva Patekar
    emp = execute_single("SELECT id, name, role FROM employee WHERE name = 'T_Atharva Patekar'")
    if not emp:
        emp = execute_single("SELECT id, name, role FROM employee LIMIT 1")
    
    emp_id = emp["id"]
    old_role = emp.get("role") or "employee"
    target_role = "manager" if old_role != "manager" else "employee"
    
    print(f"[1] Target employee: {emp['name']} (ID: {emp_id}), current role: {old_role}")
    
    # 2. Test PUT /employees/{id}/role
    r = requests.put(f"{BASE_URL}/employees/{emp_id}/role", json={"role": target_role}, headers=headers)
    print(f"[2] PUT /employees/{emp_id}/role status: {r.status_code}, response: {r.json()}")
    assert r.status_code == 200, f"Role change failed: {r.text}"
    
    # Verify in DB
    updated_emp = execute_single("SELECT id, name, role FROM employee WHERE id = %s", (emp_id,))
    updated_user = execute_single("SELECT id, employee_name, role FROM users WHERE employee_id = %s OR employee_name = %s", (emp_id, emp["name"]))
    print(f"    DB employee.role: {updated_emp.get('role')}")
    if updated_user:
        print(f"    DB users.role: {updated_user.get('role')}")
    assert updated_emp["role"] == target_role, "Employee table role not updated!"
    
    # 3. Test GET /employees/{id}
    r_get = requests.get(f"{BASE_URL}/employees/{emp_id}", headers=headers)
    assert r_get.status_code == 200
    res_role = r_get.json().get("employee", {}).get("role")
    print(f"[3] GET /employees/{emp_id} returns role: {res_role}")
    assert res_role == target_role, f"GET returned wrong role {res_role}"
    
    # 4. Revert back
    r_rev = requests.put(f"{BASE_URL}/employees/{emp_id}/role", json={"role": old_role}, headers=headers)
    print(f"[4] Revert status: {r_rev.status_code}")
    assert r_rev.status_code == 200
    
    print("\nRole update test completed successfully!")

if __name__ == "__main__":
    test_role_change()
