"""
End-to-End Test Suite for Corporate Employee Offboarding Workflow & SYSTEM_ADMIN Role
Validates all 9 test scenarios required in the specification.
"""

import sys
import os
import json
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.models.database import execute_query, execute_single, Transaction
from werkzeug.security import generate_password_hash

app = create_app()
client = app.test_client()

def run_tests():
    print("==================================================")
    print("STARTING OFFBOARDING & SYSTEM_ADMIN E2E TEST SUITE")
    print("==================================================")

    with app.app_context():
        # Setup Test Users / Employees in DB
        # 1. Test Employee
        emp_email = "test.offboard.emp@altzor.com"
        personal_email = "test.offboard.personal@gmail.com"
        emp_name = "Test Offboard Employee"
        
        # Clean up any previous test records
        with Transaction() as cursor:
            cursor.execute("DELETE FROM device_assignments WHERE employee_name = %s", (emp_name,))
            cursor.execute("DELETE FROM devices WHERE serial_number = 'SN-OFFB-TEST-001'")
            cursor.execute("DELETE FROM offboarding_request WHERE employee_name = %s", (emp_name,))
            cursor.execute("DELETE FROM users WHERE username IN (%s, 'test.sysadmin@altzor.com', 'test.offboard.mgr@altzor.com')", (emp_email,))
            cursor.execute("DELETE FROM employee WHERE email IN (%s, 'test.sysadmin@altzor.com', 'test.offboard.mgr@altzor.com')", (emp_email,))

            # Create Employee
            cursor.execute("""
                INSERT INTO employee (name, email, phone, role, status, employment_status, department, designation)
                VALUES (%s, %s, '9999999999', 'employee', 'working', 'ACTIVE', 'Engineering', 'Software Engineer')
            """, (emp_name, emp_email))
            emp_id = cursor.lastrowid

            pwd_hash = generate_password_hash("Password@123")
            # Create User for employee
            cursor.execute("""
                INSERT INTO users (username, email, password, password_hash, role, employee_name, is_active, password_change_required)
                VALUES (%s, %s, %s, %s, 'employee', %s, TRUE, FALSE)
            """, (emp_email, emp_email, pwd_hash, pwd_hash, emp_name))
            user_id = cursor.lastrowid

            # Create Manager
            cursor.execute("""
                INSERT INTO employee (name, email, role, department, designation)
                VALUES ('Test Manager', 'test.offboard.mgr@altzor.com', 'manager', 'Engineering', 'Engineering Manager')
            """)
            mgr_emp_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO users (username, email, password, password_hash, role, employee_name, is_active, password_change_required)
                VALUES ('test.offboard.mgr@altzor.com', 'test.offboard.mgr@altzor.com', %s, %s, 'manager', 'Test Manager', TRUE, FALSE)
            """, (pwd_hash, pwd_hash))
            mgr_user_id = cursor.lastrowid

            # Create System Admin
            cursor.execute("""
                INSERT INTO employee (name, email, role, department, designation)
                VALUES ('Test System Admin', 'test.sysadmin@altzor.com', 'system_admin', 'IT Infrastructure', 'Systems Administrator')
            """)
            sa_emp_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO users (username, email, password, password_hash, role, employee_name, is_active, password_change_required)
                VALUES ('test.sysadmin@altzor.com', 'test.sysadmin@altzor.com', %s, %s, 'system_admin', 'Test System Admin', TRUE, FALSE)
            """, (pwd_hash, pwd_hash))
            sa_user_id = cursor.lastrowid

            # Assign a device to employee for asset return testing
            cursor.execute("""
                INSERT INTO devices (brand, model, serial_number, status, device_type)
                VALUES ('Dell', 'Latitude 7420', 'SN-OFFB-TEST-001', 'Assigned', 'Laptop')
            """)
            test_device_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO device_assignments (device_id, employee_name, assigned_date, acceptance_status)
                VALUES (%s, %s, CURRENT_DATE, 'accepted')
            """, (test_device_id, emp_name))

        # Helper to generate JWT tokens
        import jwt
        from app.config import Config
        from datetime import datetime, timezone, timedelta

        def make_token(uid, uname, role, ename):
            payload = {
                "user_id": uid,
                "username": uname,
                "role": role,
                "employee_name": ename,
                "exp": datetime.now(timezone.utc) + timedelta(hours=2)
            }
            return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")

        emp_token = make_token(user_id, emp_email, 'employee', emp_name)
        mgr_token = make_token(mgr_user_id, 'test.offboard.mgr@altzor.com', 'manager', 'Test Manager')
        sa_token = make_token(sa_user_id, 'test.sysadmin@altzor.com', 'system_admin', 'Test System Admin')
        hr_token = make_token(1, 'hr@altzor.com', 'hr', 'HR Admin')

        # -------------------------------------------------------------------
        # TEST 1: Employee submits resignation
        # → Corporate account remains active, notifications created
        # -------------------------------------------------------------------
        print("\n--- TEST 1: Employee Submits Resignation ---")
        res = client.post('/offboarding/resign', headers={"Authorization": f"Bearer {emp_token}"}, json={
            "personal_email": personal_email,
            "personal_phone": "9999999999",
            "resignation_date": str(date.today()),
            "proposed_last_working_day": str(date.today() + timedelta(days=30)),
            "reason": "Career Advancement / Better Opportunity",
            "reason_notes": "Pursuing new senior software role"
        })
        assert res.status_code == 201, f"Failed: {res.json}"
        offboarding_id = res.json['offboarding_id']
        print(f"[PASS] Resignation submitted. Case ID: {offboarding_id}")

        # Check DB: status is EXIT_REQUESTED, user account is active, employee is ACTIVE
        case = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
        assert case['status'] == 'EXIT_REQUESTED'
        u = execute_single("SELECT is_active FROM users WHERE id = %s", (user_id,))
        assert u['is_active'] == 1, "Corporate account must remain ACTIVE!"
        e = execute_single("SELECT employment_status, personal_email FROM employee WHERE id = %s", (emp_id,))
        assert e['employment_status'] == 'ACTIVE', "Employee must remain ACTIVE upon submission!"
        assert e['personal_email'] == personal_email
        print("[PASS] Corporate account is ACTIVE and employee status is ACTIVE.")

        # -------------------------------------------------------------------
        # TEST 2: Manager rejects
        # → Employee notified, offboarding does not start
        # -------------------------------------------------------------------
        print("\n--- TEST 2: Manager Rejection Flow ---")
        rej_res = client.post(f'/offboarding/cases/{offboarding_id}/manager-review', headers={"Authorization": f"Bearer {mgr_token}"}, json={
            "decision": "REJECTED",
            "rejection_reason": "Retention bonus discussion scheduled with director"
        })
        assert rej_res.status_code == 200, f"Failed: {rej_res.json}"
        case = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
        assert case['status'] == 'MANAGER_REJECTED'
        assert case['rejection_reason'] == "Retention bonus discussion scheduled with director"
        e = execute_single("SELECT employment_status FROM employee WHERE id = %s", (emp_id,))
        assert e['employment_status'] == 'ACTIVE'
        print("[PASS] Manager rejection recorded successfully. Status is MANAGER_REJECTED.")

        # -------------------------------------------------------------------
        # TEST 3: New resignation & Manager approves
        # → Offboarding case created, employee becomes NOTICE_PERIOD, corporate account stays active
        # -------------------------------------------------------------------
        print("\n--- TEST 3: Manager Approval & Notice Period Transition ---")
        res2 = client.post('/offboarding/resign', headers={"Authorization": f"Bearer {emp_token}"}, json={
            "personal_email": personal_email,
            "personal_phone": "9999999999",
            "resignation_date": str(date.today()),
            "proposed_last_working_day": str(date.today() + timedelta(days=30)),
            "reason": "Relocation / Family Relocation",
            "reason_notes": "Moving abroad"
        })
        assert res2.status_code == 201, f"Failed: {res2.json}"
        case_id = res2.json['offboarding_id']

        appr_res = client.post(f'/offboarding/cases/{case_id}/manager-review', headers={"Authorization": f"Bearer {mgr_token}"}, json={
            "decision": "APPROVED"
        })
        assert appr_res.status_code == 200, f"Failed: {appr_res.json}"

        case = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (case_id,))
        assert case['status'] == 'NOTICE_PERIOD'
        assert case['manager_name'] == 'Test Manager'
        e = execute_single("SELECT employment_status FROM employee WHERE id = %s", (emp_id,))
        assert e['employment_status'] == 'NOTICE_PERIOD', "Employee must be in NOTICE_PERIOD!"
        u = execute_single("SELECT is_active FROM users WHERE id = %s", (user_id,))
        assert u['is_active'] == 1, "Corporate account must REMAIN ACTIVE during notice period!"
        print("[PASS] Manager approved. Case status is NOTICE_PERIOD. Corporate login remains active.")

        # -------------------------------------------------------------------
        # TEST 4: Employee completes consent
        # → HR/System Admin receive appropriate tasks
        # -------------------------------------------------------------------
        print("\n--- TEST 4: Employee Offboarding Consent ---")
        consent_res = client.post(f'/offboarding/cases/{case_id}/consent', headers={"Authorization": f"Bearer {emp_token}"}, json={
            "signature_text": emp_name,
            "resignation_confirmed": True,
            "last_working_day_confirmed": True,
            "asset_return_acknowledged": True,
            "confidential_info_acknowledged": True,
            "data_handling_acknowledged": True,
            "access_termination_acknowledged": True,
            "final_clearance_acknowledged": True
        })
        assert consent_res.status_code == 200, f"Failed: {consent_res.json}"
        consent = execute_single("SELECT * FROM offboarding_consent WHERE offboarding_id = %s", (case_id,))
        assert consent['status'] == 'CONSENT_COMPLETED'
        assert consent['signature_text'] == emp_name
        print("[PASS] Employee consent recorded and marked CONSENT_COMPLETED.")

        # Update Knowledge Transfer (Parallel task)
        kt_res = client.post(f'/offboarding/cases/{case_id}/knowledge-transfer', headers={"Authorization": f"Bearer {mgr_token}"}, json={
            "replacement_employee_name": "Test Peer",
            "status": "COMPLETED",
            "pending_responsibilities": "Handover sprint backlog items",
            "documents_transferred": "GitHub wiki link"
        })
        assert kt_res.status_code == 200
        print("[PASS] Knowledge transfer updated to COMPLETED in parallel.")

        # -------------------------------------------------------------------
        # TEST 5: Asset returned
        # → Asset record updated, historical assignment preserved
        # -------------------------------------------------------------------
        print("\n--- TEST 5: Asset Return Integration ---")
        assets_res = client.get(f'/offboarding/cases/{case_id}/assets', headers={"Authorization": f"Bearer {hr_token}"})
        assert assets_res.status_code == 200
        devices = assets_res.json['assets']
        assert len(devices) == 1, f"Expected 1 assigned device, got: {len(devices)}"

        return_res = client.post(f'/offboarding/cases/{case_id}/assets/{test_device_id}/return', headers={"Authorization": f"Bearer {hr_token}"}, json={
            "return_status": "Returned",
            "condition": "Good",
            "remarks": "Returned charger and laptop in pristine condition"
        })
        assert return_res.status_code == 200, f"Failed: {return_res.json}"

        # Verify device is now Available
        d = execute_single("SELECT status FROM devices WHERE id = %s", (test_device_id,))
        assert d['status'] == 'Available', f"Device status should be Available, got {d['status']}"
        # Verify assignment history preserved (returned_date set, record not deleted)
        da = execute_single("SELECT * FROM device_assignments WHERE device_id = %s AND employee_name = %s", (test_device_id, emp_name))
        assert da is not None, "Assignment history must be preserved!"
        assert da['returned_date'] is not None, "Returned date must be populated!"
        print("[PASS] Asset returned. Device is Available and historical assignment is preserved.")

        # -------------------------------------------------------------------
        # TEST 6: Last Working Day IT Closure by System Admin
        # → System Admin disables corporate account, access status revoked
        # -------------------------------------------------------------------
        print("\n--- TEST 6: System Admin IT Closure & Account Deactivation ---")
        it_res = client.post(f'/offboarding/cases/{case_id}/it-deactivation', headers={"Authorization": f"Bearer {sa_token}"}, json={
            "checklist": {
                "corporate_account_disabled": True,
                "corporate_email_disabled": True,
                "application_access_revoked": True,
                "vpn_access_revoked": True,
                "github_access_revoked": True,
                "groups_removed": True,
                "sessions_revoked": True,
                "licenses_removed": True
            },
            "notes": "LWD deactivation completed. Email forwarder enabled to manager."
        })
        assert it_res.status_code == 200, f"Failed: {it_res.json}"

        # Verify users.is_active = FALSE
        u = execute_single("SELECT is_active FROM users WHERE id = %s", (user_id,))
        assert u['is_active'] == 0, "Corporate account MUST be deactivated (is_active = FALSE)!"
        
        # Verify IT systems status REVOKED
        it_systems = execute_query("SELECT access_status FROM offboarding_it_access WHERE offboarding_id = %s", (case_id,))
        assert all(s['access_status'] == 'REVOKED' for s in it_systems)
        print("[PASS] System Admin IT deactivation executed: Corporate account disabled and systems revoked.")

        # -------------------------------------------------------------------
        # TEST 7: Corporate Login Blocked, Personal Email + OTP Exit Portal Works
        # -------------------------------------------------------------------
        print("\n--- TEST 7: Disabled Corporate Login vs Exit Portal Access ---")
        # Attempt login with corporate account -> Must fail because is_active = FALSE
        corp_login = client.post('/auth/login', json={
            "username": emp_email,
            "password": "Password@123"
        })
        assert corp_login.status_code == 401, "Disabled account must not be allowed to log into corporate app!"
        print("[PASS] Disabled corporate login blocked with HTTP 401.")

        # Request OTP for Exit Portal using personal email
        otp_req = client.post('/exit-portal/request-otp', json={"personal_email": personal_email})
        assert otp_req.status_code == 200, f"Failed: {otp_req.json}"
        otp_code = otp_req.json.get('otp_preview')
        if not otp_code:
            # Query from DB
            row = execute_single("SELECT otp_code FROM exit_portal_otp WHERE personal_email = %s AND is_used = FALSE", (personal_email,))
            otp_code = row['otp_code']
        print(f"[PASS] Exit Portal OTP generated: {otp_code}")

        # Verify OTP
        otp_verify = client.post('/exit-portal/verify-otp', json={
            "personal_email": personal_email,
            "otp": otp_code
        })
        assert otp_verify.status_code == 200, f"Failed: {otp_verify.json}"
        exit_token = otp_verify.json['token']
        print("[PASS] Exit Portal OTP verified. Session token issued.")

        # Fetch Exit Portal status
        status_res = client.get('/exit-portal/status', headers={"Authorization": f"Bearer {exit_token}"})
        assert status_res.status_code == 200, f"Failed: {status_res.json}"
        status_data = status_res.json
        assert status_data['timeline']['resignation_approved'] is True
        assert status_data['timeline']['assets_returned'] is True
        assert status_data['timeline']['it_access_closed'] is True
        assert status_data['personal_email'] == personal_email
        print("[PASS] Exit Portal status retrieved: Resignation Approved, Assets Returned, IT Closed all verified.")

        # -------------------------------------------------------------------
        # TEST 8: HR completes final clearance
        # → Employee becomes OFFBOARDED, historical records preserved
        # -------------------------------------------------------------------
        print("\n--- TEST 8: HR Final Clearance & Completion ---")
        hr_clear_res = client.post(f'/offboarding/cases/{case_id}/hr-clearance', headers={"Authorization": f"Bearer {hr_token}"})
        assert hr_clear_res.status_code == 200, f"Failed: {hr_clear_res.json}"

        case = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (case_id,))
        assert case['status'] == 'COMPLETED'
        e = execute_single("SELECT employment_status FROM employee WHERE id = %s", (emp_id,))
        assert e['employment_status'] == 'OFFBOARDED', "Employee must be OFFBOARDED after HR final clearance!"
        print("[PASS] HR Final Clearance completed. Employee employment_status is now OFFBOARDED.")

        # -------------------------------------------------------------------
        # TEST 9: Unauthorized role attempts restricted actions
        # → API rejects request with HTTP 403
        # -------------------------------------------------------------------
        print("\n--- TEST 9: Role Guardrails & Security Enforcement ---")
        # System Admin attempts to approve resignation -> MUST BE FORBIDDEN (403)
        sa_approve = client.post(f'/offboarding/cases/{case_id}/manager-review', headers={"Authorization": f"Bearer {sa_token}"}, json={
            "decision": "APPROVED"
        })
        assert sa_approve.status_code == 403, f"Expected 403 for System Admin approving resignation, got: {sa_approve.status_code}"
        print("[PASS] System Admin blocked from approving resignation (HTTP 403).")

        # System Admin attempts HR final clearance -> MUST BE FORBIDDEN (403)
        sa_hr = client.post(f'/offboarding/cases/{case_id}/hr-clearance', headers={"Authorization": f"Bearer {sa_token}"})
        assert sa_hr.status_code == 403, f"Expected 403 for System Admin performing HR clearance, got: {sa_hr.status_code}"
        print("[PASS] System Admin blocked from performing HR clearance (HTTP 403).")

        # Regular employee attempts HR clearance -> MUST BE FORBIDDEN (403)
        emp_hr = client.post(f'/offboarding/cases/{case_id}/hr-clearance', headers={"Authorization": f"Bearer {emp_token}"})
        assert emp_hr.status_code == 403, f"Expected 403 for Employee performing HR clearance, got: {emp_hr.status_code}"
        print("[PASS] Regular employee blocked from performing HR clearance (HTTP 403).")

        print("\n==================================================")
        print("ALL 9 E2E OFFBOARDING & SYSTEM ADMIN TESTS PASSED!")
        print("==================================================")

if __name__ == '__main__':
    run_tests()
