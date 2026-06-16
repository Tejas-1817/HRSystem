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
        INSERT INTO devices (brand, model, serial_number, asset_id, status, device_type,
                             catalog_id, purchase_date, warranty_expiry, condition_notes, location,
                             processor, ram, storage)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data["brand"], data["model"], data["serial_number"], data.get("asset_id"),
        data.get("status", "Available"), data.get("device_type", "Laptop"),
        catalog_id, data.get("purchase_date"), data.get("warranty_expiry"),
        data.get("condition_notes"), data.get("location", "HQ"),
        data.get("processor"), data.get("ram"), data.get("storage"),
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


def return_device_enterprise(
    device_id: int,
    returned_by: str,
    return_reason: str = None,
    ip_address: str = None,
    user_agent: str = None,
) -> dict:
    """
    Enterprise-grade Return Asset workflow.

    Performs all steps inside a single database transaction with automatic
    rollback on failure. Preserves full assignment history and creates
    audit + notification records for compliance.

    Parameters
    ----------
    device_id : int
        Primary key of the device to return.
    returned_by : str
        employee_name of the HR/Admin performing the return.
    return_reason : str, optional
        Reason for the return (e.g. "End of employment", "Device upgrade").
    ip_address : str, optional
        IP address of the requester (for audit trail).
    user_agent : str, optional
        User-Agent header of the requester (for audit trail).

    Returns
    -------
    dict
        Structured result with device_id, asset_status, returned_by, etc.

    Raises
    ------
    LookupError
        If device does not exist (404) or is not in 'Assigned' status (409).
    ValueError
        If required parameters are invalid.
    """
    with Transaction() as cursor:
        # ── Step 1: Validate device exists ──────────────────────────────
        cursor.execute(
            "SELECT * FROM devices WHERE id = %s AND is_deleted = FALSE",
            (device_id,),
        )
        device = cursor.fetchone()
        if not device:
            raise LookupError("Device not found.")

        device_label = f"{device['brand']} {device['model']} (SN: {device['serial_number']})"

        # ── Step 2: Validate device is currently Assigned ───────────────
        if device["status"] != "Assigned":
            if device["status"] == "Available":
                raise LookupError("CONFLICT:Asset is already available and not assigned to anyone.")
            raise LookupError(
                f"CONFLICT:Asset cannot be returned — current status is '{device['status']}'."
            )

        # ── Step 3: Find the active assignment ──────────────────────────
        cursor.execute("""
            SELECT da.*, e.id AS employee_pk
            FROM device_assignments da
            LEFT JOIN employee e ON da.employee_name = e.name
            WHERE da.device_id = %s AND da.returned_date IS NULL
            ORDER BY da.assigned_date DESC
            LIMIT 1
        """, (device_id,))
        assignment = cursor.fetchone()

        assigned_employee = assignment["employee_name"] if assignment else "Unknown"
        employee_pk = assignment["employee_pk"] if assignment else None

        # ── Step 4: Archive assignment (never delete) ───────────────────
        if assignment:
            cursor.execute("""
                UPDATE device_assignments
                SET returned_date  = CURRENT_DATE,
                    returned_by    = %s,
                    return_reason  = %s,
                    acceptance_status = CASE
                        WHEN acceptance_status = 'pending' THEN 'rejected'
                        ELSE acceptance_status
                    END
                WHERE id = %s
            """, (returned_by, return_reason, assignment["id"]))

        # ── Step 5: Update device status to Available ───────────────────
        cursor.execute(
            "UPDATE devices SET status = 'Available', updated_at = NOW() WHERE id = %s",
            (device_id,),
        )

        # ── Step 6: Audit log with request metadata ─────────────────────
        # Resolve the HR/Admin employee PK for the audit log
        cursor.execute(
            "SELECT id FROM employee WHERE name = %s LIMIT 1",
            (returned_by,),
        )
        performer = cursor.fetchone()
        performer_id = performer["id"] if performer else 0

        reason_text = f" Reason: {return_reason}" if return_reason else ""
        cursor.execute("""
            INSERT INTO audit_logs
                (user_id, event_type, description, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            performer_id,
            "ASSET_RETURNED",
            f"{returned_by} returned device {device_label} "
            f"from {assigned_employee}.{reason_text}",
            ip_address,
            user_agent,
        ))

        # ── Step 7: Notify the employee ─────────────────────────────────
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            VALUES (%s, %s, %s, 'device_return')
        """, (
            assigned_employee,
            "Device Returned",
            f"Your {device_label} has been returned by {returned_by}. "
            f"The device has been removed from your profile.{reason_text}",
        ))

        # ── Step 8: Notify all HR/Admin users ───────────────────────────
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            SELECT DISTINCT u.employee_name, %s, %s, 'device_return'
            FROM users u
            WHERE u.role IN ('hr', 'admin')
              AND u.employee_name != %s
        """, (
            "Asset Return Processed",
            f"{returned_by} has returned {device_label} "
            f"(previously assigned to {assigned_employee}).{reason_text}",
            returned_by,
        ))

    # ── Step 9: Log stock event (non-critical, outside transaction) ─────
    _log_stock(
        device_id, device.get("catalog_id"), "returned", returned_by,
        old_status="Assigned", new_status="Available",
        notes=f"Returned from {assigned_employee}. {reason_text}".strip(),
    )

    logger.info(
        "ASSET_RETURNED: device_id=%s label=%s from=%s by=%s reason=%s",
        device_id, device_label, assigned_employee, returned_by, return_reason,
    )

    return {
        "device_id": device_id,
        "device_label": device_label,
        "asset_status": "AVAILABLE",
        "available_for_assignment": True,
        "returned_by": returned_by,
        "returned_from": assigned_employee,
        "returned_at": datetime.now().strftime("%Y-%m-%d"),
        "return_reason": return_reason,
    }


def return_device(device_id: int) -> bool:
    """
    Legacy wrapper — kept for backward compatibility.

    Delegates to the enterprise return workflow with minimal defaults.
    Returns True on success for callers expecting the old boolean API.
    """
    try:
        return_device_enterprise(device_id, returned_by="system")
        return True
    except (LookupError, ValueError):
        return False


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
