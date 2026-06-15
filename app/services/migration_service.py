import logging
from flask import request
from app.models.database import execute_single, Transaction

logger = logging.getLogger(__name__)

def migrate_login_email(joinee_id, login_email, company_email, performed_by_user_id):
    """
    Executes the secure login migration workflow inside a transaction.
    """
    with Transaction() as cursor:
        # Step 1: Retrieve joinee
        cursor.execute("""
            SELECT id, user_id, onboarding_status, personal_email, 
                   company_email, active_login_email 
            FROM onboarding_joinee 
            WHERE id = %s
        """, (joinee_id,))
        joinee = cursor.fetchone()
        
        if not joinee:
            return {
                "status": 404, 
                "response": {"success": False, "message": "Onboarding joinee not found."}
            }
            
        # Step 2: Validate status
        if joinee["onboarding_status"] != "VERIFIED":
            return {
                "status": 400, 
                "response": {"success": False, "message": "Joinee must be fully verified before login migration."}
            }
            
        # Step 3: Check uniqueness if company_email is provided
        if company_email:
            # Check users table (using username as per schema)
            cursor.execute(
                "SELECT id FROM users WHERE username = %s AND id != %s", 
                (company_email, joinee["user_id"])
            )
            if cursor.fetchone():
                return {
                    "status": 409, 
                    "response": {"success": False, "message": "Company email already exists in users table."}
                }
            
            # Check onboarding_joinee table
            cursor.execute(
                "SELECT id FROM onboarding_joinee WHERE company_email = %s AND id != %s", 
                (company_email, joinee_id)
            )
            if cursor.fetchone():
                return {
                    "status": 409, 
                    "response": {"success": False, "message": "Company email already exists in onboarding records."}
                }
                
            # Update company email
            cursor.execute(
                "UPDATE onboarding_joinee SET company_email = %s WHERE id = %s", 
                (company_email, joinee_id)
            )
            joinee["company_email"] = company_email
            
        # Step 4: Determine active login email
        if login_email not in (joinee["personal_email"], joinee["company_email"]):
            return {
                "status": 400, 
                "response": {"success": False, "message": "Selected login email must be exactly one of personal or company email."}
            }
            
        # Step 5 & 6: Update users record
        cursor.execute(
            "UPDATE users SET username = %s WHERE id = %s", 
            (login_email, joinee["user_id"])
        )
        
        # Step 7: Update active login email in onboarding
        cursor.execute(
            "UPDATE onboarding_joinee SET active_login_email = %s WHERE id = %s", 
            (login_email, joinee_id)
        )
        
        # Step 8: Create Audit log
        ip_address = request.remote_addr if request else "Unknown"
        user_agent = request.headers.get("User-Agent", "Unknown") if request else "Unknown"
        notes = f"IP: {ip_address} | User-Agent: {user_agent}"
        
        cursor.execute("""
            INSERT INTO onboarding_audit_log 
                (joinee_id, action, old_value, new_value, performed_by, performed_at, notes)
            VALUES (%s, 'LOGIN_MIGRATED', %s, %s, %s, NOW(), %s)
        """, (joinee_id, joinee["active_login_email"], login_email, performed_by_user_id, notes))
        
        return {
            "status": 200,
            "response": {
                "success": True,
                "message": "Login email updated successfully.",
                "active_login_email": login_email,
                "company_email": joinee["company_email"]
            }
        }

def get_prefill_data(joinee_id):
    """
    Retrieves verified onboarding data for HR prefill.
    """
    query = """
        SELECT 
            person_id, full_name, phone, personal_email, company_email, 
            active_login_email, joining_date, assigned_role, assigned_department, 
            onboarding_status
        FROM onboarding_joinee 
        WHERE id = %s
    """
    return execute_single(query, (joinee_id,))
