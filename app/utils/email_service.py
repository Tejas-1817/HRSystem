import smtplib
import logging
import threading
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal: resolve an employee's registered email address
# ---------------------------------------------------------------------------

def _get_email_for_employee(employee_name: str) -> str | None:
    """
    Look up the login email (username) for an employee by their system name.
    Returns None if the employee does not exist or has no account.
    """
    try:
        from app.models.database import execute_single
        row = execute_single(
            "SELECT username FROM users WHERE employee_name = %s AND is_active = TRUE LIMIT 1",
            (employee_name,)
        )
        return row["username"] if row else None
    except Exception as exc:
        logger.warning("Could not resolve email for employee '%s': %s", employee_name, exc)
        return None


# ---------------------------------------------------------------------------
# Internal: write delivery status to audit table (best-effort)
# ---------------------------------------------------------------------------

def _log_notification(
    notification_type: str,
    recipient_email: str,
    recipient_name: str | None,
    leave_id: int | None,
    sent: bool,
    error_message: str | None = None,
) -> None:
    """Insert one row into email_notification_logs. Swallows all exceptions."""
    try:
        from app.models.database import execute_query
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        execute_query(
            """
            INSERT INTO email_notification_logs
              (notification_type, recipient_email, recipient_name,
               leave_id, notification_sent, sent_at, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                notification_type,
                recipient_email,
                recipient_name,
                leave_id,
                sent,
                now if sent else None,
                error_message,
            ),
            commit=True,
        )
    except Exception as exc:
        logger.error("Failed to write email_notification_logs: %s", exc)


# ---------------------------------------------------------------------------
# Core: SMTP delivery (synchronous, called inside background thread)
# ---------------------------------------------------------------------------

def _smtp_send(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    """
    Establish SMTP connection and send a multipart/alternative message.
    Raises on any transport or authentication error (caller catches).
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = Config.MAIL_DEFAULT_SENDER
    msg["To"]      = to_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=20) as server:
        if Config.MAIL_USE_TLS:
            server.starttls()
        if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.sendmail(Config.MAIL_DEFAULT_SENDER, to_email, msg.as_string())


# ---------------------------------------------------------------------------
# Public API: async email send
# ---------------------------------------------------------------------------

def send_email_async(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    notification_type: str = "general",
    recipient_name: str | None = None,
    leave_id: int | None = None,
) -> None:
    """
    Send an HTML email in a background daemon thread.

    The calling request thread returns immediately — the email is delivered
    asynchronously. Delivery status (success/failure) is written to the
    `email_notification_logs` audit table.

    Args:
        to_email          : Recipient email address
        subject           : Email subject line
        html_body         : Full HTML email body
        text_body         : Plain-text fallback body
        notification_type : Audit label (e.g. 'leave_application')
        recipient_name    : Human name for audit log
        leave_id          : FK to leaves.id for traceability
    """
    def _worker():
        try:
            _smtp_send(to_email, subject, html_body, text_body)
            logger.info("[email] ✓ Sent '%s' to %s", notification_type, to_email)
            _log_notification(notification_type, to_email, recipient_name, leave_id, sent=True)
        except Exception as exc:
            logger.error("[email] ✗ Failed '%s' to %s: %s", notification_type, to_email, exc)
            _log_notification(
                notification_type, to_email, recipient_name, leave_id,
                sent=False, error_message=str(exc)[:500]
            )

    thread = threading.Thread(target=_worker, daemon=True, name=f"email-{notification_type}")
    thread.start()

def send_reset_email(to_email, reset_link):
    """
    Sends a password reset email using SMTP.
    In production, this should use a background task (like Celery)
    to avoid blocking the request.
    """
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Password Reset Request - HRMS"
        msg["From"] = Config.MAIL_DEFAULT_SENDER
        msg["To"] = to_email

        # Create text/html body
        text = f"Hello,\n\nYou requested a password reset. Please click the link below to reset your password:\n{reset_link}\n\nThis link will expire in 30 minutes.\n\nIf you didn't request this, please ignore this email."
        html = f"""
        <html>
        <body>
            <p>Hello,</p>
            <p>You requested a password reset. Please click the button below to reset your password:</p>
            <a href="{reset_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a>
            <p>This link will expire in 30 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Connect and send
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            if Config.MAIL_USE_TLS:
                server.starttls()
            
            # Note: MAIL_PASSWORD should be an App Password if using Gmail
            if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            
            server.sendmail(Config.MAIL_DEFAULT_SENDER, to_email, msg.as_string())
        
        logger.info(f"Password reset email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        # In production, you might want to re-raise or handle this specifically
        return False


def send_announcement_email(to_email, title, description):
    """
    Sends a company announcement email to an employee.
    """
    import re
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📢 Company Announcement: {title}"
        msg["From"] = Config.MAIL_DEFAULT_SENDER
        msg["To"] = to_email

        # Create text/html body
        # Strip HTML tags for plain text body
        text_desc = re.sub(r'<[^<]+?>', '', description) if '<' in description else description
        text = f"Hello,\n\nA new company announcement has been published:\n\nTitle: {title}\n\nDescription:\n{text_desc}\n\nPlease check the HRMS dashboard to view details and attachments."
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; padding: 20px; background-color: #f9f9f9;">
                <div style="text-align: center; border-bottom: 2px solid #007bff; padding-bottom: 10px; margin-bottom: 20px;">
                    <h2 style="color: #007bff; margin: 0;">📢 New Company Announcement</h2>
                </div>
                <h3 style="color: #333;">{title}</h3>
                <div style="background-color: #fff; border-left: 4px solid #007bff; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                    {description}
                </div>
                <p>Please log into your <a href="http://192.168.1.151:5002" style="color: #007bff; text-decoration: none; font-weight: bold;">HRMS Dashboard</a> to view full details and check any attachments.</p>
                <div style="font-size: 12px; color: #777; border-top: 1px solid #eee; padding-top: 10px; text-align: center; margin-top: 20px;">
                    This is an automated notification from Altzor HRMS. Please do not reply directly to this email.
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            if Config.MAIL_USE_TLS:
                server.starttls()
            if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_DEFAULT_SENDER, to_email, msg.as_string())
        
        logger.info(f"Announcement email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send announcement email to {to_email}: {str(e)}")
        return False
