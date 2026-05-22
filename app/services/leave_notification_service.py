"""
leave_notification_service.py
==============================
Single-responsibility service for leave workflow email notifications.

Each public function:
  1. Resolves the recipient's email address from the users table
  2. Renders the appropriate HTML template
  3. Dispatches async email via send_email_async()
  4. Never raises — all errors are logged and swallowed

This module is the only file that imports from both email_templates and
email_service, keeping the coupling clean and testable.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_date_str(value) -> str:
    """Convert date/datetime/str to a readable 'DD Mon YYYY' string."""
    if value is None:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    try:
        from datetime import date
        d = date.fromisoformat(str(value))
        return d.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(value)


def _safe_datetime_str(value) -> str:
    """Convert datetime/str to 'DD Mon YYYY HH:MM' readable string."""
    if value is None:
        return datetime.now().strftime("%d %b %Y %H:%M")
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y %H:%M")
    return str(value)


# ---------------------------------------------------------------------------
# Public: notify Manager when an employee applies for leave
# ---------------------------------------------------------------------------

def notify_manager_leave_application(
    leave_data: dict,
    manager_name: str,
) -> None:
    """
    Send a leave application notification email to the assigned manager.

    Args:
        leave_data   : Dict with keys: employee_name, employee_id, leave_type,
                       leave_type_category, half_day_period, start_date, end_date,
                       leave_duration, reason, applied_at, id (leave ID)
        manager_name : The system name of the manager (e.g. 'M_Tejas')
    """
    try:
        from app.utils.email_service import send_email_async, _get_email_for_employee
        from app.utils.email_templates import leave_application_to_manager

        manager_email = _get_email_for_employee(manager_name)
        if not manager_email:
            logger.warning(
                "[leave_notify] Manager '%s' has no email — skipping leave application email.",
                manager_name
            )
            return

        employee_name       = leave_data.get("employee_name", "Unknown")
        employee_id         = leave_data.get("employee_id")
        leave_type          = leave_data.get("leave_type", "")
        leave_type_category = leave_data.get("leave_type_category", "full_day")
        half_day_period     = leave_data.get("half_day_period")
        start_date          = _safe_date_str(leave_data.get("start_date"))
        end_date            = _safe_date_str(leave_data.get("end_date"))
        total_days          = float(leave_data.get("leave_duration", 1))
        reason              = leave_data.get("reason", "")
        submitted_at        = _safe_datetime_str(leave_data.get("applied_at"))
        leave_id            = leave_data.get("id")

        subject, html_body, text_body = leave_application_to_manager(
            manager_name=manager_name,
            employee_name=employee_name,
            employee_id=str(employee_id) if employee_id else None,
            leave_type=leave_type,
            leave_type_category=leave_type_category,
            half_day_period=half_day_period,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            submitted_at=submitted_at,
            leave_id=leave_id,
        )

        send_email_async(
            to_email=manager_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            notification_type="leave_application",
            recipient_name=manager_name,
            leave_id=leave_id,
        )

        logger.info(
            "[leave_notify] leave_application email queued → manager '%s' <%s> for leave ID %s",
            manager_name, manager_email, leave_id
        )

    except Exception as exc:
        # Never raise — email failure must not break the leave submission flow
        logger.error(
            "[leave_notify] Error queuing leave_application email for manager '%s': %s",
            manager_name, exc, exc_info=True
        )


# ---------------------------------------------------------------------------
# Public: notify Employee when their leave is approved
# ---------------------------------------------------------------------------

def notify_employee_leave_approved(
    leave_data: dict,
    approver_name: str,
) -> None:
    """
    Send a leave approval confirmation email to the team member.

    Args:
        leave_data    : Full leave row dict (from DB or route handler)
        approver_name : employee_name of the person who approved
    """
    try:
        from app.utils.email_service import send_email_async, _get_email_for_employee
        from app.utils.email_templates import leave_approved_to_employee

        employee_name = leave_data.get("employee_name", "")
        employee_email = _get_email_for_employee(employee_name)
        if not employee_email:
            logger.warning(
                "[leave_notify] Employee '%s' has no email — skipping leave approved email.",
                employee_name
            )
            return

        leave_type          = leave_data.get("leave_type", "")
        leave_type_category = leave_data.get("leave_type_category", "full_day")
        half_day_period     = leave_data.get("half_day_period")
        start_date          = _safe_date_str(leave_data.get("start_date"))
        end_date            = _safe_date_str(leave_data.get("end_date"))
        total_days          = float(leave_data.get("leave_duration", 1))
        approved_at         = _safe_datetime_str(leave_data.get("approved_at"))
        leave_id            = leave_data.get("id")

        subject, html_body, text_body = leave_approved_to_employee(
            employee_name=employee_name,
            approved_by=approver_name,
            leave_type=leave_type,
            leave_type_category=leave_type_category,
            half_day_period=half_day_period,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            approved_at=approved_at,
            leave_id=leave_id,
        )

        send_email_async(
            to_email=employee_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            notification_type="leave_approved",
            recipient_name=employee_name,
            leave_id=leave_id,
        )

        logger.info(
            "[leave_notify] leave_approved email queued → employee '%s' <%s> for leave ID %s",
            employee_name, employee_email, leave_id
        )

    except Exception as exc:
        logger.error(
            "[leave_notify] Error queuing leave_approved email for '%s': %s",
            leave_data.get("employee_name"), exc, exc_info=True
        )


# ---------------------------------------------------------------------------
# Public: notify Employee when their leave is rejected
# ---------------------------------------------------------------------------

def notify_employee_leave_rejected(
    leave_data: dict,
    rejector_name: str,
    rejection_reason: str,
) -> None:
    """
    Send a leave rejection notification email to the team member.

    Args:
        leave_data       : Full leave row dict
        rejector_name    : employee_name of the person who rejected
        rejection_reason : Human-readable rejection reason
    """
    try:
        from app.utils.email_service import send_email_async, _get_email_for_employee
        from app.utils.email_templates import leave_rejected_to_employee

        employee_name = leave_data.get("employee_name", "")
        employee_email = _get_email_for_employee(employee_name)
        if not employee_email:
            logger.warning(
                "[leave_notify] Employee '%s' has no email — skipping leave rejected email.",
                employee_name
            )
            return

        leave_type          = leave_data.get("leave_type", "")
        leave_type_category = leave_data.get("leave_type_category", "full_day")
        half_day_period     = leave_data.get("half_day_period")
        start_date          = _safe_date_str(leave_data.get("start_date"))
        end_date            = _safe_date_str(leave_data.get("end_date"))
        total_days          = float(leave_data.get("leave_duration", 1))
        rejected_at         = _safe_datetime_str(None)  # rejection just happened
        leave_id            = leave_data.get("id")

        subject, html_body, text_body = leave_rejected_to_employee(
            employee_name=employee_name,
            rejected_by=rejector_name,
            leave_type=leave_type,
            leave_type_category=leave_type_category,
            half_day_period=half_day_period,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            rejection_reason=rejection_reason,
            rejected_at=rejected_at,
            leave_id=leave_id,
        )

        send_email_async(
            to_email=employee_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            notification_type="leave_rejected",
            recipient_name=employee_name,
            leave_id=leave_id,
        )

        logger.info(
            "[leave_notify] leave_rejected email queued → employee '%s' <%s> for leave ID %s",
            employee_name, employee_email, leave_id
        )

    except Exception as exc:
        logger.error(
            "[leave_notify] Error queuing leave_rejected email for '%s': %s",
            leave_data.get("employee_name"), exc, exc_info=True
        )
