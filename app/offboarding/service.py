from app.models.database import Transaction, execute_query, execute_single
from app.services.leave_service import get_employee_manager
from app.services.device_service import get_employee_devices
from app.services.offboarding_notification_service import (
    notify_approvers_offboarding_initiated,
    notify_hr_approval_decision,
    notify_offboarding_completed
)

def _get_active_users_by_role(role):
    users = execute_query("SELECT id FROM users WHERE role = %s AND (is_active IS NULL OR is_active = TRUE)", (role,))
    return [u['id'] for u in users]

def initiate_offboarding(employee_id, employee_name, reason, reason_notes, last_working_day, initiator_id, initiator_name):
    with Transaction() as cursor:
        # Check if active request already exists
        cursor.execute("SELECT id FROM offboarding_request WHERE employee_id = %s AND status IN ('INITIATED', 'IN_PROGRESS')", (employee_id,))
        if cursor.fetchone():
            raise ValueError("An active offboarding request already exists for this employee.")
            
        # Create request
        cursor.execute("""
            INSERT INTO offboarding_request (employee_id, employee_name, initiated_by, initiated_by_name, reason, reason_notes, last_working_day)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (employee_id, employee_name, initiator_id, initiator_name, reason, reason_notes, last_working_day))
        
        offboarding_id = cursor.lastrowid
        
        # Create checklist items
        checklist_items = [
            ('ASSETS_RETURNED', True),
            ('EMAIL_ACCESS_REMOVED', False),
            ('SYSTEM_ACCESS_REMOVED', False),
            ('MS_TEAMS_ACCESS_REMOVED', False)
        ]
        for item_type, is_auto in checklist_items:
            cursor.execute("""
                INSERT INTO offboarding_checklist_item (offboarding_id, item_type, is_auto_tracked)
                VALUES (%s, %s, %s)
            """, (offboarding_id, item_type, is_auto))
            
        # Create approvals
        for approver_role in ['hr', 'manager', 'accounts']:
            cursor.execute("""
                INSERT INTO offboarding_approval (offboarding_id, approver_role)
                VALUES (%s, %s)
            """, (offboarding_id, approver_role))
            
        # Audit log
        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, performed_by, performed_by_name, notes)
            VALUES (%s, 'INITIATED', %s, %s, 'Offboarding initiated')
        """, (offboarding_id, initiator_id, initiator_name))
        
        # Resolve manager and notify
        manager_name = get_employee_manager(employee_name)
        manager_id = None
        if manager_name:
            manager_record = execute_single("SELECT id FROM users WHERE employee_name = %s", (manager_name,))
            if manager_record:
                manager_id = manager_record['id']
        
        hr_ids = _get_active_users_by_role('hr')
        accounts_ids = _get_active_users_by_role('accounts')
        
        notify_approvers_offboarding_initiated(offboarding_id, employee_name, manager_id, hr_ids, accounts_ids)
        
        return offboarding_id

def get_offboarding_requests(user_role, user_id):
    if user_role in ['hr', 'accounts', 'admin', 'superadmin']:
        return execute_query("SELECT * FROM offboarding_request ORDER BY created_at DESC")
    elif user_role == 'manager':
        # Get employees where this manager is the project manager or reporting manager
        employees = execute_query("""
            SELECT id FROM employee 
            WHERE reporting_manager_id = %s
               OR id IN (SELECT employee_id FROM team_member WHERE project_id IN 
                         (SELECT id FROM project WHERE project_manager_id = %s) AND status = 'active')
        """, (user_id, user_id))
        emp_ids = [e['id'] for e in employees]
        if not emp_ids:
            return []
        
        format_strings = ','.join(['%s'] * len(emp_ids))
        query = f"SELECT * FROM offboarding_request WHERE employee_id IN ({format_strings}) ORDER BY created_at DESC"
        return execute_query(query, tuple(emp_ids))
    return []

def get_offboarding_details(offboarding_id):
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req:
        return None
        
    checklist = execute_query("SELECT * FROM offboarding_checklist_item WHERE offboarding_id = %s", (offboarding_id,))
    approvals = execute_query("SELECT * FROM offboarding_approval WHERE offboarding_id = %s", (offboarding_id,))
    audit = execute_query("SELECT * FROM offboarding_audit_log WHERE offboarding_id = %s ORDER BY performed_at DESC", (offboarding_id,))
    
    # Handle ASSETS_RETURNED dynamic calculation
    outstanding_devices = get_employee_devices(req['employee_name'])
    for item in checklist:
        if item['item_type'] == 'ASSETS_RETURNED':
            if not outstanding_devices:
                if item['status'] != 'DONE':
                    # Auto mark done
                    with Transaction() as cursor:
                        cursor.execute("UPDATE offboarding_checklist_item SET status = 'DONE' WHERE id = %s", (item['id'],))
                    item['status'] = 'DONE'
            else:
                if item['status'] != 'PENDING':
                    # Revert if devices checked out again? Unlikely but safe
                    with Transaction() as cursor:
                        cursor.execute("UPDATE offboarding_checklist_item SET status = 'PENDING' WHERE id = %s", (item['id'],))
                    item['status'] = 'PENDING'
            item['outstanding_devices'] = outstanding_devices
            break
            
    return {
        'request': req,
        'checklist': checklist,
        'approvals': approvals,
        'audit': audit
    }

def update_checklist_item(offboarding_id, item_type, status, notes, marker_id, marker_name):
    if item_type == 'ASSETS_RETURNED':
        raise ValueError("ASSETS_RETURNED cannot be manually updated.")
        
    with Transaction() as cursor:
        cursor.execute("""
            UPDATE offboarding_checklist_item 
            SET status = %s, notes = %s, marked_by = %s, marked_by_name = %s, marked_at = CURRENT_TIMESTAMP
            WHERE offboarding_id = %s AND item_type = %s
        """, (status, notes, marker_id, marker_name, offboarding_id, item_type))
        
        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by, performed_by_name, notes)
            VALUES (%s, 'CHECKLIST_UPDATE', %s, %s, %s, %s)
        """, (offboarding_id, f"{item_type}: {status}", marker_id, marker_name, notes))
        
    _check_completion(offboarding_id)

def approve_reject(offboarding_id, approver_role, approver_id, approver_name, decision, comments):
    if decision not in ['APPROVED', 'REJECTED', 'PENDING']:
        raise ValueError("Invalid decision")
    if decision == 'REJECTED' and not comments:
        raise ValueError("Comments required for rejection")
        
    with Transaction() as cursor:
        # Check if already completed
        cursor.execute("SELECT status, employee_name FROM offboarding_request WHERE id = %s", (offboarding_id,))
        req = cursor.fetchone()
        if not req:
            raise ValueError("Request not found")
        if req['status'] in ('COMPLETED', 'CANCELLED'):
            raise ValueError(f"Request is already {req['status']}")
            
        cursor.execute("""
            UPDATE offboarding_approval 
            SET status = %s, comments = %s, approver_id = %s, approver_name = %s, acted_at = CURRENT_TIMESTAMP
            WHERE offboarding_id = %s AND approver_role = %s
        """, (decision, comments, approver_id, approver_name, offboarding_id, approver_role))
        
        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, new_value, performed_by, performed_by_name, notes)
            VALUES (%s, 'APPROVAL_DECISION', %s, %s, %s, %s)
        """, (offboarding_id, f"{approver_role}: {decision}", approver_id, approver_name, comments))
        
        if decision == 'REJECTED':
            cursor.execute("UPDATE offboarding_request SET status = 'IN_PROGRESS' WHERE id = %s", (offboarding_id,))
            hr_ids = _get_active_users_by_role('hr')
            notify_hr_approval_decision(offboarding_id, req['employee_name'], approver_role, decision, comments, hr_ids)
            
    _check_completion(offboarding_id)

def cancel_offboarding(offboarding_id, canceler_id, canceler_name):
    with Transaction() as cursor:
        cursor.execute("UPDATE offboarding_request SET status = 'CANCELLED' WHERE id = %s AND status NOT IN ('COMPLETED', 'CANCELLED')", (offboarding_id,))
        if cursor.rowcount == 0:
            raise ValueError("Cannot cancel request.")
            
        cursor.execute("""
            INSERT INTO offboarding_audit_log (offboarding_id, action, performed_by, performed_by_name, notes)
            VALUES (%s, 'CANCELLED', %s, %s, 'Offboarding cancelled')
        """, (offboarding_id, canceler_id, canceler_name))

def _check_completion(offboarding_id):
    # This must be called AFTER transactions commit, so we check using simple execute_single
    req = execute_single("SELECT * FROM offboarding_request WHERE id = %s", (offboarding_id,))
    if not req or req['status'] in ('COMPLETED', 'CANCELLED'):
        return
        
    approvals = execute_query("SELECT status FROM offboarding_approval WHERE offboarding_id = %s", (offboarding_id,))
    all_approved = all(a['status'] == 'APPROVED' for a in approvals)
    
    checklist = execute_query("SELECT status, item_type FROM offboarding_checklist_item WHERE offboarding_id = %s", (offboarding_id,))
    
    # We must explicitly evaluate ASSETS_RETURNED logic for this check since DB state might be PENDING
    all_done = True
    for c in checklist:
        if c['item_type'] == 'ASSETS_RETURNED':
            outstanding = get_employee_devices(req['employee_name'])
            if outstanding:
                all_done = False
                break
        else:
            if c['status'] not in ('DONE', 'NOT_APPLICABLE'):
                all_done = False
                break
                
    if all_approved and all_done:
        with Transaction() as cursor:
            # Re-verify to avoid race condition
            cursor.execute("SELECT status FROM offboarding_request WHERE id = %s FOR UPDATE", (offboarding_id,))
            current_status = cursor.fetchone()['status']
            if current_status in ('COMPLETED', 'CANCELLED'):
                return
                
            cursor.execute("UPDATE offboarding_request SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP WHERE id = %s", (offboarding_id,))
            
            # Revoke system login by setting is_active = FALSE
            cursor.execute("UPDATE users SET is_active = FALSE WHERE email = (SELECT email FROM employee WHERE id = %s)", (req['employee_id'],))
            
            cursor.execute("""
                INSERT INTO offboarding_audit_log (offboarding_id, action, notes)
                VALUES (%s, 'COMPLETED', 'Auto-completed after all approvals and checklist items met')
            """, (offboarding_id,))
            
        manager_name = get_employee_manager(req['employee_name'])
        manager_id = None
        if manager_name:
            manager_record = execute_single("SELECT id FROM users WHERE employee_name = %s", (manager_name,))
            if manager_record:
                manager_id = manager_record['id']
        hr_ids = _get_active_users_by_role('hr')
        notify_offboarding_completed(offboarding_id, req['employee_name'], manager_id, hr_ids)
