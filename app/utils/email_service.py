import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import Config

logger = logging.getLogger(__name__)

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
