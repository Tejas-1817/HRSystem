"""
Device Agreement Service — business logic for the acceptance workflow.

Handles agreement rendering, digital signature storage, acceptance/rejection,
and audit trail creation.
"""

import os
import logging
from datetime import datetime

from app.models.database import execute_query, execute_single, Transaction
from app.utils.agreement_template import render_agreement, AGREEMENT_VERSION
from app.utils.file_upload import save_upload, ALLOWED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agreement Rendering
# ---------------------------------------------------------------------------

def get_pending_agreement(device_id: int, employee_name: str) -> dict | None:
    """
    Fetch the pending assignment for a device+employee pair and render the
    personalised agreement text.

    Returns None if no pending assignment exists.
    """
    # 1. Find the pending assignment for this device + employee
    assignment = execute_single("""
        SELECT da.id AS assignment_id, da.device_id, da.employee_name,
               da.assigned_date, da.acceptance_status,
               d.brand, d.model, d.serial_number, d.device_type
        FROM device_assignments da
        JOIN devices d ON da.device_id = d.id
        WHERE da.device_id = %s
          AND da.employee_name = %s
          AND da.returned_date IS NULL
          AND da.acceptance_status = 'pending'
        ORDER BY da.assigned_date DESC
        LIMIT 1
    """, (device_id, employee_name))

    if not assignment:
        return None

    # 2. Get employee ID from employee table
    emp = execute_single(
        "SELECT id FROM employee WHERE name = %s", (employee_name,)
    )
    employee_id = emp["id"] if emp else "N/A"

    # 3. Render agreement
    assigned_date = str(assignment["assigned_date"])
    agreement_text = render_agreement(
        employee_name=employee_name,
        employee_id=employee_id,
        device={
            "brand": assignment["brand"],
            "model": assignment["model"],
            "serial_number": assignment["serial_number"],
            "device_type": assignment["device_type"],
        },
        assigned_date=assigned_date,
    )

    return {
        "assignment_id": assignment["assignment_id"],
        "device_id": assignment["device_id"],
        "employee_name": employee_name,
        "employee_id": employee_id,
        "device": {
            "brand": assignment["brand"],
            "model": assignment["model"],
            "serial_number": assignment["serial_number"],
            "device_type": assignment["device_type"],
        },
        "assigned_date": assigned_date,
        "agreement_text": agreement_text,
        "agreement_version": AGREEMENT_VERSION,
    }


# ---------------------------------------------------------------------------
# Accept Agreement
# ---------------------------------------------------------------------------

def accept_agreement(
    assignment_id: int,
    employee_name: str,
    signature_file,
    ip_address: str = None,
) -> dict:
    """
    Process acceptance of a device agreement.

    1. Validate the assignment belongs to the employee and is pending.
    2. Save the digital signature image.
    3. Update device_assignments status → 'accepted'.
    4. Create immutable device_agreements record.
    5. Notify HR.
    6. Audit log.
    """
    with Transaction() as cursor:
        # 1. Validate assignment
        cursor.execute("""
            SELECT da.*, d.brand, d.model, d.serial_number, d.device_type
            FROM device_assignments da
            JOIN devices d ON da.device_id = d.id
            WHERE da.id = %s AND da.employee_name = %s
        """, (assignment_id, employee_name))
        assignment = cursor.fetchone()

        if not assignment:
            raise ValueError("Assignment not found or does not belong to you.")
        if assignment["acceptance_status"] != "pending":
            raise ValueError(
                f"Assignment already {assignment['acceptance_status']}. Cannot accept again."
            )

        # 2. Save signature image
        signature_url = save_upload(
            signature_file, folder="signatures", allowed=ALLOWED_IMAGE_EXTENSIONS
        )

        # 3. Get employee ID
        cursor.execute("SELECT id FROM employee WHERE name = %s", (employee_name,))
        emp = cursor.fetchone()
        employee_id = emp["id"] if emp else None

        # 4. Render agreement text (snapshot for immutable storage)
        assigned_date = str(assignment["assigned_date"])
        agreement_text = render_agreement(
            employee_name=employee_name,
            employee_id=employee_id or "N/A",
            device={
                "brand": assignment["brand"],
                "model": assignment["model"],
                "serial_number": assignment["serial_number"],
                "device_type": assignment["device_type"],
            },
            assigned_date=assigned_date,
        )

        # 5. Update assignment status
        now = datetime.now()
        cursor.execute("""
            UPDATE device_assignments
            SET acceptance_status = 'accepted',
                accepted_at = %s,
                signature_url = %s
            WHERE id = %s
        """, (now, signature_url, assignment_id))

        # 6. Create immutable agreement record
        cursor.execute("""
            INSERT INTO device_agreements
            (assignment_id, employee_name, device_id, agreement_text,
             agreement_version, signature_url, accepted_at, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            assignment_id, employee_name, assignment["device_id"],
            agreement_text, AGREEMENT_VERSION, signature_url, now,
            ip_address,
        ))

        # 7. Notify HR — device accepted
        device_label = f"{assignment['brand']} {assignment['model']}"
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            SELECT DISTINCT u.employee_name, %s, %s, 'device_acceptance'
            FROM users u WHERE u.role IN ('hr', 'admin')
        """, (
            "Device Agreement Accepted",
            f"{employee_name} has accepted the {device_label} "
            f"(SN: {assignment['serial_number']}) assignment.",
        ))

        # 8. Audit log
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (
            employee_id or 0,
            "device_agreement_accepted",
            f"{employee_name} accepted {device_label} (Assignment #{assignment_id})",
        ))

    logger.info(
        "Agreement accepted: employee=%s assignment=%s device=%s",
        employee_name, assignment_id, assignment["device_id"],
    )

    return {
        "assignment_id": assignment_id,
        "acceptance_status": "accepted",
        "accepted_at": now.isoformat(),
        "signature_url": signature_url,
    }


# ---------------------------------------------------------------------------
# Reject Agreement
# ---------------------------------------------------------------------------

def reject_agreement(
    assignment_id: int,
    employee_name: str,
    reason: str = None,
) -> dict:
    """
    Process rejection of a device agreement.

    1. Validate the assignment belongs to the employee and is pending.
    2. Update device_assignments status → 'rejected'.
    3. Return device to 'Available'.
    4. Notify HR.
    5. Audit log.
    """
    with Transaction() as cursor:
        # 1. Validate
        cursor.execute("""
            SELECT da.*, d.brand, d.model, d.serial_number
            FROM device_assignments da
            JOIN devices d ON da.device_id = d.id
            WHERE da.id = %s AND da.employee_name = %s
        """, (assignment_id, employee_name))
        assignment = cursor.fetchone()

        if not assignment:
            raise ValueError("Assignment not found or does not belong to you.")
        if assignment["acceptance_status"] != "pending":
            raise ValueError(
                f"Assignment already {assignment['acceptance_status']}. Cannot reject."
            )

        # 2. Update assignment
        cursor.execute("""
            UPDATE device_assignments
            SET acceptance_status = 'rejected',
                rejection_reason = %s,
                returned_date = CURRENT_DATE
            WHERE id = %s
        """, (reason, assignment_id))

        # 3. Return device to available
        cursor.execute(
            "UPDATE devices SET status = 'Available' WHERE id = %s",
            (assignment["device_id"],),
        )

        # 4. Get employee ID for audit
        cursor.execute("SELECT id FROM employee WHERE name = %s", (employee_name,))
        emp = cursor.fetchone()
        employee_id = emp["id"] if emp else 0

        # 5. Notify HR
        device_label = f"{assignment['brand']} {assignment['model']}"
        reason_text = f" Reason: {reason}" if reason else ""
        cursor.execute("""
            INSERT INTO notifications (employee_name, title, message, type)
            SELECT DISTINCT u.employee_name, %s, %s, 'device_acceptance'
            FROM users u WHERE u.role IN ('hr', 'admin')
        """, (
            "Device Agreement Rejected",
            f"{employee_name} has rejected the {device_label} "
            f"(SN: {assignment['serial_number']}) assignment.{reason_text}",
        ))

        # 6. Audit log
        cursor.execute("""
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
        """, (
            employee_id,
            "device_agreement_rejected",
            f"{employee_name} rejected {device_label} (Assignment #{assignment_id}).{reason_text}",
        ))

    logger.info(
        "Agreement rejected: employee=%s assignment=%s reason=%s",
        employee_name, assignment_id, reason,
    )

    return {
        "assignment_id": assignment_id,
        "acceptance_status": "rejected",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_agreement_record(assignment_id: int) -> dict | None:
    """Fetch the signed agreement record for an assignment."""
    record = execute_single("""
        SELECT dag.*, d.brand, d.model, d.serial_number, d.device_type
        FROM device_agreements dag
        JOIN devices d ON dag.device_id = d.id
        WHERE dag.assignment_id = %s
    """, (assignment_id,))

    if record:
        for k, v in record.items():
            if hasattr(v, "isoformat"):
                record[k] = v.isoformat()
    return record


def get_acceptance_status(device_id: int) -> dict:
    """
    Get the current acceptance status for a device's active assignment.
    Returns assignment details + signed agreement if accepted.
    """
    assignment = execute_single("""
        SELECT da.id AS assignment_id, da.employee_name, da.assigned_date,
               da.acceptance_status, da.accepted_at, da.signature_url,
               da.rejection_reason,
               d.brand, d.model, d.serial_number, d.device_type
        FROM device_assignments da
        JOIN devices d ON da.device_id = d.id
        WHERE da.device_id = %s AND da.returned_date IS NULL
        ORDER BY da.assigned_date DESC
        LIMIT 1
    """, (device_id,))

    if not assignment:
        return {"assigned": False}

    for k, v in assignment.items():
        if hasattr(v, "isoformat"):
            assignment[k] = v.isoformat()

    result = {"assigned": True, **assignment}

    # If accepted, include the signed agreement record
    if assignment["acceptance_status"] == "accepted":
        agreement = get_agreement_record(assignment["assignment_id"])
        if agreement:
            result["agreement"] = agreement

    return result
