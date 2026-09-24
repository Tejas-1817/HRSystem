from flask import Blueprint, request, jsonify
from app.offboarding import service
from app.api.middleware.auth import token_required, role_required
import logging

logger = logging.getLogger(__name__)
offboarding_bp = Blueprint('offboarding', __name__)

# ---------------------------------------------------------------------------
# Employee Resignation / Exit Request
# ---------------------------------------------------------------------------

@offboarding_bp.route('/resign', methods=['POST'])
@token_required
def submit_resignation(current_user):
    data = request.get_json() or {}
    try:
        employee_id = current_user.get('user_id')
        # If user is linked to an employee record
        from app.models.database import execute_single
        emp = execute_single("SELECT id, name, email, phone FROM employee WHERE name = %s OR email = %s", (current_user.get('employee_name'), current_user.get('username')))
        if emp:
            employee_id = emp['id']

        offboarding_id = service.submit_resignation(
            employee_id=employee_id,
            personal_email=data.get('personal_email'),
            personal_phone=data.get('personal_phone'),
            resignation_date=data.get('resignation_date'),
            proposed_lwd=data.get('proposed_last_working_day'),
            reason=data.get('reason'),
            reason_notes=data.get('reason_notes'),
            resignation_doc_path=data.get('resignation_doc_path'),
            initiator_user_id=current_user.get('user_id'),
            exit_type=data.get('exit_type', 'Voluntary Resignation'),
            other_exit_type=data.get('other_exit_type'),
            other_reason=data.get('other_reason'),
            handover_required=data.get('handover_required', 'Yes'),
            handover_to=data.get('handover_to'),
            handover_projects=data.get('handover_projects'),
            handover_notes=data.get('handover_notes'),
            alternate_phone=data.get('alternate_phone'),
            preferred_communication=data.get('preferred_communication', 'Personal Email'),
            post_employment_contact_consent=data.get('post_employment_contact_consent', 'Yes'),
            supporting_doc_path=data.get('supporting_doc_path'),
            declarations_confirmed=data.get('declarations_confirmed', True)
        )
        return jsonify({
            "success": True,
            "message": "Your resignation request has been submitted successfully and is awaiting manager approval.",
            "offboarding_id": offboarding_id
        }), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error submitting resignation: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_bp.route('/initiate', methods=['POST'])
@offboarding_bp.route('/', methods=['POST'])
@token_required
@role_required(['hr', 'admin', 'superadmin'])
def initiate_offboarding(current_user):
    data = request.get_json() or {}
    try:
        offboarding_id = service.initiate_offboarding_by_hr(
            employee_id=data.get('employee_id'),
            employee_name=data.get('employee_name'),
            reason=data.get('reason', 'RESIGNATION'),
            reason_notes=data.get('reason_notes'),
            last_working_day=data.get('last_working_day'),
            initiator_user_id=current_user.get('user_id'),
            initiator_user_name=current_user.get('employee_name')
        )
        return jsonify({
            "success": True,
            "message": "Offboarding initiated successfully.",
            "offboarding_id": offboarding_id
        }), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error initiating offboarding: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_bp.route('/my-case', methods=['GET'])
@token_required
def get_my_case(current_user):
    try:
        from app.models.database import execute_single, execute_query
        from app.services.device_service import get_employee_devices
        emp = execute_single("SELECT id, name, email, phone, personal_email, personal_phone, department, designation FROM employee WHERE name = %s OR email = %s", (current_user.get('employee_name'), current_user.get('username')))
        emp_id = emp['id'] if emp else current_user.get('user_id')
        emp_name = emp['name'] if emp else current_user.get('employee_name')
        
        assigned_assets = get_employee_devices(emp_name) if emp_name else []
        active_employees_raw = execute_query("""
            SELECT id, name, department, designation 
            FROM employee 
            WHERE (employment_status IS NULL OR employment_status != 'OFFBOARDED')
            ORDER BY name ASC
        """)
        from app.utils.display_name_service import strip_all_prefixes
        active_employees = []
        for ae in active_employees_raw:
            clean = strip_all_prefixes(ae.get('name') or '')
            active_employees.append({
                'id': ae['id'],
                'name': clean,
                'raw_name': ae.get('name'),
                'department': ae.get('department'),
                'designation': ae.get('designation')
            })

        req = execute_single("""
            SELECT * FROM offboarding_request 
            WHERE employee_id = %s OR employee_name = %s
            ORDER BY created_at DESC LIMIT 1
        """, (emp_id, emp_name))
        
        if not req:
            return jsonify({
                "success": True, 
                "case": None,
                "employee": emp,
                "assigned_assets": assigned_assets,
                "active_employees": active_employees
            })
            
        case_data = service.get_offboarding_case_details(req['id'])
        return jsonify({
            "success": True, 
            "case": case_data,
            "employee": emp,
            "assigned_assets": assigned_assets,
            "active_employees": active_employees
        })
    except Exception as e:
        logger.error(f"Error fetching my case: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Cases Listing & Detail
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases', methods=['GET'])
@token_required
def list_cases(current_user):
    try:
        user_role = current_user.get('role', 'employee')
        user_id = current_user.get('user_id')
        user_name = current_user.get('employee_name')
        
        cases = service.get_offboarding_cases(user_role, user_id, user_name)
        return jsonify({"success": True, "cases": cases})
    except Exception as e:
        logger.error(f"Error listing offboarding cases: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_bp.route('/cases/<int:id>', methods=['GET'])
@token_required
def get_case(current_user, id):
    try:
        case_data = service.get_offboarding_case_details(id)
        if not case_data:
            return jsonify({"success": False, "error": "Offboarding case not found"}), 404
        
        # Security check: employee can only see their own case
        user_role = current_user.get('role', 'employee')
        if user_role not in ('hr', 'admin', 'superadmin', 'manager', 'system_admin'):
            if case_data['request']['employee_name'] != current_user.get('employee_name'):
                return jsonify({"success": False, "error": "Access denied"}), 403

        return jsonify({"success": True, "case": case_data})
    except Exception as e:
        logger.error(f"Error fetching case detail: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Manager Approval / Rejection
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases/<int:id>/manager-review', methods=['POST'])
@role_required(['manager', 'admin', 'hr', 'superadmin'])
def manager_review(current_user, id):
    # Guardrail: System Admin MUST NOT approve resignations
    if current_user.get('role') == 'system_admin':
        return jsonify({"success": False, "error": "System Admin is not authorized to approve resignations."}), 403

    data = request.get_json() or {}
    decision = (data.get('decision') or '').upper()
    rejection_reason = data.get('rejection_reason')
    
    try:
        service.manager_approval_decision(
            offboarding_id=id,
            manager_id=current_user.get('user_id'),
            manager_name=current_user.get('employee_name'),
            decision=decision,
            rejection_reason=rejection_reason
        )
        return jsonify({
            "success": True,
            "message": f"Resignation request has been {decision.lower()} successfully."
        })
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error processing manager review: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Employee Consent Form
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases/<int:id>/consent', methods=['POST'])
@token_required
def submit_consent(current_user, id):
    data = request.get_json() or {}
    try:
        from app.models.database import execute_single
        emp = execute_single("SELECT id FROM employee WHERE name = %s OR email = %s", (current_user.get('employee_name'), current_user.get('username')))
        emp_id = emp['id'] if emp else current_user.get('user_id')

        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        service.submit_employee_consent(id, emp_id, data, ip_address=ip_addr)
        return jsonify({"success": True, "message": "Offboarding consent submitted successfully."})
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error submitting consent: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Knowledge Transfer
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases/<int:id>/knowledge-transfer', methods=['POST'])
@role_required(['manager', 'hr', 'admin', 'superadmin'])
def update_kt(current_user, id):
    data = request.get_json() or {}
    try:
        service.update_knowledge_transfer(id, current_user.get('employee_name'), data)
        return jsonify({"success": True, "message": "Knowledge transfer details updated successfully."})
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error updating KT: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Asset Return
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases/<int:id>/assets', methods=['GET'])
@token_required
def get_assets(current_user, id):
    try:
        devices = service.get_offboarding_assets(id)
        return jsonify({"success": True, "assets": devices})
    except Exception as e:
        logger.error(f"Error fetching offboarding assets: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_bp.route('/cases/<int:id>/assets/<int:device_id>/return', methods=['POST'])
@role_required(['hr', 'admin', 'superadmin'])
def return_asset(current_user, id, device_id):
    data = request.get_json() or {}
    return_status = data.get('return_status', 'Returned')
    condition = data.get('condition')
    remarks = data.get('remarks')

    try:
        result = service.return_offboarding_asset(
            offboarding_id=id,
            device_id=device_id,
            return_status=return_status,
            condition=condition,
            remarks=remarks,
            user_name=current_user.get('employee_name')
        )
        return jsonify({"success": True, "message": "Asset status updated successfully.", "result": result})
    except Exception as e:
        logger.error(f"Error returning asset: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# System Admin IT Access & Deactivation
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases/<int:id>/it-access', methods=['GET'])
@role_required(['system_admin', 'admin', 'superadmin', 'hr'])
def get_it_access(current_user, id):
    try:
        details = service.get_it_access_details(id)
        return jsonify({"success": True, "data": details})
    except Exception as e:
        logger.error(f"Error fetching IT access: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_bp.route('/cases/<int:id>/it-access/<system_name>', methods=['PATCH'])
@role_required(['system_admin', 'admin', 'superadmin'])
def update_it_system(current_user, id, system_name):
    data = request.get_json() or {}
    status = data.get('access_status', 'REVOKED')
    notes = data.get('notes')

    try:
        service.update_it_system_status(id, system_name, status, notes=notes, user_name=current_user.get('employee_name'))
        return jsonify({"success": True, "message": f"{system_name} access marked as {status}."})
    except Exception as e:
        logger.error(f"Error updating IT system: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_bp.route('/cases/<int:id>/it-deactivation', methods=['POST'])
@role_required(['system_admin', 'admin', 'superadmin'])
def perform_it_deactivation(current_user, id):
    data = request.get_json() or {}
    checklist = data.get('checklist') or {}
    notes = data.get('notes')

    try:
        service.perform_it_deactivation(
            offboarding_id=id,
            user_name=current_user.get('employee_name'),
            actions_dict=checklist,
            notes=notes
        )
        return jsonify({"success": True, "message": "Corporate account disabled and system access revoked successfully."})
    except Exception as e:
        logger.error(f"Error performing IT deactivation: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# HR Final Clearance
# ---------------------------------------------------------------------------

@offboarding_bp.route('/cases/<int:id>/hr-clearance', methods=['POST'])
@role_required(['hr', 'admin', 'superadmin'])
def hr_clearance(current_user, id):
    # Guardrail: System Admin MUST NOT complete HR clearance
    if current_user.get('role') == 'system_admin':
        return jsonify({"success": False, "error": "System Admin is not authorized to complete HR clearances."}), 403

    try:
        service.complete_hr_final_clearance(id, current_user.get('employee_name'))
        return jsonify({"success": True, "message": "Final HR clearance completed. Employee is now offboarded."})
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error completing HR clearance: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# HR Dashboard Metrics
# ---------------------------------------------------------------------------

@offboarding_bp.route('/metrics', methods=['GET'])
@role_required(['hr', 'admin', 'superadmin'])
def get_metrics(current_user):
    try:
        metrics = service.get_hr_dashboard_metrics()
        return jsonify({"success": True, "metrics": metrics})
    except Exception as e:
        logger.error(f"Error fetching offboarding metrics: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
