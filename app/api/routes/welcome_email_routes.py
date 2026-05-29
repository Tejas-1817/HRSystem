import logging
import threading
from flask import Blueprint, request, jsonify
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import role_required
from app.utils.display_name_service import strip_all_prefixes
from app.utils.email_service import _smtp_send, _log_notification

logger = logging.getLogger(__name__)
welcome_email_bp = Blueprint('welcome_email', __name__)

DEFAULT_WELCOME_EMAIL_SUBJECT = "Welcome to Altzor Digital Solutions Private Limited"

DEFAULT_WELCOME_EMAIL_BODY = """Dear {{Employee Full Name}},

We are thrilled to welcome you to the Altzor Digital Solutions Private Limited family! 
You've joined a team of passionate and talented people, and we're excited to have you on board. 
We believe you'll bring great energy and skills to the team, and we look forward to growing together.

Your IT setup will be ready for you on your first day. 
If you face any issues with your system, accounts, or access, please reach out to me.
For any HR-related queries — policies, documents, onboarding formalities — feel free to ask.

Once again, a very warm welcome! Here's to a fantastic journey ahead.

Thanks & Regards,
Shruti Jadhav
Sr Manager Recruitment and HR | Altzor Digital Solutions
📞 +91 0000000000 | ✉️ shruti.jadhavjs@gmail.com 
🌐 www.altzor.com"""


def send_welcome_email_worker(employee_id, email, full_name, first_name, subject, body):
    """
    Background worker thread to deliver the welcome email and remove the employee 
    from the pending list on successful transmission.
    """
    try:
        # Dynamically replace variables
        rendered_subject = subject.replace("{{Employee Full Name}}", full_name).replace("{{Employee First Name}}", first_name)
        rendered_body = body.replace("{{Employee Full Name}}", full_name).replace("{{Employee First Name}}", first_name)
        
        # Format HTML body preserving line breaks
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Welcome to Altzor</title>
</head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 20px; background-color: #F4F6F9;">
  <div style="max-width: 600px; margin: 0 auto; background: #FFFFFF; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-top: 5px solid #1F4E78;">
    <div style="white-space: pre-wrap; font-size: 15px;">{rendered_body}</div>
  </div>
</body>
</html>"""
        
        # Attempt synchronous SMTP send inside background thread
        logger.info(f"Sending welcome email to {full_name} <{email}>...")
        _smtp_send(email, rendered_subject, html_body, rendered_body)
        
        # Delete from pending_welcome_emails on success
        execute_query(
            "DELETE FROM pending_welcome_emails WHERE employee_id = %s",
            (employee_id,),
            commit=True
        )
        
        logger.info(f"[OK] Welcome email successfully sent to {full_name} ({email}). Removed from pending table.")
        _log_notification("welcome_email", email, full_name, None, sent=True)
    except Exception as exc:
        logger.error(f"[FAIL] Failed to send welcome email to {full_name} ({email}): {exc}", exc_info=True)
        _log_notification(
            "welcome_email", email, full_name, None,
            sent=False, error_message=str(exc)[:500]
        )


@welcome_email_bp.route("/pending-welcome-emails", methods=["GET"])
@role_required(["hr", "admin"])
def get_pending_welcome_emails(current_user):
    """
    Fetch a list of employees who are currently in the pending_welcome_emails table.
    Returns: Necessary details (ID, First Name, Full Name, Email).
    """
    try:
        query = """
            SELECT e.id, e.name, e.email 
            FROM pending_welcome_emails p
            JOIN employee e ON p.employee_id = e.id
            ORDER BY p.created_at DESC
        """
        rows = execute_query(query)
        
        serialized = []
        for row in rows:
            full_name = strip_all_prefixes(row["name"])
            first_name = full_name.split()[0] if full_name else ""
            serialized.append({
                "id": row["id"],
                "firstName": first_name,
                "fullName": full_name,
                "email": row["email"]
            })
            
        return jsonify({
            "success": True,
            "count": len(serialized),
            "pending_emails": serialized
        }), 200
    except Exception as e:
        logger.error(f"Error fetching pending welcome emails: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@welcome_email_bp.route("/send-welcome-emails", methods=["POST"])
@role_required(["hr", "admin"])
def send_welcome_emails(current_user):
    """
    Accepts an array of employee_ids and asynchronously delivers welcome emails.
    Optionally accepts a custom 'subject' and 'body' in the JSON body.
    """
    try:
        data = request.get_json(silent=True) or {}
        employee_ids = data.get("employee_ids") or data.get("employeeIds")
        
        if not employee_ids or not isinstance(employee_ids, list):
            return jsonify({
                "success": False, 
                "error": "Required field 'employee_ids' must be a non-empty array of employee IDs."
            }), 400
            
        subject_template = data.get("subject") or DEFAULT_WELCOME_EMAIL_SUBJECT
        body_template = data.get("body") or DEFAULT_WELCOME_EMAIL_BODY
        
        sent_count = 0
        for emp_id in employee_ids:
            # Verify the employee is actually pending
            emp = execute_single("""
                SELECT e.id, e.name, e.email 
                FROM pending_welcome_emails p
                JOIN employee e ON p.employee_id = e.id
                WHERE p.employee_id = %s
            """, (emp_id,))
            
            if not emp:
                continue
                
            full_name = strip_all_prefixes(emp["name"])
            first_name = full_name.split()[0] if full_name else ""
            email = emp["email"]
            
            # Spawn a background thread to send the email asynchronously
            thread = threading.Thread(
                target=send_welcome_email_worker,
                args=(emp_id, email, full_name, first_name, subject_template, body_template),
                daemon=True,
                name=f"welcome-email-{emp_id}"
            )
            thread.start()
            sent_count += 1
            
        return jsonify({
            "success": True,
            "message": f"Successfully queued welcome emails for {sent_count} pending employee(s) in background threads."
        }), 200
        
    except Exception as e:
        logger.error(f"Error triggering welcome emails: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500
