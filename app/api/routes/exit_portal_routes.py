from flask import Blueprint, request, jsonify, send_from_directory
from app.models.database import execute_query, execute_single, Transaction
from app.config import Config
from app.utils.email_service import send_email_async
import jwt
import random
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
exit_portal_bp = Blueprint('exit_portal', __name__, url_prefix='/exit-portal')

def exit_token_required(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"success": False, "error": "Authorization token is missing"}), 401
        
        token = auth_header.split(" ")[1] if " " in auth_header else auth_header
        try:
            payload = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            if not payload.get('exit_portal'):
                return jsonify({"success": False, "error": "Invalid token type for Exit Portal"}), 403
            return f(payload, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "error": "Session expired. Please request a new OTP."}), 401
        except Exception as e:
            return jsonify({"success": False, "error": "Invalid token"}), 401
    wrapper.__name__ = f.__name__
    return wrapper

@exit_portal_bp.route('/request-otp', methods=['POST'])
def request_otp():
    data = request.get_json() or {}
    personal_email = (data.get('personal_email') or '').strip().lower()
    if not personal_email or '@' not in personal_email:
        return jsonify({"success": False, "error": "A valid personal email is required."}), 400

    # Locate employee or offboarding case with this personal email
    case = execute_single("""
        SELECT r.*, e.employment_status, e.id AS emp_id, e.name AS emp_name
        FROM offboarding_request r
        JOIN employee e ON r.employee_id = e.id
        WHERE LOWER(r.personal_email) = %s OR LOWER(e.personal_email) = %s
        ORDER BY r.id DESC LIMIT 1
    """, (personal_email, personal_email))

    if not case:
        return jsonify({
            "success": False, 
            "error": "No offboarding record found matching this personal email address. Please contact HR."
        }), 404

    # Generate 6-digit OTP
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = (datetime.now() + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')

    with Transaction() as cursor:
        # Invalidate old OTPs
        cursor.execute("UPDATE exit_portal_otp SET is_used = TRUE WHERE personal_email = %s", (personal_email,))
        
        # Save new OTP
        cursor.execute("""
            INSERT INTO exit_portal_otp (personal_email, employee_id, otp_code, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (personal_email, case['emp_id'], otp_code, expires_at))

    # Send email asynchronously
    send_email_async(
        to_email=personal_email,
        subject="Your Exit Portal Verification Code – Altzor HRMS",
        html_body=f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #1E293B;">
            <h2 style="color: #2563EB;">Exit Portal Verification</h2>
            <p>Hello {case['emp_name']},</p>
            <p>Your one-time verification code to access the Former Employee Exit Portal is:</p>
            <div style="font-size: 28px; font-weight: bold; letter-spacing: 4px; padding: 12px 24px; background: #F1F5F9; border-radius: 8px; display: inline-block; color: #0F172A;">
                {otp_code}
            </div>
            <p style="margin-top: 16px; color: #64748B; font-size: 13px;">This code is valid for 15 minutes. If you did not request this, please contact HR.</p>
        </div>
        """,
        text_body=f"Hello {case['emp_name']},\nYour Exit Portal verification code is: {otp_code}\nValid for 15 minutes.\nAltzor HRMS",
        notification_type="exit_portal_otp",
        recipient_name=case['emp_name']
    )

    resp = {
        "success": True,
        "message": f"Verification code sent to {personal_email}."
    }
    # In development mode, provide OTP preview for easy testing
    if Config.DEBUG:
        resp["otp_preview"] = otp_code

    return jsonify(resp), 200

@exit_portal_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json() or {}
    personal_email = (data.get('personal_email') or '').strip().lower()
    otp_code = (data.get('otp') or '').strip()

    if not personal_email or not otp_code:
        return jsonify({"success": False, "error": "Email and OTP code are required."}), 400

    record = execute_single("""
        SELECT * FROM exit_portal_otp 
        WHERE personal_email = %s AND otp_code = %s AND is_used = FALSE AND expires_at >= NOW()
        ORDER BY created_at DESC LIMIT 1
    """, (personal_email, otp_code))

    if not record:
        return jsonify({"success": False, "error": "Invalid or expired verification code."}), 400

    # Mark OTP as used
    with Transaction() as cursor:
        cursor.execute("UPDATE exit_portal_otp SET is_used = TRUE WHERE id = %s", (record['id'],))

    # Fetch employee
    emp = execute_single("SELECT * FROM employee WHERE id = %s", (record['employee_id'],))
    
    # Generate Exit Portal Token
    token_payload = {
        "exit_portal": True,
        "employee_id": emp['id'],
        "employee_name": emp['name'],
        "personal_email": personal_email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12)
    }
    token = jwt.encode(token_payload, Config.JWT_SECRET, algorithm="HS256")

    return jsonify({
        "success": True,
        "token": token,
        "employee": {
            "id": emp['id'],
            "name": emp['name'],
            "personal_email": personal_email
        }
    }), 200

@exit_portal_bp.route('/status', methods=['GET'])
@exit_token_required
def get_exit_status(current_former_user):
    emp_id = current_former_user['employee_id']
    
    case = execute_single("""
        SELECT * FROM offboarding_request 
        WHERE employee_id = %s 
        ORDER BY id DESC LIMIT 1
    """, (emp_id,))

    if not case:
        return jsonify({"success": False, "error": "Offboarding record not found."}), 404

    # Determine timeline flags
    resignation_approved = bool(case.get('manager_approved_at'))
    
    # Notice Period Completed
    notice_period_completed = False
    if case.get('last_working_day'):
        try:
            lwd = case['last_working_day']
            if isinstance(lwd, str):
                lwd = datetime.strptime(lwd, '%Y-%m-%d').date()
            notice_period_completed = (date.today() >= lwd)
        except Exception:
            pass
    if case['status'] == 'COMPLETED':
        notice_period_completed = True

    # Assets Returned
    from app.services.device_service import get_employee_devices
    outstanding_devices = get_employee_devices(case['employee_name'])
    assets_returned = (len(outstanding_devices) == 0)

    # IT Access Closed
    it_access_closed = bool(case.get('it_cleared_at'))

    # Final HR Clearance
    hr_clearance_completed = (case['status'] == 'COMPLETED')

    # Available Documents (Relieving Letter, Experience Letter, Payslips)
    docs = execute_query("""
        SELECT id, doc_type, file_path, status, verified_at, uploaded_at 
        FROM employee_documents 
        WHERE employee_name = %s AND doc_type IN ('relieving_letter', 'experience_letter', 'offer_letter')
    """, (case['employee_name'],))

    return jsonify({
        "success": True,
        "employee_name": case['employee_name'],
        "personal_email": current_former_user['personal_email'],
        "department": case.get('department'),
        "designation": case.get('designation'),
        "resignation_date": case.get('resignation_date'),
        "last_working_day": case.get('last_working_day'),
        "overall_status": case['status'],
        "timeline": {
            "resignation_approved": resignation_approved,
            "notice_period_completed": notice_period_completed,
            "assets_returned": assets_returned,
            "it_access_closed": it_access_closed,
            "hr_clearance_completed": hr_clearance_completed
        },
        "documents": docs,
        "hr_contact": {
            "name": "HR Department",
            "email": "hr@altzor.com",
            "support_notes": "For any final settlement inquiries or document requests, please email hr@altzor.com."
        }
    })
