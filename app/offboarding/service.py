from app.models.database import execute_query, execute_single, Transaction
from app.services.leave_service import get_employee_manager
from app.services.device_service import get_employee_devices, return_device_enterprise
from app.services.offboarding_notification_service import (
    notify_resignation_submitted,
    notify_manager_decision,
    notify_consent_completed,
    notify_assets_cleared,
    notify_it_closure,
    notify_offboarding_completed
)
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Employee Resignation / Exit Request
# ---------------------------------------------------------------------------

def submit_resignation(employee_id, personal_email, personal_phone, resignation_date, proposed_lwd, reason, 
                       reason_notes=None, resignation_doc_path=None, initiator_user_id=None,
                       exit_type='Voluntary Resignation', other_exit_type=None, other_reason=None,
                       handover_required='Yes', handover_to=None, handover_projects=None, handover_notes=None,
                       alternate_phone=None, preferred_communication='Personal Email',
                       post_employment_contact_consent='Yes', supporting_doc_path=None,
                       declarations_confirmed=True):
    if not personal_email or '@' not in personal_email:
        raise ValueError("A valid personal email address is mandatory for post-employment communication.")
    if not personal_phone:
        raise ValueError("Personal contact phone number is required.")
    if not resignation_date or not proposed_lwd:
        raise ValueError("Resignation date and proposed last working day are required.")
    if str(proposed_lwd) < str(resignation_date):
        raise ValueError("Proposed last working day cannot be earlier than resignation date.")
    if not exit_type:
        raise ValueError("Exit type is required.")
    if exit_type == 'Other' and not (other_exit_type and other_exit_type.strip()):
        raise ValueError("Please specify your exit type.")
    if not reason:
        raise ValueError("Primary reason for leaving is required.")
    if reason == 'Other' and not (other_reason and other_reason.strip()):
        raise ValueError("Please specify your reason for leaving.")
    if not declarations_confirmed:
        raise ValueError("All confirmation declarations must be accepted before submitting.")

    # 1. Fetch employee record
    emp = execute_single("SELECT id, name, department, designation, email FROM employee WHERE id = %s", (employee_id,))
    if not emp and initiator_user_id:
        user_row = execute_single("SELECT id, employee_name, email FROM users WHERE id = %s", (initiator_user_id,))
        if user_row:
            emp = execute_single("SELECT id, name, department, designation, email FROM employee WHERE name = %s OR email = %s", (user_row['employee_name'], user_row['email']))
            if not emp:
                from app.models.database import execute_query
                new_emp_id = execute_query("""
                    INSERT INTO employee (name, email, department, designation, status, employment_status)
                    VALUES (%s, %s, 'Engineering', 'Team Member', 'working', 'ACTIVE')
                """, (user_row['employee_name'] or 'Employee', user_row['email']), commit=True)
                emp = execute_single("SELECT id, name, department, designation, email FROM employee WHERE id = %s", (new_emp_id,))
                employee_id = emp['id']

    if not emp:
        raise ValueError("Employee not found.")

    reporting_mgr = get_employee_manager(emp['name'])

    # Resolve users.id for foreign key initiated_by
    if not initiator_user_id:
        user_row = execute_single("SELECT id FROM users WHERE employee_name = %s OR email = %s LIMIT 1", (emp['name'], emp['email']))
        initiator_user_id = user_row['id'] if user_row else employee_id

    # 2. Check for duplicate active exit request
    existing = execute_single(
        "SELECT id, status FROM offboarding_request WHERE employee_id = %s AND status NOT IN ('COMPLETED', 'CANCELLED', 'MANAGER_REJECTED')",
        (employee_id,)
    )
    if existing:
        raise ValueError("An active resignation or offboarding request already exists for this employee.")

    with Transaction() as cursor:
        # Update personal email and phone on employee table
        cursor.execute(
            "UPDATE employee SET personal_email = %s, personal_phone = %s WHERE id = %s",
            (personal_email, personal_phone, employee_id)
        )

        # Insert offboarding request with all corporate fields
        cursor.execute("""
            INSERT INTO offboarding_request (
                employee_id, employee_name, resignation_date, proposed_last_working_day,
                exit_type, other_exit_type, personal_email, personal_phone, alternate_phone,
                preferred_communication, post_employment_contact_consent,
                department, designation, reason, other_reason, reason_notes,
                handover_required, handover_to, handover_projects, handover_notes,
                resignation_doc_path, supporting_doc_path, declarations_confirmed,
                status, initiated_by, initiated_by_name, manager_name, last_working_day
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                'EXIT_REQUESTED', %s, %s, %s, %s
            )
        """, (
            employee_id, emp['name'], resignation_date, proposed_lwd,
            exit_type, other_exit_type, personal_email, personal_phone, alternate_phone,
            preferred_communication, post_employment_contact_consent,
            emp.get('department'), emp.get('designation'), reason, other_reason, reason_notes,
            handover_required, handover_to, handover_projects, handover_notes,
            resignation_doc_path, supporting_doc_path, bool(declarations_confirmed),
            initiator_user_id, emp['name'], reporting_mgr, proposed_lwd
        ))
        offboarding_id = cursor.lastrowid

        # If handover information is provided, seed the KT record
        if handover_required in ('Yes', True, 'true', '1') and (handover_to or handover_projects or handover_notes):
            cursor.execute("""
                INSERT INTO offboarding_knowledge_transfer (
                    offboarding_id, employee_id, replacement_employee_name,
                    pending_responsibilities, remarks, status
                ) VALUES (
                    %s, %s, %s, %s, %s, 'PENDING'
                ) ON DUPLICATE KEY UPDATE
                    replacement_employee_name = VALUES(replacement_employee_name),
                    pending_responsibilities = VALUES(pending_responsibilities),
                    remarks = VALUES(remarks)
            """, (offboarding_id, employee_id, handover_to, handover_projects, handover_notes))

        # Audit log
        performed_by_uid = initiator_user_id
        if not performed_by_uid:
            u = execute_single("SELECT id FROM users WHERE employee_name = %s LIMIT 1", (emp['name'],))
            performed_by_uid = u['id'] if u else None

        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, previous_status, new_value, performed_by, performed_by_name, role, notes)
            VALUES (%s, 'RESIGNATION_SUBMITTED', NULL, 'EXIT_REQUESTED', %s, %s, 'employee', %s)
        """, (offboarding_id, performed_by_uid, emp['name'], f"Resignation submitted. Exit Type: {exit_type}, Proposed LWD: {proposed_lwd}"))

    # Notify parties
    notify_resignation_submitted(offboarding_id, emp['name'], emp.get('reporting_manager'))

    return offboarding_id


def initiate_offboarding_by_hr(employee_id=None, employee_name=None, reason='RESIGNATION',
                               reason_notes=None, last_working_day=None, initiator_user_id=None,
                               initiator_user_name=None):
    if not employee_id and not employee_name:
        raise ValueError("Employee ID or Employee Name is required.")

    emp = None
    if employee_id:
        emp = execute_single("SELECT * FROM employee WHERE id = %s", (employee_id,))
    if not emp and employee_name:
        emp = execute_single("SELECT * FROM employee WHERE name = %s", (employee_name,))

    if not emp:
        raise ValueError("Employee not found.")

    # Check for active case
    existing = execute_single("""
        SELECT * FROM offboarding_request 
        WHERE employee_id = %s AND status NOT IN ('COMPLETED', 'MANAGER_REJECTED')
        ORDER BY id DESC LIMIT 1
    """, (emp['id'],))
    if existing:
        return existing['id']

    personal_email = emp.get('personal_email') or emp.get('email')
    personal_phone = emp.get('personal_phone') or emp.get('phone')
    reporting_mgr = emp.get('reporting_manager') or get_employee_manager(emp['name']) or initiator_user_name or 'Management'
    lwd = last_working_day or str(date.today() + timedelta(days=30))
    resignation_date = date.today().isoformat()

    with Transaction() as cursor:
        cursor.execute("""
            INSERT INTO offboarding_request (
                employee_id, employee_name, resignation_date, proposed_last_working_day,
                personal_email, personal_phone, department, designation, reason,
                reason_notes, status, initiated_by, initiated_by_name,
                manager_id, manager_name, manager_approved_at, last_working_day
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'NOTICE_PERIOD', %s, %s, %s, %s, CURRENT_TIMESTAMP, %s
            )
        """, (
            emp['id'], emp['name'], resignation_date, lwd,
            personal_email, personal_phone, emp.get('department'), emp.get('designation'),
            reason, reason_notes, initiator_user_id, initiator_user_name or 'HR Admin',
            initiator_user_id, initiator_user_name or 'HR Admin', lwd
        ))
        offboarding_id = cursor.lastrowid

        # Update employee employment_status
        cursor.execute("UPDATE employee SET employment_status = 'NOTICE_PERIOD' WHERE id = %s", (emp['id'],))

        # Initial tasks
        cursor.execute("""
            INSERT IGNORE INTO offboarding_consent (offboarding_id, employee_id, status)
            VALUES (%s, %s, 'EMPLOYEE_CONSENT_PENDING')
        """, (offboarding_id, emp['id']))

        cursor.execute("""
            INSERT IGNORE INTO offboarding_knowledge_transfer (offboarding_id, employee_id, status)
            VALUES (%s, %s, 'PENDING')
        """, (offboarding_id, emp['id']))

        default_systems = [
            'Microsoft 365', 'Corporate Email', 'Teams', 'SharePoint',
            'VPN', 'GitHub', 'Power BI', 'Internal Applications'
        ]
        for sys_name in default_systems:
            cursor.execute("""
                INSERT IGNORE INTO offboarding_it_access (
                    offboarding_id, employee_id, system_name, access_status, scheduled_deactivation_date
                ) VALUES (%s, %s, %s, 'SCHEDULED', %s)
            """, (offboarding_id, emp['id'], sys_name, lwd))

        performed_by_uid = initiator_user_id
        if not performed_by_uid:
            u = execute_single("SELECT id FROM users WHERE employee_name = %s LIMIT 1", (initiator_user_name,))
            performed_by_uid = u['id'] if u else None

        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, previous_status, new_value, performed_by, performed_by_name, role, notes)
            VALUES (%s, 'OFFBOARDING_INITIATED_BY_HR', NULL, 'NOTICE_PERIOD', %s, %s, 'hr', %s)
        """, (offboarding_id, performed_by_uid, initiator_user_name or 'HR Admin', f"Offboarding initiated by HR for {emp['name']}. Reason: {reason}"))

    notify_resignation_submitted(offboarding_id, emp['name'], reporting_mgr)
    return offboarding_id


# ---------------------------------------------------------------------------
# Manager Approval / Rejection
# ---------------------------------------------------------------------------

def manager_approval_decision(offboarding_id, manager_id, manager_name, decision, rejection_reason=None):
    if decision not in ('APPROVED', 'REJECTED'):
        raise ValueError("Decision must be APPROVED or REJECTED.")
    if decision == 'REJECTED' and not rejection_reason:
        raise ValueError("Rejection reason is required when rejecting a resignation request.")

    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")
    if req['status'] not in ('EXIT_REQUESTED', 'MANAGER_PENDING'):
        raise ValueError(f"Cannot review request in '{req['status']}' status.")

    with Transaction() as cursor:
        if decision == 'REJECTED':
            cursor.execute("""
                UPDATE offboarding_request 
                SET status = 'MANAGER_REJECTED', rejection_reason = %s, manager_id = %s, manager_name = %s
                WHERE id = %s
            """, (rejection_reason, manager_id, manager_name, offboarding_id))

            cursor.execute("""
                INSERT INTO offboarding_audit_log (offboarding_id, action, previous_status, new_value, performed_by, performed_by_name, role, notes)
                VALUES (%s, 'MANAGER_REJECTED', %s, 'MANAGER_REJECTED', %s, %s, 'manager', %s)
            """, (offboarding_id, req['status'], manager_id, manager_name, rejection_reason))

        else: # APPROVED
            cursor.execute("""
                UPDATE offboarding_request 
                SET status = 'NOTICE_PERIOD', manager_id = %s, manager_name = %s, manager_approved_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (manager_id, manager_name, offboarding_id))

            # Set employee employment_status to NOTICE_PERIOD
            cursor.execute(
                "UPDATE employee SET employment_status = 'NOTICE_PERIOD' WHERE id = %s",
                (req['employee_id'],)
            )

            # Create initial tasks
            # 1. Consent task
            cursor.execute("""
                INSERT IGNORE INTO offboarding_consent (offboarding_id, employee_id, status)
                VALUES (%s, %s, 'EMPLOYEE_CONSENT_PENDING')
            """, (offboarding_id, req['employee_id']))

            # 2. Knowledge Transfer task
            cursor.execute("""
                INSERT IGNORE INTO offboarding_knowledge_transfer (offboarding_id, employee_id, status)
                VALUES (%s, %s, 'PENDING')
            """, (offboarding_id, req['employee_id']))

            # 3. IT Access Systems task
            default_systems = [
                'Microsoft 365', 'Corporate Email', 'Teams', 'SharePoint',
                'VPN', 'GitHub', 'Power BI', 'Internal Applications'
            ]
            for sys_name in default_systems:
                cursor.execute("""
                    INSERT IGNORE INTO offboarding_it_access (
                        offboarding_id, employee_id, system_name, access_status, scheduled_deactivation_date
                    ) VALUES (%s, %s, %s, 'SCHEDULED', %s)
                """, (offboarding_id, req['employee_id'], sys_name, req['proposed_last_working_day']))

            cursor.execute("""
                INSERT INTO offboarding_audit_log (offboarding_id, action, previous_status, new_value, performed_by, performed_by_name, role, notes)
                VALUES (%s, 'MANAGER_APPROVED', %s, 'NOTICE_PERIOD', %s, %s, 'manager', 'Resignation approved. Notice period started.')
            """, (offboarding_id, req['status'], manager_id, manager_name))

    notify_manager_decision(offboarding_id, req['employee_name'], decision, rejection_reason, manager_name)


# ---------------------------------------------------------------------------
# Employee Consent
# ---------------------------------------------------------------------------

def submit_employee_consent(offboarding_id, employee_id, consent_data, ip_address=None):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")
    if req['employee_id'] != employee_id:
        raise ValueError("Unauthorized to complete consent for this offboarding case.")

    signature_text = consent_data.get('signature_text') or req['employee_name']

    with Transaction() as cursor:
        cursor.execute("""
            INSERT INTO offboarding_consent (
                offboarding_id, employee_id, resignation_confirmed, last_working_day_confirmed,
                asset_return_acknowledged, confidential_info_acknowledged, data_handling_acknowledged,
                access_termination_acknowledged, final_clearance_acknowledged, status,
                signature_text, ip_address, submitted_at
            ) VALUES (
                %s, %s, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 'CONSENT_COMPLETED',
                %s, %s, CURRENT_TIMESTAMP
            ) ON DUPLICATE KEY UPDATE
                resignation_confirmed = TRUE,
                last_working_day_confirmed = TRUE,
                asset_return_acknowledged = TRUE,
                confidential_info_acknowledged = TRUE,
                data_handling_acknowledged = TRUE,
                access_termination_acknowledged = TRUE,
                final_clearance_acknowledged = TRUE,
                status = 'CONSENT_COMPLETED',
                signature_text = VALUES(signature_text),
                ip_address = VALUES(ip_address),
                submitted_at = CURRENT_TIMESTAMP
        """, (offboarding_id, employee_id, signature_text, ip_address))

        u = execute_single("SELECT id FROM users WHERE employee_name = %s LIMIT 1", (req['employee_name'],))
        u_id = u['id'] if u else None
        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by, performed_by_name, role, notes)
            VALUES (%s, 'CONSENT_COMPLETED', 'CONSENT_COMPLETED', %s, %s, 'employee', 'Employee submitted offboarding consent')
        """, (offboarding_id, u_id, req['employee_name']))

    notify_consent_completed(offboarding_id, req['employee_name'], req.get('manager_name'))


# ---------------------------------------------------------------------------
# Knowledge Transfer
# ---------------------------------------------------------------------------

def update_knowledge_transfer(offboarding_id, updated_by_name, kt_data):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")

    replacement_id = kt_data.get('replacement_employee_id')
    replacement_name = kt_data.get('replacement_employee_name')
    pending_resp = kt_data.get('pending_responsibilities')
    docs_transferred = kt_data.get('documents_transferred')
    remarks = kt_data.get('remarks')
    status = kt_data.get('status', 'IN_PROGRESS')
    completed_date = date.today().isoformat() if status == 'COMPLETED' else None

    with Transaction() as cursor:
        cursor.execute("""
            INSERT INTO offboarding_knowledge_transfer (
                offboarding_id, employee_id, replacement_employee_id, replacement_employee_name,
                pending_responsibilities, documents_transferred, remarks, status, completed_date, updated_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON DUPLICATE KEY UPDATE
                replacement_employee_id = VALUES(replacement_employee_id),
                replacement_employee_name = VALUES(replacement_employee_name),
                pending_responsibilities = VALUES(pending_responsibilities),
                documents_transferred = VALUES(documents_transferred),
                remarks = VALUES(remarks),
                status = VALUES(status),
                completed_date = VALUES(completed_date),
                updated_by = VALUES(updated_by)
        """, (
            offboarding_id, req['employee_id'], replacement_id, replacement_name,
            pending_resp, docs_transferred, remarks, status, completed_date, updated_by_name
        ))

        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by_name, notes)
            VALUES (%s, 'KNOWLEDGE_TRANSFER_UPDATE', %s, %s, %s)
        """, (offboarding_id, status, updated_by_name, f"KT status: {status}"))


# ---------------------------------------------------------------------------
# Asset Return Integration
# ---------------------------------------------------------------------------

def get_offboarding_assets(offboarding_id):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")
    
    # Retrieve assigned devices using existing device_service
    devices = get_employee_devices(req['employee_name'])
    return devices

def return_offboarding_asset(offboarding_id, device_id, return_status, condition=None, remarks=None, user_name="HR"):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")

    if return_status in ('Returned', 'RETURNED'):
        # Reuse enterprise-grade device return function from device_service
        return_device_enterprise(
            device_id=device_id,
            returned_by=user_name,
            return_reason=f"Offboarding Case #{offboarding_id} return: {remarks or 'Asset cleared'}"
        )
    else:
        # Update condition notes if damaged/lost/pending
        with Transaction() as cursor:
            cursor.execute(
                "UPDATE devices SET condition_notes = CONCAT(COALESCE(condition_notes, ''), ' | ', %s) WHERE id = %s",
                (f"Offboarding condition: {condition or return_status}. Remarks: {remarks or ''}", device_id)
            )

    with Transaction() as cursor:
        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by_name, notes)
            VALUES (%s, 'ASSET_RETURNED', %s, %s, %s)
        """, (offboarding_id, f"Device {device_id}: {return_status}", user_name, remarks or condition))

    # Check if any remaining devices
    remaining = get_employee_devices(req['employee_name'])
    if not remaining:
        notify_assets_cleared(offboarding_id, req['employee_name'])

    return {"success": True, "remaining_devices": len(remaining)}


# ---------------------------------------------------------------------------
# System Admin: System Access & Deactivation
# ---------------------------------------------------------------------------

def get_it_access_details(offboarding_id):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")

    systems = execute_query("SELECT * FROM offboarding_it_access WHERE offboarding_id = %s", (offboarding_id,))
    actions = execute_single("SELECT * FROM offboarding_it_actions WHERE offboarding_id = %s", (offboarding_id,))
    
    # Corporate account active status in users table
    u = execute_single("SELECT is_active FROM users WHERE employee_name = %s LIMIT 1", (req['employee_name'],))
    account_active = bool(u.get('is_active')) if u else False

    return {
        "request": req,
        "systems": systems,
        "actions": actions,
        "corporate_account_active": account_active
    }

def update_it_system_status(offboarding_id, system_name, access_status, notes=None, user_name="System Admin"):
    with Transaction() as cursor:
        revoked_at = "CURRENT_TIMESTAMP" if access_status == 'REVOKED' else "NULL"
        cursor.execute(f"""
            UPDATE offboarding_it_access
            SET access_status = %s, notes = %s,
                revoked_at = {revoked_at},
                revoked_by = CASE WHEN %s = 'REVOKED' THEN %s ELSE revoked_by END
            WHERE offboarding_id = %s AND system_name = %s
        """, (access_status, notes, access_status, user_name, offboarding_id, system_name))

        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by_name, role, notes)
            VALUES (%s, 'IT_SYSTEM_STATUS_CHANGE', %s, %s, 'system_admin', %s)
        """, (offboarding_id, f"{system_name}: {access_status}", user_name, notes))

def perform_it_deactivation(offboarding_id, user_name, actions_dict, notes=None):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")

    with Transaction() as cursor:
        # 1. Record IT actions checklist
        cursor.execute("""
            INSERT INTO offboarding_it_actions (
                offboarding_id, corporate_account_disabled, corporate_email_disabled,
                application_access_revoked, vpn_access_revoked, github_access_revoked,
                groups_removed, sessions_revoked, licenses_removed,
                deactivated_by, deactivated_at, notes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s
            ) ON DUPLICATE KEY UPDATE
                corporate_account_disabled = VALUES(corporate_account_disabled),
                corporate_email_disabled = VALUES(corporate_email_disabled),
                application_access_revoked = VALUES(application_access_revoked),
                vpn_access_revoked = VALUES(vpn_access_revoked),
                github_access_revoked = VALUES(github_access_revoked),
                groups_removed = VALUES(groups_removed),
                sessions_revoked = VALUES(sessions_revoked),
                licenses_removed = VALUES(licenses_removed),
                deactivated_by = VALUES(deactivated_by),
                deactivated_at = CURRENT_TIMESTAMP,
                notes = VALUES(notes)
        """, (
            offboarding_id,
            bool(actions_dict.get('corporate_account_disabled', True)),
            bool(actions_dict.get('corporate_email_disabled', True)),
            bool(actions_dict.get('application_access_revoked', True)),
            bool(actions_dict.get('vpn_access_revoked', True)),
            bool(actions_dict.get('github_access_revoked', True)),
            bool(actions_dict.get('groups_removed', True)),
            bool(actions_dict.get('sessions_revoked', True)),
            bool(actions_dict.get('licenses_removed', True)),
            user_name, notes
        ))

        # 2. Mark all IT access items as REVOKED
        cursor.execute("""
            UPDATE offboarding_it_access 
            SET access_status = 'REVOKED', revoked_at = CURRENT_TIMESTAMP, revoked_by = %s
            WHERE offboarding_id = %s
        """, (user_name, offboarding_id))

        # 3. Disable Corporate Account in users table
        cursor.execute("""
            UPDATE users SET is_active = FALSE WHERE employee_name = %s
        """, (req['employee_name'],))

        # 4. Update offboarding request
        cursor.execute("""
            UPDATE offboarding_request 
            SET it_cleared_by = %s, it_cleared_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_name, offboarding_id))

        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by_name, role, notes)
            VALUES (%s, 'IT_ACCESS_DEACTIVATION', 'REVOKED', %s, 'system_admin', 'Corporate account disabled and all system accesses revoked')
        """, (offboarding_id, user_name))

    notify_it_closure(offboarding_id, req['employee_name'], req.get('personal_email'))


# ---------------------------------------------------------------------------
# HR Final Clearance & Completion
# ---------------------------------------------------------------------------

def complete_hr_final_clearance(offboarding_id, hr_name):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        raise ValueError("Offboarding request not found.")
    if req['status'] == 'COMPLETED':
        raise ValueError("This offboarding case is already completed.")

    # Validation of mandatory tasks
    errors = []
    
    # Check Consent
    consent = execute_single("SELECT status FROM offboarding_consent WHERE offboarding_id = %s", (offboarding_id,))
    if not consent or consent['status'] != 'CONSENT_COMPLETED':
        errors.append("Employee offboarding consent is pending.")

    # Check Assets
    devices = get_employee_devices(req['employee_name'])
    if devices:
        errors.append(f"{len(devices)} assigned device(s) have not been returned.")

    # Check IT access closure
    if not req.get('it_cleared_at'):
        # Check if corporate account is deactivated
        u = execute_single("SELECT is_active FROM users WHERE employee_name = %s", (req['employee_name'],))
        if u and u.get('is_active') is True:
            errors.append("System Admin IT access closure and corporate account deactivation is pending.")

    if errors:
        raise ValueError("Cannot complete offboarding. Incomplete mandatory tasks: " + "; ".join(errors))

    with Transaction() as cursor:
        cursor.execute("""
            UPDATE offboarding_request 
            SET status = 'COMPLETED', hr_cleared_by = %s, hr_cleared_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (hr_name, offboarding_id))

        # Update employee employment_status to OFFBOARDED
        cursor.execute(
            "UPDATE employee SET employment_status = 'OFFBOARDED' WHERE id = %s",
            (req['employee_id'],)
        )

        # Confirm users is_active = FALSE
        cursor.execute("UPDATE users SET is_active = FALSE WHERE employee_name = %s", (req['employee_name'],))

        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, previous_status, new_value, performed_by_name, role, notes)
            VALUES (%s, 'OFFBOARDING_COMPLETED', %s, 'COMPLETED', %s, 'hr', 'Final HR clearance approved. Employee offboarded.')
        """, (offboarding_id, req['status'], hr_name))

    notify_offboarding_completed(offboarding_id, req['employee_name'], req.get('manager_name'), req.get('personal_email'))


# ---------------------------------------------------------------------------
# Case Queries & Metrics
# ---------------------------------------------------------------------------

def get_offboarding_case_details(offboarding_id):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        return None

    consent = execute_single("SELECT * FROM offboarding_consent WHERE offboarding_id = %s", (offboarding_id,))
    kt = execute_single("SELECT * FROM offboarding_knowledge_transfer WHERE offboarding_id = %s", (offboarding_id,))
    it_systems = execute_query("SELECT * FROM offboarding_it_access WHERE offboarding_id = %s", (offboarding_id,))
    it_actions = execute_single("SELECT * FROM offboarding_it_actions WHERE offboarding_id = %s", (offboarding_id,))
    audit = execute_query("SELECT * FROM offboarding_audit_log WHERE offboarding_id = %s ORDER BY performed_at DESC", (offboarding_id,))
    assigned_assets = get_employee_devices(req['employee_name'])

    # Determine current stage
    current_stage = "MANAGER APPROVAL"
    if req['status'] == 'MANAGER_REJECTED':
        current_stage = "REJECTED"
    elif req['status'] == 'COMPLETED':
        current_stage = "COMPLETED"
    elif not req.get('it_cleared_at'):
        if consent and consent.get('status') == 'CONSENT_COMPLETED' and not assigned_assets:
            current_stage = "IT CLOSURE"
        else:
            current_stage = "NOTICE PERIOD"
    else:
        current_stage = "HR CLEARANCE"

    return {
        "request": req,
        "consent": consent,
        "knowledge_transfer": kt,
        "it_systems": it_systems,
        "it_actions": it_actions,
        "assigned_assets": assigned_assets,
        "audit": audit,
        "current_stage": current_stage
    }

def get_offboarding_cases(user_role, user_id, user_name):
    if user_role in ('hr', 'admin', 'superadmin'):
        cases = execute_query("SELECT * FROM offboarding_request ORDER BY created_at DESC")
    elif user_role == 'system_admin':
        cases = execute_query("""
            SELECT * FROM offboarding_request 
            WHERE status NOT IN ('MANAGER_REJECTED', 'CANCELLED')
            ORDER BY created_at DESC
        """)
    elif user_role == 'manager':
        cases = execute_query("""
            SELECT * FROM offboarding_request 
            WHERE manager_name = %s OR manager_id = %s
            ORDER BY created_at DESC
        """, (user_name, user_id))
    else:
        # Employee
        cases = execute_query("""
            SELECT * FROM offboarding_request 
            WHERE employee_name = %s OR employee_id = %s
            ORDER BY created_at DESC
        """, (user_name, user_id))

    # Enrich with stage
    for c in cases:
        if c['status'] == 'COMPLETED':
            c['current_stage'] = 'COMPLETED'
        elif c['status'] == 'MANAGER_REJECTED':
            c['current_stage'] = 'REJECTED'
        elif c['status'] in ('EXIT_REQUESTED', 'MANAGER_PENDING'):
            c['current_stage'] = 'MANAGER APPROVAL'
        elif not c.get('it_cleared_at'):
            c['current_stage'] = 'NOTICE PERIOD'
        else:
            c['current_stage'] = 'HR CLEARANCE'

    return cases

def get_hr_dashboard_metrics():
    cases = execute_query("SELECT * FROM offboarding_request")
    
    pending_exit = sum(1 for c in cases if c['status'] in ('EXIT_REQUESTED', 'MANAGER_PENDING'))
    notice_period = sum(1 for c in cases if c['status'] == 'NOTICE_PERIOD')
    completed = sum(1 for c in cases if c['status'] == 'COMPLETED')
    
    # Upcoming Last Working Days (within 14 days)
    today = date.today()
    upcoming_lwd = 0
    for c in cases:
        if c.get('proposed_last_working_day') and c['status'] not in ('COMPLETED', 'CANCELLED', 'MANAGER_REJECTED'):
            try:
                lwd = c['proposed_last_working_day']
                if isinstance(lwd, str):
                    lwd = datetime.strptime(lwd, '%Y-%m-%d').date()
                if 0 <= (lwd - today).days <= 14:
                    upcoming_lwd += 1
            except Exception:
                pass

    pending_consent = execute_single("""
        SELECT COUNT(*) AS count FROM offboarding_consent c
        JOIN offboarding_request r ON c.offboarding_id = r.id
        WHERE c.status = 'EMPLOYEE_CONSENT_PENDING' AND r.status NOT IN ('COMPLETED', 'CANCELLED', 'MANAGER_REJECTED')
    """)['count']

    pending_it = sum(1 for c in cases if c['status'] not in ('COMPLETED', 'CANCELLED', 'MANAGER_REJECTED') and not c.get('it_cleared_at'))
    pending_hr = sum(1 for c in cases if c['status'] not in ('COMPLETED', 'CANCELLED', 'MANAGER_REJECTED') and c.get('it_cleared_at'))

    return {
        "pending_exit_requests": pending_exit,
        "in_notice_period": notice_period,
        "upcoming_last_working_days": upcoming_lwd,
        "pending_consent": pending_consent,
        "pending_it_closure": pending_it,
        "pending_hr_clearance": pending_hr,
        "completed": completed
    }
