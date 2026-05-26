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
    Sends a branded password reset email asynchronously.
    Uses the same professional Altzor HRMS template as leave notifications.
    Delivery status is logged to the email_notification_logs audit table.
    """
    from datetime import datetime as _dt

    year = _dt.now().year

    subject = "Password Reset Request – Altzor HRMS"

    text = (
        f"Hello,\n\n"
        f"You requested a password reset. Please click the link below to reset your password:\n\n"
        f"{reset_link}\n\n"
        f"This link will expire in 30 minutes.\n\n"
        f"If you didn't request this, please ignore this email.\n\n"
        f"---\nThis is an automated message from Altzor HRMS."
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Reset</title>
</head>
<body style="margin:0;padding:0;background-color:#F4F6F9;font-family:Segoe UI,Helvetica Neue,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#F4F6F9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;border-radius:8px;
                      overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.10);">

          <!-- Brand Header -->
          <tr>
            <td style="background-color:#1F4E78;padding:28px 32px;">
              <p style="margin:0;font-size:13px;font-weight:600;
                         color:rgba(255,255,255,0.75);letter-spacing:1.5px;
                         text-transform:uppercase;">RISE</p>
              <h1 style="margin:6px 0 0;font-size:22px;font-weight:700;
                          color:#FFFFFF;line-height:1.3;">Password Reset Request</h1>
              <p style="margin:6px 0 0;font-size:14px;color:rgba(255,255,255,0.85);">
                A password reset was requested for your account
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background-color:#FFFFFF;padding:32px;">
              <p style="margin:0 0 16px;font-size:15px;color:#333;line-height:1.6;">
                Hello,
              </p>
              <p style="margin:0 0 24px;font-size:15px;color:#333;line-height:1.6;">
                We received a request to reset your password. Click the button below
                to create a new password. This link will expire in
                <strong>30 minutes</strong>.
              </p>

              <table cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;">
                <tr>
                  <td style="border-radius:6px;background-color:#1F4E78;">
                    <a href="{reset_link}" target="_blank"
                       style="display:inline-block;padding:12px 28px;font-size:14px;
                              font-weight:600;color:#FFFFFF;text-decoration:none;
                              border-radius:6px;letter-spacing:0.3px;">Reset My Password &rarr;</a>
                  </td>
                </tr>
              </table>

              <p style="margin:16px 0 8px;font-size:13px;color:#777;line-height:1.6;">
                If the button doesn't work, copy and paste this URL into your browser:
              </p>
              <p style="margin:0 0 24px;font-size:12px;color:#1F4E78;word-break:break-all;">
                {reset_link}
              </p>

              <p style="margin:20px 0 0;font-size:13px;color:#777;
                        border-top:1px solid #E0E0E0;padding-top:16px;">
                If you didn't request a password reset, you can safely ignore this email.
                Your password will remain unchanged.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#F8F9FB;padding:20px 32px;
                        border-top:1px solid #E0E0E0;">
              <p style="margin:0;font-size:12px;color:#777;line-height:1.6;">
                This is an automated notification from <strong>Altzor HRMS</strong>.
                Please do not reply directly to this email.<br>
                &copy; {year} Altzor Technologies. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    send_email_async(
        to_email=to_email,
        subject=subject,
        html_body=html,
        text_body=text,
        notification_type="password_reset",
        recipient_name=to_email,
    )
    logger.info(f"Password reset email queued for {to_email}")


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
                <p>Please log into your <a href="{Config.FRONTEND_URL}" style="color: #007bff; text-decoration: none; font-weight: bold;">HRMS Dashboard</a> to view full details and check any attachments.</p>
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
