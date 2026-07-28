from app.models.database import Transaction
from datetime import datetime

def notify_approvers_offboarding_initiated(offboarding_id, employee_name, manager_id, hr_ids, accounts_ids):
    with Transaction() as cursor:
        title = f"Offboarding Initiated: {employee_name}"
        message = f"An offboarding request has been initiated for {employee_name}. Please review and approve."
        type = "action_required"
        link = f"/offboarding/dashboard?id={offboarding_id}"
        
        # Notify manager
        if manager_id:
            cursor.execute("INSERT INTO notifications (user_id, title, message, type, link) VALUES (%s, %s, %s, %s, %s)",
                           (manager_id, title, message, type, link))
        
        # Notify HRs
        for hr_id in hr_ids:
            cursor.execute("INSERT INTO notifications (user_id, title, message, type, link) VALUES (%s, %s, %s, %s, %s)",
                           (hr_id, title, message, type, link))
            
        # Notify Accounts
        for accounts_id in accounts_ids:
            cursor.execute("INSERT INTO notifications (user_id, title, message, type, link) VALUES (%s, %s, %s, %s, %s)",
                           (accounts_id, title, message, type, link))

def notify_hr_approval_decision(offboarding_id, employee_name, approver_role, decision, comments, hr_ids):
    with Transaction() as cursor:
        title = f"Offboarding {decision}: {employee_name}"
        message = f"The {approver_role} approval for {employee_name}'s offboarding is now {decision}."
        if comments:
            message += f" Comments: {comments}"
        type = "action_required" if decision == "REJECTED" else "info"
        link = f"/offboarding/dashboard?id={offboarding_id}"
        
        for hr_id in hr_ids:
            cursor.execute("INSERT INTO notifications (user_id, title, message, type, link) VALUES (%s, %s, %s, %s, %s)",
                           (hr_id, title, message, type, link))

def notify_offboarding_completed(offboarding_id, employee_name, manager_id, hr_ids):
    with Transaction() as cursor:
        title = f"Offboarding Completed: {employee_name}"
        message = f"The offboarding process for {employee_name} has been successfully completed and system access is revoked."
        type = "success"
        link = f"/offboarding/dashboard?id={offboarding_id}"
        
        if manager_id:
            cursor.execute("INSERT INTO notifications (user_id, title, message, type, link) VALUES (%s, %s, %s, %s, %s)",
                           (manager_id, title, message, type, link))
        for hr_id in hr_ids:
            cursor.execute("INSERT INTO notifications (user_id, title, message, type, link) VALUES (%s, %s, %s, %s, %s)",
                           (hr_id, title, message, type, link))
