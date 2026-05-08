import requests
import os

BASE_URL = "http://localhost:5001"

def test_routes():
    # Login
    login_data = {"username": "admin@hr.com", "password": "Admin@123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.json()}")
        return
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    endpoints = [
        "/employees/",
        "/projects/",
        "/leaves/",
        "/reports/resource/utilization",
        "/reports/resource/billing-ratio",
        "/reports/payslips",
        "/auth/profile",
        "/auth/users",
        "/holidays/",
        "/notifications/",
        "/auth/admin/audit-logs"
    ]

    for ep in endpoints:
        print(f"Testing {ep} ...", end=" ")
        try:
            r = requests.get(f"{BASE_URL}{ep}", headers=headers)
            print(f"{r.status_code}")
            if r.status_code == 500:
                print(f"   ❌ ERROR: {r.json()}")
        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")

test_routes()
