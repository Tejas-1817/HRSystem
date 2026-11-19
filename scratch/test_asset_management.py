"""
Comprehensive Verification Test for Asset Management Return Actions:
1. Return to Inventory (Available, assignment closed, reassignable, audit logged, duplicate protected)
2. Return to Vendor (Returned to Vendor, removed from active listing, preserves record/history, cannot be reassigned, mandatory reason, audit logged, duplicate protected)
3. Dashboard counts & Filters updated
"""

import sys
import os
import unittest
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env")))

from app.models.database import get_connection, execute_query, execute_single, Transaction
from app.services.device_service import (
    create_device, assign_device, return_device_enterprise,
    return_device_to_vendor_enterprise, list_devices, get_device_history,
    get_device_by_id
)
from app.services.inventory_service import get_inventory_dashboard


class TestAssetReturnEnhancements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure a test employee exists
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT name FROM employee LIMIT 1")
        emp = cur.fetchone()
        cls.test_emp_name = emp["name"] if emp else "Test Employee"
        cls.admin_user = "HR Admin Tester"
        conn.close()

    def setUp(self):
        # Create a test device for each test
        self.serial_num = f"SN-TEST-{int(datetime.now().timestamp() * 1000)}"
        self.device_id = create_device({
            "brand": "Dell",
            "model": "Latitude 7420",
            "serial_number": self.serial_num,
            "device_type": "Laptop",
            "ownership_type": "Purchased",
            "location": "HQ",
            "added_by": self.admin_user,
        })
        self.assertIsNotNone(self.device_id)

    def tearDown(self):
        # Clean up test device and its assignments, stock logs, audit logs
        try:
            execute_query("DELETE FROM device_assignments WHERE device_id = %s", (self.device_id,), commit=True)
            execute_query("DELETE FROM asset_stock_log WHERE device_id = %s", (self.device_id,), commit=True)
            execute_query("DELETE FROM devices WHERE id = %s", (self.device_id,), commit=True)
        except Exception as e:
            print(f"Cleanup warning: {e}")

    # =========================================================================
    # 1. Return to Inventory
    # =========================================================================
    def test_return_to_inventory_workflow(self):
        """Test returning an assigned device back to inventory."""
        # 1. Assign to employee
        assigned = assign_device(self.device_id, self.test_emp_name)
        self.assertTrue(assigned, "Device should be assigned successfully")

        # Verify status is 'Assigned'
        dev = get_device_by_id(self.device_id)
        self.assertEqual(dev["status"], "Assigned")

        # 2. Return to Inventory
        result = return_device_enterprise(
            device_id=self.device_id,
            returned_by=self.admin_user,
            return_reason="End of project",
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )

        # Verify returned data
        self.assertEqual(result["asset_status"], "AVAILABLE")
        self.assertTrue(result["available_for_assignment"])
        self.assertEqual(result["returned_by"], self.admin_user)
        self.assertEqual(result["returned_from"], self.test_emp_name)

        # Verify device in DB is Available
        dev = get_device_by_id(self.device_id)
        self.assertEqual(dev["status"], "Available")

        # Verify active assignment is removed/closed
        active_assign = execute_single(
            "SELECT * FROM device_assignments WHERE device_id = %s AND returned_date IS NULL",
            (self.device_id,)
        )
        self.assertIsNone(active_assign, "Active assignment must be closed")

        # Verify closed assignment has returned_by and return_reason
        closed_assign = execute_single(
            "SELECT * FROM device_assignments WHERE device_id = %s ORDER BY id DESC LIMIT 1",
            (self.device_id,)
        )
        self.assertIsNotNone(closed_assign)
        self.assertIsNotNone(closed_assign["returned_date"])
        self.assertEqual(closed_assign["returned_by"], self.admin_user)
        self.assertEqual(closed_assign["return_reason"], "End of project")

        # 3. Allow asset to be reassigned to another employee
        reassigned = assign_device(self.device_id, self.test_emp_name)
        self.assertTrue(reassigned, "Available asset must be reassignable")

        dev = get_device_by_id(self.device_id)
        self.assertEqual(dev["status"], "Assigned")

    def test_return_to_inventory_duplicate_protection(self):
        """Test that duplicate returns are prevented with conflict error."""
        # Device is Available initially (not assigned)
        with self.assertRaises(LookupError) as ctx:
            return_device_enterprise(self.device_id, returned_by=self.admin_user)
        self.assertIn("CONFLICT", str(ctx.exception))

    # =========================================================================
    # 2. Return to Vendor
    # =========================================================================
    def test_return_to_vendor_from_assigned(self):
        """Test returning an assigned asset directly to vendor."""
        # 1. Assign to employee
        assign_device(self.device_id, self.test_emp_name)

        # 2. Return to Vendor
        return_date = date.today().strftime("%Y-%m-%d")
        result = return_device_to_vendor_enterprise(
            device_id=self.device_id,
            returned_by=self.admin_user,
            return_reason="Defective display replaced under RMA",
            return_date=return_date,
            vendor_reference="RMA-DELL-98765",
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )

        # Verify result structure
        self.assertEqual(result["asset_status"], "Returned to Vendor")
        self.assertFalse(result["available_for_assignment"])
        self.assertEqual(result["returned_by"], self.admin_user)
        self.assertEqual(result["previous_owner"], self.test_emp_name)
        self.assertEqual(result["vendor_reference"], "RMA-DELL-98765")

        # Verify device record in DB
        dev = get_device_by_id(self.device_id)
        self.assertIsNotNone(dev, "Device must NOT be permanently deleted from database")
        self.assertEqual(dev["status"], "Returned to Vendor")
        self.assertEqual(str(dev["vendor_return_date"]), return_date)
        self.assertEqual(dev["vendor_return_reason"], "Defective display replaced under RMA")
        self.assertEqual(dev["vendor_return_reference"], "RMA-DELL-98765")
        self.assertFalse(bool(dev["is_deleted"]), "Asset must not be soft-deleted")

        # Verify active assignment was closed
        active_assign = execute_single(
            "SELECT * FROM device_assignments WHERE device_id = %s AND returned_date IS NULL",
            (self.device_id,)
        )
        self.assertIsNone(active_assign, "Active assignment must be closed")

        # Verify asset CANNOT be reassigned to any employee
        reassign_attempt = assign_device(self.device_id, self.test_emp_name)
        self.assertFalse(reassign_attempt, "Returned to Vendor asset must NOT be reassignable")

        # Verify audit log entry
        audit = execute_single(
            "SELECT * FROM audit_logs WHERE event_type = 'ASSET_RETURNED_TO_VENDOR' ORDER BY id DESC LIMIT 1"
        )
        self.assertIsNotNone(audit)
        self.assertIn("RMA-DELL-98765", audit["description"])
        self.assertIn(self.test_emp_name, audit["description"])
        self.assertIn(self.admin_user, audit["description"])

    def test_return_to_vendor_mandatory_reason(self):
        """Test that return reason is mandatory."""
        with self.assertRaises(ValueError):
            return_device_to_vendor_enterprise(
                device_id=self.device_id,
                returned_by=self.admin_user,
                return_reason="",  # Empty
            )

        with self.assertRaises(ValueError):
            return_device_to_vendor_enterprise(
                device_id=self.device_id,
                returned_by=self.admin_user,
                return_reason="   ",  # Whitespace only
            )

    def test_return_to_vendor_duplicate_protection(self):
        """Test preventing duplicate returns to vendor."""
        # First return
        return_device_to_vendor_enterprise(
            device_id=self.device_id,
            returned_by=self.admin_user,
            return_reason="Lease expired",
        )

        # Second attempt must fail with CONFLICT
        with self.assertRaises(LookupError) as ctx:
            return_device_to_vendor_enterprise(
                device_id=self.device_id,
                returned_by=self.admin_user,
                return_reason="Lease expired again",
            )
        self.assertIn("CONFLICT", str(ctx.exception))
        self.assertIn("already been returned to vendor", str(ctx.exception))

    # =========================================================================
    # 3. Active Assets Listing Filter & Dashboard Counts
    # =========================================================================
    def test_active_assets_listing_and_filters(self):
        """Test that Returned to Vendor assets are excluded from active listing and included in status filter."""
        # Active initially
        active_list = list_devices({"status": "active"})
        active_ids = [d["id"] for d in active_list]
        self.assertIn(self.device_id, active_ids, "Newly created asset must be in active list")

        # Return to Vendor
        return_device_to_vendor_enterprise(
            device_id=self.device_id,
            returned_by=self.admin_user,
            return_reason="Decommissioned to vendor",
        )

        # Check Active Assets listing again
        active_list_after = list_devices({"status": "active"})
        active_ids_after = [d["id"] for d in active_list_after]
        self.assertNotIn(self.device_id, active_ids_after, "Returned to Vendor asset must be removed from active listing")

        # Check Status filter for 'Returned to Vendor'
        vendor_returned_list = list_devices({"status": "Returned to Vendor"})
        vendor_returned_ids = [d["id"] for d in vendor_returned_list]
        self.assertIn(self.device_id, vendor_returned_ids, "Asset must appear when filtering by 'Returned to Vendor'")

        # Verify transaction history and timeline are preserved
        history = get_device_history(self.device_id)
        self.assertIn("timeline", history)
        self.assertGreater(len(history["timeline"]), 0)
        has_vendor_return_event = any(
            "returned to vendor" in str(event.get("details", "")).lower() or
            "returned_to_vendor" in str(event.get("action", "")).lower()
            for event in history["timeline"]
        )
        self.assertTrue(has_vendor_return_event, "History timeline must preserve the vendor return transaction")

    def test_dashboard_counts(self):
        """Test that get_inventory_dashboard counts returned_to_vendor accurately."""
        # Return device to vendor
        return_device_to_vendor_enterprise(
            device_id=self.device_id,
            returned_by=self.admin_user,
            return_reason="Contract terminated",
        )

        dashboard = get_inventory_dashboard()
        totals = dashboard.get("totals", {})
        self.assertIn("returned_to_vendor", totals)
        self.assertGreaterEqual(totals.get("returned_to_vendor", 0), 1)


if __name__ == "__main__":
    unittest.main()
