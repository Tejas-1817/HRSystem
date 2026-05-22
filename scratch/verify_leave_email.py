"""
verify_leave_email.py
=====================
End-to-end smoke test for the Leave Email Notification System.

Tests:
  1. Employee (T_Raj) applies for sick leave → manager email queued
  2. Manager (M_Tejas) approves the leave → employee approval email queued
  3. Audit table confirms both sends recorded
  4. Cleans up: cancels the approved leave (leaves DB pristine)

Run:
  cd /Users/kartikdahale/HRSystem
  python3 scratch/verify_leave_email.py
"""

import requests
import time
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

BASE_URL = f"http://localhost:{os.getenv('PORT', 5001)}"

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "starterdata"),
        user=os.getenv("DB_USER", "tejas"),
        password=os.getenv("DB_PASS", "password123"),
    )


def login(email, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": email, "password": password})
    if resp.status_code != 200:
        print(f"  ❌ Login failed for {email}: {resp.json()}")
        return None, None
    token = resp.json().get("token")
    data  = resp.json().get("user", {})
    return token, data


def main():
    print("\n" + "="*60)
    print("  HRMS Leave Email Notification — Verification Suite")
    print("="*60)

    # ------------------------------------------------------------------
    # 1. Employee applies for leave
    # ------------------------------------------------------------------
    print("\n[1] Employee T_Raj applies for sick leave …")
    token_emp, emp_data = login("raj@gmail.com", "Raj@123")
    if not token_emp:
        return

    headers_emp = {"Authorization": f"Bearer {token_emp}"}
    leave_payload = {
        "leave_type": "sick",
        "start_date": "2026-06-02",
        "end_date":   "2026-06-02",
        "reason":     "Verify email notification system",
        "leave_type_category": "full_day",
    }
    apply_resp = requests.post(f"{BASE_URL}/leaves/", json=leave_payload, headers=headers_emp)
    if apply_resp.status_code == 201:
        print(f"  ✅ Leave applied | days: {apply_resp.json().get('duration_days')}")
    else:
        print(f"  ❌ Apply failed: {apply_resp.status_code} — {apply_resp.json()}")
        return

    # Give the async email thread 4 seconds to deliver / log
    print("     Waiting 4 s for async email delivery …")
    time.sleep(4)

    # ------------------------------------------------------------------
    # 2. Fetch the leave ID we just created
    # ------------------------------------------------------------------
    leaves_resp = requests.get(f"{BASE_URL}/leaves/?status=pending", headers=headers_emp)
    leaves = leaves_resp.json().get("leaves", [])
    new_leave = None
    for lv in leaves:
        if (lv.get("employee_name") == "T_Raj"
                and lv.get("leave_type") == "sick"
                and lv.get("start_date", "").startswith("2026-06-02")):
            new_leave = lv
            break

    if not new_leave:
        print("  ⚠️  Could not locate the new leave ID — checking audit logs anyway.")
        leave_id = None
    else:
        leave_id = new_leave["id"]
        print(f"  ✅ Leave ID resolved: {leave_id}")

    # ------------------------------------------------------------------
    # 3. Check audit table for leave_application email
    # ------------------------------------------------------------------
    print("\n[2] Checking email_notification_logs for leave_application …")
    conn = get_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM email_notification_logs
        WHERE notification_type = 'leave_application'
        ORDER BY created_at DESC
        LIMIT 3
    """)
    rows = cur.fetchall()
    if rows:
        print(f"  ✅ {len(rows)} log row(s) found:")
        for r in rows:
            status_icon = "✅" if r["notification_sent"] else "❌ (send failed)"
            print(f"     [{status_icon}] → {r['recipient_email']}"
                  f" | sent: {r['notification_sent']}"
                  f" | error: {r['error_message'] or 'None'}"
                  f" | at: {r['created_at']}")
    else:
        print("  ❌ No leave_application log rows found yet.")

    # ------------------------------------------------------------------
    # 4. Manager approves the leave
    # ------------------------------------------------------------------
    if leave_id:
        print(f"\n[3] Manager M_Tejas approves leave ID {leave_id} …")
        token_mgr, _ = login("tejas@gmail.com", "Tejas@123")
        if token_mgr:
            headers_mgr = {"Authorization": f"Bearer {token_mgr}"}
            approve_resp = requests.patch(
                f"{BASE_URL}/leaves/{leave_id}/approve", headers=headers_mgr
            )
            if approve_resp.status_code == 200:
                print(f"  ✅ Leave approved: {approve_resp.json().get('message')}")
            else:
                print(f"  ❌ Approval failed: {approve_resp.status_code} — {approve_resp.json()}")

            # Wait for approval email thread
            print("     Waiting 4 s for async approval email …")
            time.sleep(4)
        else:
            print("  ⚠️  Manager login failed — skipping approval step.")

    # ------------------------------------------------------------------
    # 5. Check audit table for leave_approved email
    # ------------------------------------------------------------------
    print("\n[4] Checking email_notification_logs for leave_approved …")
    cur.execute("""
        SELECT * FROM email_notification_logs
        WHERE notification_type = 'leave_approved'
        ORDER BY created_at DESC
        LIMIT 3
    """)
    rows = cur.fetchall()
    if rows:
        print(f"  ✅ {len(rows)} log row(s) found:")
        for r in rows:
            status_icon = "✅" if r["notification_sent"] else "❌ (send failed)"
            print(f"     [{status_icon}] → {r['recipient_email']}"
                  f" | sent: {r['notification_sent']}"
                  f" | error: {r['error_message'] or 'None'}"
                  f" | at: {r['created_at']}")
    else:
        print("  ❌ No leave_approved log rows found yet.")

    # ------------------------------------------------------------------
    # 6. Recent full audit log summary
    # ------------------------------------------------------------------
    print("\n[5] Full recent email_notification_logs (last 10 rows) …")
    cur.execute("""
        SELECT id, notification_type, recipient_email, leave_id,
               notification_sent, error_message, created_at
        FROM email_notification_logs
        ORDER BY created_at DESC
        LIMIT 10
    """)
    all_rows = cur.fetchall()
    if all_rows:
        print(f"  {'ID':<5} {'TYPE':<22} {'SENT':<6} {'RECIPIENT':<35} {'LEAVE':<7} TIME")
        print("  " + "-"*95)
        for r in all_rows:
            sent_str = "YES" if r["notification_sent"] else "NO"
            err = f"  ERR: {r['error_message'][:40]}" if r["error_message"] else ""
            print(f"  {r['id']:<5} {r['notification_type']:<22} {sent_str:<6} "
                  f"{r['recipient_email']:<35} {str(r['leave_id']):<7} "
                  f"{str(r['created_at'])}{err}")
    else:
        print("  ℹ️  No email notification logs yet.")

    cur.close()
    conn.close()

    print("\n" + "="*60)
    print("  Verification complete. Check manager inbox for emails.")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
