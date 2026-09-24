from app.models.database import execute_query, Transaction
import logging

logger = logging.getLogger(__name__)

def _get_active_employee_names_by_role(role):
    try:
        users = execute_query(
            "SELECT employee_name FROM users WHERE role = %s AND (is_active IS NULL OR is_active = TRUE)",
            (role,)
        )
        return [u['employee_name'] for u in users if u.get('employee_name')]
    except Exception as e:
        logger.error(f"Error fetching users by role {role}: {e}")
        return []

def _create_notification(employee_name, title, message, n_type="offboarding"):
    if not employee_name:
        return
    try:
        with Transaction() as cursor:
            cursor.execute(
                "INSERT INTO notifications (employee_name, title, message, type) VALUES (%s, %s, %s, %s)",
                (employee_name, title, message, n_type)
            )
    except Exception as e:
        logger.warning(f"Failed to create notification for {employee_name}: {e}")

def notify_resignation_submitted(offboarding_id, employee_name, manager_name=None):
    """Notify Employee, Manager, and HR when resignation is submitted."""
    # 1. Notify Employee
    _create_notification(
        employee_name,
        "Resignation Submitted",
        "Your resignation request has been submitted and is awaiting manager approval.",
        "info"
    )
    # 2. Notify Manager
    if manager_name:
        _create_notification(
            manager_name,
            "New Resignation Request",
            f"{employee_name} has submitted a resignation request awaiting your review.",
            "action_required"
        )
    # 3. Notify HR
    for hr_name in _get_active_employee_names_by_role('hr'):
        _create_notification(
            hr_name,
            "New Exit Request",
            f"A resignation request was submitted by {employee_name} (Case #{offboarding_id}).",
            "info"
        )

def notify_manager_decision(offboarding_id, employee_name, decision, rejection_reason=None, manager_name=None):
    """Notify Employee, HR, and System Admin after manager approval/rejection."""
    if decision == 'APPROVED':
        _create_notification(
            employee_name,
            "Resignation Approved",
            "Your resignation request has been approved. You are now in your notice period. Please complete your offboarding consent.",
            "success"
        )
        _create_notification(
            employee_name,
            "Offboarding Consent Required",
            "Please review and submit your Offboarding Consent Form.",
            "action_required"
        )
        for hr_name in _get_active_employee_names_by_role('hr'):
            _create_notification(
                hr_name,
                "Resignation Approved by Manager",
                f"Resignation for {employee_name} has been approved by {manager_name or 'Manager'}. Notice period has started.",
                "info"
            )
        for sa_name in _get_active_employee_names_by_role('system_admin'):
            _create_notification(
                sa_name,
                "New IT Offboarding Task",
                f"Offboarding initiated for {employee_name}. IT access closure has been scheduled.",
                "action_required"
            )
    else:
        msg = f"Your resignation request has been rejected."
        if rejection_reason:
            msg += f" Reason: {rejection_reason}"
        _create_notification(employee_name, "Resignation Rejected", msg, "warning")
        for hr_name in _get_active_employee_names_by_role('hr'):
            _create_notification(
                hr_name,
                "Resignation Rejected by Manager",
                f"Resignation for {employee_name} was rejected by {manager_name or 'Manager'}. Reason: {rejection_reason or 'None'}",
                "warning"
            )

def notify_consent_completed(offboarding_id, employee_name, manager_name=None):
    """Notify HR and Manager that employee finished consent."""
    for hr_name in _get_active_employee_names_by_role('hr'):
        _create_notification(
            hr_name,
            "Offboarding Consent Completed",
            f"{employee_name} has completed the offboarding consent acknowledgements.",
            "info"
        )
    if manager_name:
        _create_notification(
            manager_name,
            "Offboarding Consent Completed",
            f"{employee_name} has submitted the required offboarding consent form.",
            "info"
        )

def notify_assets_cleared(offboarding_id, employee_name):
    """Notify HR and Employee that all assigned assets have been returned."""
    _create_notification(
        employee_name,
        "Assets Return Complete",
        "All company assets assigned to you have been marked as returned.",
        "success"
    )
    for hr_name in _get_active_employee_names_by_role('hr'):
        _create_notification(
            hr_name,
            "Assets Cleared",
            f"All assigned assets for {employee_name} have been cleared.",
            "success"
        )

def notify_it_closure(offboarding_id, employee_name, personal_email=None):
    """Notify HR and former employee that IT access has been revoked."""
    for hr_name in _get_active_employee_names_by_role('hr'):
        _create_notification(
            hr_name,
            "IT Access Closed",
            f"System Admin has disabled corporate account and revoked system access for {employee_name}.",
            "info"
        )
    # If personal email is provided, send post-employment notification via email
    if personal_email:
        try:
            from app.utils.email_service import send_email_async
            from app.config import Config
            send_email_async(
                to_email=personal_email,
                subject="Altzor HRMS - Corporate Account Closure & Exit Portal Access",
                html_body=f"""
                <p>Hello {employee_name},</p>
                <p>Your corporate access has been decommissioned as part of your offboarding process.</p>
                <p>You can access your post-employment documents, relieving letters, and final clearance status through the 
                <strong>Exit Portal</strong> using this personal email address.</p>
                <p><a href="{Config.FRONTEND_URL}/exit-portal/login" style="padding: 10px 18px; background: #2563EB; color: #fff; text-decoration: none; border-radius: 6px;">Access Exit Portal</a></p>
                <p>Best regards,<br>Altzor Digital Solutions HR Team</p>
                """,
                text_body=f"Hello {employee_name},\nYour corporate access has been decommissioned. You can access the Exit Portal at {Config.FRONTEND_URL}/exit-portal/login using your personal email: {personal_email}.\nBest regards,\nAltzor HR Team",
                notification_type="it_closure",
                recipient_name=employee_name
            )
        except Exception as e:
            logger.warning(f"Could not send IT closure email to {personal_email}: {e}")

def notify_offboarding_completed(offboarding_id, employee_name, manager_name=None, personal_email=None):
    """Notify HR, Manager, and Employee that offboarding is completely finalized."""
    if manager_name:
        _create_notification(
            manager_name,
            "Offboarding Completed",
            f"Offboarding for {employee_name} has been completed and marked finalized by HR.",
            "success"
        )
    for hr_name in _get_active_employee_names_by_role('hr'):
        _create_notification(
            hr_name,
            "Offboarding Completed",
            f"Offboarding case #{offboarding_id} for {employee_name} has been successfully closed.",
            "success"
        )
    if personal_email:
        try:
            from app.utils.email_service import send_email_async
            from app.config import Config
            send_email_async(
                to_email=personal_email,
                subject="Altzor HRMS - Offboarding Completed & Relieving Documents Ready",
                html_body=f"""
                <p>Hello {employee_name},</p>
                <p>Your offboarding has been fully completed. Your relieving and experience documents are now available in your Exit Portal.</p>
                <p><a href="{Config.FRONTEND_URL}/exit-portal/login" style="padding: 10px 18px; background: #16A34A; color: #fff; text-decoration: none; border-radius: 6px;">View Documents in Exit Portal</a></p>
                <p>We wish you all the best in your future endeavors!</p>
                <p>Best regards,<br>Altzor Digital Solutions HR Team</p>
                """,
                text_body=f"Hello {employee_name},\nYour offboarding has been completed. Your relieving and experience documents are available in your Exit Portal at {Config.FRONTEND_URL}/exit-portal/login.\nBest regards,\nAltzor HR Team",
                notification_type="offboarding_completed",
                recipient_name=employee_name
            )
        except Exception as e:
            logger.warning(f"Could not send offboarding completed email to {personal_email}: {e}")
