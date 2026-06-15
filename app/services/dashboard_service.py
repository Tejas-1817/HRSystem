import logging
from app.models.database import execute_query, execute_single
from app.services import declaration_service, document_service

logger = logging.getLogger(__name__)

def get_dashboard_stats():
    """
    Compute aggregate metrics for the HR onboarding dashboard.
    Uses a single query to avoid N+1 issues and sequential counts.
    """
    query = """
        SELECT 
            COUNT(*) as total_joinees,
            SUM(CASE WHEN onboarding_status IN ('PENDING', 'DOCUMENTS_SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED') THEN 1 ELSE 0 END) as pending_tasks,
            SUM(CASE WHEN onboarding_status IN ('DOCUMENTS_SUBMITTED', 'UNDER_REVIEW', 'VERIFIED') THEN 1 ELSE 0 END) as forms_submitted,
            SUM(CASE WHEN onboarding_status = 'VERIFIED' THEN 1 ELSE 0 END) as cleared_to_start
        FROM onboarding_joinee
    """
    result = execute_single(query)
    
    # Handle the case where the table is empty
    if not result:
        return {
            "total_joinees": 0,
            "pending_tasks": 0,
            "forms_submitted": 0,
            "cleared_to_start": 0
        }
        
    return {
        "total_joinees": int(result["total_joinees"] or 0),
        "pending_tasks": int(result["pending_tasks"] or 0),
        "forms_submitted": int(result["forms_submitted"] or 0),
        "cleared_to_start": int(result["cleared_to_start"] or 0)
    }

def get_joinee_summary(joinee_id):
    """
    Fetch a comprehensive summary for a single joinee.
    Includes joinee details, declaration, documents, and audit logs.
    """
    # 1. Fetch Joinee Record
    joinee = execute_single(
        "SELECT * FROM onboarding_joinee WHERE id = %s", 
        (joinee_id,)
    )
    if not joinee:
        return None

    # 2. Fetch Declaration (Reuse existing service)
    declaration = declaration_service.build_declaration_response(joinee_id)

    # 3. Fetch Documents (Reuse existing service, ensuring safety)
    # get_documents_by_joinee explicitly excludes file_path
    documents = document_service.get_documents_by_joinee(joinee_id)
    
    # 4. Fetch Audit Logs (Join with users table to get the name)
    audit_query = """
        SELECT 
            oal.action,
            COALESCE(u.employee_name, 'System') as performed_by,
            oal.old_value,
            oal.new_value,
            oal.performed_at as created_at
        FROM onboarding_audit_log oal
        LEFT JOIN users u ON oal.performed_by = u.id
        WHERE oal.joinee_id = %s
        ORDER BY oal.performed_at DESC
        LIMIT 20
    """
    audit_logs = execute_query(audit_query, (joinee_id,)) or []

    return {
        "joinee": joinee,
        "declaration": declaration,
        "documents": documents,
        "audit_log": audit_logs
    }
