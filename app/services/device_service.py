from app.models.database import execute_query, execute_single, Transaction
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _log_stock(device_id, catalog_id, action, performed_by, old_status=None, new_status=None, notes=None):
    """Log a stock event. Lazy import to avoid circular dependency."""
    try:
        from app.services.inventory_service import log_stock_event
        log_stock_event(device_id, catalog_id, action, performed_by, old_status, new_status, notes)
    except Exception as e:
        logger.warning(f"Stock log failed for device {device_id}: {e}")

# ---------------------------------------------------------------------------
# Device Management Logic
# ---------------------------------------------------------------------------

def list_devices(filters: dict = None) -> list:
    """List devices with optional filtering, including current assignee details."""
    conditions = []
    params = []

    if filters:
        if filters.get("status"):
            conditions.append("d.status = %s")
            params.append(filters["status"])
        if filters.get("brand"):
            conditions.append("d.brand = %s")
            params.append(filters["brand"])
        if filters.get("device_type"):
            conditions.append("d.device_type = %s")
            params.append(filters["device_type"])
        if filters.get("search"):
            conditions.append("(d.brand LIKE %s OR d.model LIKE %s OR d.serial_number LIKE %s)")
            search_param = f"%{filters['search']}%"
            params.extend([search_param] * 3)

    # Always exclude soft-deleted devices
    conditions.append("d.is_deleted = FALSE")
    where_clause = "WHERE " + " AND ".join(conditions)

    rows = execute_query(f"""
        SELECT d.*,
               da.id AS assignment_id,
               da.employee_name AS assigned_to,
               da.assigned_date,
               da.acceptance_status,
               e.id AS employee_id,
               e.name AS employee_name,
               e.email AS employee_email,
               e.phone AS employee_phone
        FROM devices d
        LEFT JOIN device_assignments da
            ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e
            ON da.employee_name = e.name
        {where_clause}
        ORDER BY d.created_at DESC
    """, tuple(params) if params else None)

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return rows


def get_device_by_id(device_id: int):
    """Fetch a single device by ID with current assignee and images."""
    device = execute_single("""
        SELECT d.*,
               da.id AS assignment_id,
               da.employee_name AS assigned_to,
               da.assigned_date,
               da.acceptance_status,
               da.accepted_at,
               e.id AS employee_id,
               e.name AS employee_name,
               e.email AS employee_email,
               e.phone AS employee_phone
        FROM devices d
        LEFT JOIN device_assignments da
            ON d.id = da.device_id AND da.returned_date IS NULL
        LEFT JOIN employee e
            ON da.employee_name = e.name
        WHERE d.id = %s AND d.is_deleted = FALSE
    """, (device_id,))
    if device:
        for k, v in device.items():
            if hasattr(v, "isoformat"):
                device[k] = v.isoformat()
        
        # Fetch images
        images = execute_query("SELECT id, image_url, uploaded_at FROM device_images WHERE device_id = %s", (device_id,))
        for img in images:
            img["uploaded_at"] = img["uploaded_at"].isoformat()
        device["images"] = images
        
    return device


def create_device(data: dict) -> int:
    """Add a new device to the system with optional catalog linkage and purchase metadata."""
    catalog_id = data.get("catalog_id")

    # Auto-link to catalog by brand+model if not explicitly provided
    if not catalog_id:
        cat = execute_single(
            "SELECT id FROM asset_catalog WHERE brand = %s AND model = %s",
            (data["brand"], data["model"])
        )
        if cat:
            catalog_id = cat["id"]

    device_id = execute_query("""
        INSERT INTO devices (brand, model, serial_number, status, device_type,
                             catalog_id, purchase_date, warranty_expiry, condition_notes, location)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data["brand"], data["model"], data["serial_number"],
        data.get("status", "Available"), data.get("device_type", "Laptop"),
        catalog_id, data.get("purchase_date"), data.get("warranty_expiry"),
        data.get("condition_notes"), data.get("location", "HQ"),
    ), commit=True)

    # Log stock event
    _log_stock(device_id, catalog_id, "added", data.get("added_by", "system"),
               new_status="Available", notes=f"New device added: {data['brand']} {data['model']}")

    return device_id


def assign_device(device_id: int, employee_name: str) -> bool:
    """Assign device to an employee, set pending acceptance, and notify.
    CRITICAL: blocks assignment unless device status is 'Available'."""
    with Transaction() as cursor:
        # Check if device is available — MUST be 'Available' to assign
        cursor.execute("SELECT * FROM devices WHERE id = %s AND is_deleted = FALSE", (device_id,))
        device = cursor.fetchone()
        if not device:
            return False
        if device["status"] != "Available":
            logger.warning(f"BLOCK: assign attempt on device {device_id} with status '{device['status']}'")
            return False

        # Close previous assignment if any (safety check)
        cursor.execute("""
            UPDATE device_assignments 
            SET returned_date = CURRENT_DATE 
            WHERE device_id = %s AND returned_date IS NULL
        """, (device_id,))

        # Create new assignment with pending acceptance
        cursor.execute("""
            INSERT INTO device_assignments
            (device_id, employee_name, assigned_date, acceptance_status)
            VALUES (%s, %s, CURRENT_DATE, 'pending')
        """, (device_id, employee_name))

        # Update device status
        cursor.execute("UPDATE devices SET status = 'Assigned' WHERE id = %s", (device_id,))

        # Notify employee — device assigned, acceptance required
        device_label = f"{device['brand']} {device['model']}"
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, 'device_assignment')
        """, (
            employee_name,
            "Device Assigned — Action Required",
            f"A {device_label} (SN: {device['serial_number']}) has been assigned "
            f"to you. Please review and accept the device agreement.",
        ))

    # Log stock event (outside transaction — non-critical)
    _log_stock(device_id, device.get("catalog_id"), "assigned", "system",
               old_status="Available", new_status="Assigned",
               notes=f"Assigned to {employee_name}")

    return True


def return_device(device_id: int) -> bool:
    """Mark device as returned and update status to Available."""
    device = execute_single("SELECT id, catalog_id FROM devices WHERE id = %s", (device_id,))

    execute_query("""
        UPDATE device_assignments 
        SET returned_date = CURRENT_DATE,
            acceptance_status = CASE
                WHEN acceptance_status = 'pending' THEN 'rejected'
                ELSE acceptance_status
            END
        WHERE device_id = %s AND returned_date IS NULL
    """, (device_id,), commit=True)
    
    execute_query("UPDATE devices SET status = 'Available' WHERE id = %s", (device_id,), commit=True)

    # Log stock event
    if device:
        _log_stock(device_id, device.get("catalog_id"), "returned", "system",
                   old_status="Assigned", new_status="Available", notes="Device returned")

    return True


def get_device_history(device_id: int) -> dict:
    """Return assignment history (with employee details) and related helpdesk tickets."""
    assignments = execute_query("""
        SELECT da.employee_name, da.assigned_date, da.returned_date,
               da.acceptance_status,
               e.id AS employee_id,
               e.email AS employee_email,
               e.phone AS employee_phone
        FROM device_assignments da
        LEFT JOIN employee e ON da.employee_name = e.name
        WHERE da.device_id = %s 
        ORDER BY da.assigned_date DESC
    """, (device_id,))
    
    for a in assignments:
        for k, v in a.items():
            if hasattr(v, "isoformat"):
                a[k] = v.isoformat()

    tickets = execute_query("""
        SELECT ticket_ref, title, status, employee_name, issue_type, created_at 
        FROM helpdesk_tickets 
        WHERE device_id = %s 
        ORDER BY created_at DESC
    """, (device_id,))
    
    for t in tickets:
        t["created_at"] = t["created_at"].isoformat()

    return {
        "assignments": assignments,
        "tickets": tickets
    }


def add_device_image(device_id: int, image_url: str) -> int:
    """Link an uploaded image URL to a device."""
    return execute_query("INSERT INTO device_images (device_id, image_url) VALUES (%s, %s)", (device_id, image_url), commit=True)


def get_employee_devices(employee_name: str) -> list:
    """Get currently assigned devices for an employee, including acceptance status."""
    rows = execute_query("""
        SELECT d.*, da.id AS assignment_id, da.acceptance_status,
               da.accepted_at, da.assigned_date
        FROM devices d
        JOIN device_assignments da ON d.id = da.device_id
        WHERE da.employee_name = %s AND da.returned_date IS NULL
    """, (employee_name,))
    
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return rows


# ---------------------------------------------------------------------------
# Soft Delete
# ---------------------------------------------------------------------------

def soft_delete_device(device_id: int, deleted_by: str) -> dict:
    """
    Soft-delete a device after validating it is safe to remove.

    Blocks deletion if:
      - Device is currently assigned to an employee
      - Device is under repair
      - Device has open/in-progress helpdesk tickets

    On success:
      - Sets is_deleted=TRUE, records who deleted and when
      - Creates audit log entry
      - Returns summary of the deleted device
    """
    # 1. Fetch device (must exist and not already deleted)
    device = execute_single(
        "SELECT * FROM devices WHERE id = %s AND is_deleted = FALSE",
        (device_id,),
    )
    if not device:
        raise ValueError("Device not found or already deleted.")

    device_label = f"{device['brand']} {device['model']} (SN: {device['serial_number']})"

    # 2. Block if currently assigned
    active_assignment = execute_single("""
        SELECT id, employee_name FROM device_assignments
        WHERE device_id = %s AND returned_date IS NULL
    """, (device_id,))
    if active_assignment:
        raise ValueError(
            f"Cannot delete — device is currently assigned to "
            f"{active_assignment['employee_name']}. "
            f"Please return the device first."
        )

    # 3. Block if under repair
    if device["status"] == "Under Repair":
        raise ValueError(
            "Cannot delete — device is currently under repair. "
            "Please resolve the repair status first."
        )

    # 4. Block if linked to open helpdesk tickets
    open_tickets = execute_single("""
        SELECT COUNT(*) AS cnt FROM helpdesk_tickets
        WHERE device_id = %s AND status IN ('open', 'in_progress')
    """, (device_id,))
    if open_tickets and open_tickets["cnt"] > 0:
        raise ValueError(
            f"Cannot delete — device has {open_tickets['cnt']} open helpdesk "
            f"ticket(s). Please resolve or close them first."
        )

    # 5. All checks passed — soft delete
    old_status = device["status"]
    with Transaction() as cursor:
        cursor.execute("""
            UPDATE devices
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = %s,
                status = 'Retired'
            WHERE id = %s
        """, (deleted_by, device_id))

        # 6. Audit log
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (
                (SELECT id FROM employee WHERE name = %s LIMIT 1),
                %s, %s
            )
        """, (
            deleted_by,
            "asset_deleted",
            f"{deleted_by} soft-deleted device: {device_label} (ID: {device_id})",
        ))

    # Log stock event
    _log_stock(device_id, device.get("catalog_id"), "deleted", deleted_by,
               old_status=old_status, new_status="Retired",
               notes=f"Soft-deleted: {device_label}")

    logger.info("Device soft-deleted: id=%s by=%s label=%s", device_id, deleted_by, device_label)

    return {
        "device_id": device_id,
        "device_label": device_label,
        "deleted_by": deleted_by,
    }
