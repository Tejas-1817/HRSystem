"""
Flask Test Client Verification for /devices/<id>/return and /devices/<id>/return-to-vendor
"""

import sys
import os
import unittest
import jwt
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env")))

from app import create_app
from app.config import Config
from app.models.database import execute_query, execute_single
from app.services.device_service import create_device, assign_device


class TestReturnRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        payload = {
            "id": 1,
            "user_id": 1,
            "username": "admin_test",
            "employee_name": "Admin Tester",
            "role": "admin"
        }
        cls.token = jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")
        cls.headers = {
            "Authorization": f"Bearer {cls.token}",
            "Content-Type": "application/json"
        }

    def setUp(self):
        self.device_id = create_device({
            "brand": "HP",
            "model": "EliteBook 840",
            "serial_number": f"SN-ROUTE-{int(datetime.now().timestamp() * 1000)}",
            "device_type": "Laptop",
            "ownership_type": "Purchased",
            "location": "HQ",
            "added_by": "Admin Tester",
        })

    def tearDown(self):
        try:
            execute_query("DELETE FROM device_assignments WHERE device_id = %s", (self.device_id,), commit=True)
            execute_query("DELETE FROM asset_stock_log WHERE device_id = %s", (self.device_id,), commit=True)
            execute_query("DELETE FROM devices WHERE id = %s", (self.device_id,), commit=True)
        except Exception:
            pass

    def test_return_to_inventory_endpoint(self):
        # Assign first
        assign_device(self.device_id, "Admin Tester")

        res = self.client.post(
            f"/devices/{self.device_id}/return",
            headers=self.headers,
            json={"return_reason": "Device upgrade completed"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["asset_status"], "AVAILABLE")
        self.assertEqual(data["returned_by"], "Admin Tester")

        # Duplicate return must fail with 409
        dup_res = self.client.post(
            f"/devices/{self.device_id}/return",
            headers=self.headers,
            json={}
        )
        self.assertEqual(dup_res.status_code, 409)

    def test_return_to_vendor_endpoint(self):
        # 1. Missing reason returns 400
        res_bad = self.client.post(
            f"/devices/{self.device_id}/return-to-vendor",
            headers=self.headers,
            json={"return_reason": ""}
        )
        self.assertEqual(res_bad.status_code, 400)

        # 2. Valid return
        res = self.client.post(
            f"/devices/{self.device_id}/return-to-vendor",
            headers=self.headers,
            json={
                "return_reason": "RMA return for motherboard failure",
                "return_date": "2026-11-19",
                "vendor_reference": "RMA-HP-112233"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["asset_status"], "Returned to Vendor")
        self.assertEqual(data["vendor_reference"], "RMA-HP-112233")

        # 3. Duplicate return must fail with 409
        dup_res = self.client.post(
            f"/devices/{self.device_id}/return-to-vendor",
            headers=self.headers,
            json={"return_reason": "Trying again"}
        )
        self.assertEqual(dup_res.status_code, 409)


if __name__ == "__main__":
    unittest.main()
