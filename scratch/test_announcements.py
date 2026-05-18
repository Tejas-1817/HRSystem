import requests
import os
import io
import mysql.connector
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = f"http://localhost:{os.getenv('PORT', 5001)}"

def test_announcements():
    print("--- 🔍 Starting Announcement Management System Verification ---")
    
    # 1. Login as HR (Saurabh)
    login_data_hr = {"username": "saurabh@gmail.com", "password": "Saurabh@123"}
    resp_hr = requests.post(f"{BASE_URL}/auth/login", json=login_data_hr)
    if resp_hr.status_code != 200:
        print(f"❌ HR Login failed: {resp_hr.json()}")
        return
    token_hr = resp_hr.json()["token"]
    headers_hr = {"Authorization": f"Bearer {token_hr}"}
    print("✅ Logged in successfully as HR.")
    
    # 2. Login as Employee (Raj)
    login_data_emp = {"username": "raj@gmail.com", "password": "Raj@123"}
    resp_emp = requests.post(f"{BASE_URL}/auth/login", json=login_data_emp)
    if resp_emp.status_code != 200:
        print(f"❌ Employee Login failed: {resp_emp.json()}")
        return
    token_emp = resp_emp.json()["token"]
    headers_emp = {"Authorization": f"Bearer {token_emp}"}
    print("✅ Logged in successfully as Employee.")

    # [Step 1] HR Creates a Draft Announcement with XSS Script & Attachment
    print("\n[Step 1] HR creating a Draft announcement with HTML XSS script & attachment...")
    future_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Multipart form-data
    payload = {
        "title": "<script>alert('xss')</script>Annual Tech Conference 2026",
        "description": "<h3>Welcome!</h3> Join our tech event.<iframe src='evil.com'></iframe><p onclick='alert(1)'>Click here for details!</p>",
        "expires_at": future_date,
        "status": "draft"
    }
    
    # Mock a PDF file attachment
    mock_pdf = io.BytesIO(b"Fake PDF Announcement content.")
    files = {"attachment": ("annual_tech_conf.pdf", mock_pdf, "application/pdf")}
    
    create_resp = requests.post(f"{BASE_URL}/announcements", data=payload, files=files, headers=headers_hr)
    if create_resp.status_code != 201:
        print(f"❌ Failed to create announcement: {create_resp.json()}")
        return
    
    ann_id = create_resp.json()["announcement_id"]
    print(f"✅ Announcement created successfully. ID: {ann_id}")
    
    # [Step 2] Verify Sanitization and DB values
    print("\n[Step 2] Verifying HTML XSS input sanitization in database...")
    db_conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'tejas'),
        password=os.getenv('DB_PASS', 'password123'),
        database=os.getenv('DB_NAME', 'starterdata')
    )
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM announcements WHERE id = %s", (ann_id,))
    db_row = cursor.fetchone()
    
    title_sanitized = db_row["title"]
    desc_sanitized = db_row["description"]
    
    print(f"  Raw Title in DB: '{title_sanitized}'")
    print(f"  Raw Description in DB: '{desc_sanitized}'")
    
    if "<script>" not in title_sanitized and "<iframe" not in desc_sanitized and "onclick" not in desc_sanitized:
        print("  ✅ Sanitization verified: Dangerous HTML tags/event attributes removed.")
    else:
        print("  ❌ XSS Sanitization failed!")
        return

    # [Step 3] Verify Draft is hidden from Employee
    print("\n[Step 3] Verifying Draft announcement is hidden from Employee...")
    list_resp = requests.get(f"{BASE_URL}/announcements", headers=headers_emp)
    emp_announcements = list_resp.json()["announcements"]
    found_draft = any(a["id"] == ann_id for a in emp_announcements)
    
    detail_resp = requests.get(f"{BASE_URL}/announcements/{ann_id}", headers=headers_emp)
    
    if not found_draft and detail_resp.status_code == 403:
        print("  ✅ Draft is successfully hidden: Employee cannot list or access details (Returns 403).")
    else:
        print(f"  ❌ Security issue: Employee accessed a draft! Detail status code: {detail_resp.status_code}, Found in list: {found_draft}")
        return

    # [Step 4] HR publishes the Draft Announcement
    print("\n[Step 4] HR publishing the announcement...")
    update_payload = {"status": "published"}
    update_resp = requests.put(f"{BASE_URL}/announcements/{ann_id}", json=update_payload, headers=headers_hr)
    if update_resp.status_code == 200:
        print("  ✅ Announcement updated to published successfully.")
    else:
        print(f"  ❌ Failed to update announcement status: {update_resp.json()}")
        return

    # [Step 5] Verify Employee can now see it and download attachment
    print("\n[Step 5] Verifying Employee can now view the published announcement and download attachment...")
    list_resp2 = requests.get(f"{BASE_URL}/announcements", headers=headers_emp)
    emp_announcements2 = list_resp2.json()["announcements"]
    found_pub = next((a for a in emp_announcements2 if a["id"] == ann_id), None)
    
    detail_resp2 = requests.get(f"{BASE_URL}/announcements/{ann_id}", headers=headers_emp)
    
    # Download attachment
    dl_resp = requests.get(f"{BASE_URL}/announcements/{ann_id}/attachment", headers=headers_emp)
    
    if found_pub and detail_resp2.status_code == 200 and dl_resp.status_code == 200:
        print("  ✅ Employee can view the published announcement in the list, detail page, and download the PDF attachment!")
        print(f"  Short description preview: '{found_pub['short_description']}'")
    else:
        print(f"  ❌ Visibility check failed! Detail: {detail_resp2.status_code}, Attachment Download: {dl_resp.status_code}")
        return

    # [Step 6] Employee attempting CRUD operations (Should Fail with 403)
    print("\n[Step 6] Verifying Employee RBAC: Attempting to modify/delete announcements (Expected Fail)...")
    fail_create = requests.post(f"{BASE_URL}/announcements", json={"title": "Hack", "description": "Hacked", "expires_at": future_date}, headers=headers_emp)
    fail_update = requests.put(f"{BASE_URL}/announcements/{ann_id}", json={"title": "Hacked Title"}, headers=headers_emp)
    fail_delete = requests.delete(f"{BASE_URL}/announcements/{ann_id}", headers=headers_emp)
    
    if fail_create.status_code == 403 and fail_update.status_code == 403 and fail_delete.status_code == 403:
        print("  ✅ Employee CRUD operations blocked successfully (All returned 403 Forbidden).")
    else:
        print(f"  ❌ RBAC violation! Code: Create={fail_create.status_code}, Update={fail_update.status_code}, Delete={fail_delete.status_code}")
        return

    # [Step 7] Expiry Handling Verification
    print("\n[Step 7] Verifying Expiry Handling (Auto-Hide)...")
    # First, create with a future date to pass validation
    temp_future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    expired_payload = {
        "title": "Expired Safety Rules",
        "description": "Old safety rules from yesterday.",
        "expires_at": temp_future_date,
        "status": "published"
    }
    # HR creates it
    create_exp_resp = requests.post(f"{BASE_URL}/announcements", json=expired_payload, headers=headers_hr)
    if create_exp_resp.status_code != 201:
        print(f"❌ Failed to create temporary announcement: {create_exp_resp.json()}")
        return
    exp_ann_id = create_exp_resp.json()["announcement_id"]
    
    # Update expires_at to past date directly via cursor to simulate expired announcement
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE announcements SET expires_at = %s WHERE id = %s", (past_date, exp_ann_id))
    db_conn.commit()
    print(f"  Expired Announcement created and database updated to past date (ID: {exp_ann_id})")
    
    # Employee fetches list
    list_resp3 = requests.get(f"{BASE_URL}/announcements", headers=headers_emp)
    emp_announcements3 = list_resp3.json()["announcements"]
    found_expired = any(a["id"] == exp_ann_id for a in emp_announcements3)
    
    # Employee fetches detail
    exp_detail_resp = requests.get(f"{BASE_URL}/announcements/{exp_ann_id}", headers=headers_emp)
    
    if not found_expired and exp_detail_resp.status_code == 403:
        print("  ✅ Expired Announcement auto-hidden successfully: excluded from Employee list and blocks direct details access.")
    else:
        print(f"  ❌ Expiry protection failed! Listed: {found_expired}, Detail status: {exp_detail_resp.status_code}")
        return

    # [Step 8] Dashboard Widget Verification
    print("\n[Step 8] Verifying Dashboard Widget integration...")
    dash_resp = requests.get(f"{BASE_URL}/announcements/dashboard", headers=headers_emp)
    dash_data = dash_resp.json()
    
    dash_announcements = dash_data["announcements"]
    found_active_in_dash = any(a["id"] == ann_id for a in dash_announcements)
    found_expired_in_dash = any(a["id"] == exp_ann_id for a in dash_announcements)
    
    if found_active_in_dash and not found_expired_in_dash:
        print("  ✅ Dashboard Announcement Widget loaded successfully: displays active, published ones and excludes expired ones!")
    else:
        print(f"  ❌ Dashboard widget failed! Active found: {found_active_in_dash}, Expired found: {found_expired_in_dash}")
        return

    # [Step 9] HR Deletes the Announcements (Hard-delete and clean-up)
    print("\n[Step 9] HR deleting announcements...")
    del_resp = requests.delete(f"{BASE_URL}/announcements/{ann_id}", headers=headers_hr)
    del_exp_resp = requests.delete(f"{BASE_URL}/announcements/{exp_ann_id}", headers=headers_hr)
    
    if del_resp.status_code == 200 and del_exp_resp.status_code == 200:
        print("  ✅ Announcements deleted successfully by HR.")
    else:
        print("  ❌ Failed to delete announcements.")
        return

    # [Step 10] Audit Log Event Verification
    print("\n[Step 10] Verifying Audit Logging...")
    cursor.execute("""
        SELECT * FROM audit_logs 
        WHERE event_type IN ('announcement_create', 'announcement_update', 'announcement_delete')
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    audit_rows = cursor.fetchall()
    
    if len(audit_rows) >= 3:
        print("  ✅ Audit Logging verified! Events successfully written to 'audit_logs':")
        for audit in audit_rows:
            print(f"    - User ID: {audit['user_id']} | Event: {audit['event_type']} | Desc: {audit['description']}")
    else:
        print(f"  ❌ Missing audit logs in database! Count found: {len(audit_rows)}")
        return

    print("\n🎉 ALL VERIFICATION CHECKS PASSED SUCCESSFULLY! Production-ready enterprise status confirmed.")
    
    cursor.close()
    db_conn.close()

if __name__ == "__main__":
    test_announcements()
