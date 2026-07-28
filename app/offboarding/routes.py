from flask import Blueprint, request, jsonify
from app.offboarding import service
from app.api.middleware.auth import token_required, role_required

offboarding_bp = Blueprint('offboarding', __name__)

@offboarding_bp.route('/', methods=['POST'])
@role_required(['hr'])
def initiate(current_user):
    data = request.json
    try:
        req_id = service.initiate_offboarding(
            data['employee_id'], 
            data['employee_name'], 
            data['reason'], 
            data.get('reason_notes'), 
            data['last_working_day'], 
            current_user.get('user_id'), 
            current_user.get('employee_name')
        )
        return jsonify({"success": True, "offboarding_id": req_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@offboarding_bp.route('/', methods=['GET'])
@role_required(['hr', 'manager', 'accounts'])
def get_all(current_user):
    try:
        data = service.get_offboarding_requests(current_user.get('role'), current_user.get('user_id'))
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@offboarding_bp.route('/<int:id>', methods=['GET'])
@role_required(['hr', 'manager', 'accounts'])
def get_detail(current_user, id):
    try:
        data = service.get_offboarding_details(id)
        if not data:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@offboarding_bp.route('/<int:id>/checklist/<item_type>', methods=['PATCH'])
@role_required(['hr'])
def update_checklist(current_user, id, item_type):
    data = request.json
    try:
        service.update_checklist_item(
            id, 
            item_type, 
            data['status'], 
            data.get('notes'), 
            current_user.get('user_id'), 
            current_user.get('employee_name')
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@offboarding_bp.route('/<int:id>/approve', methods=['POST'])
@role_required(['hr', 'manager', 'accounts'])
def approve(current_user, id):
    data = request.json
    try:
        service.approve_reject(
            id, 
            current_user.get('role'), 
            current_user.get('user_id'), 
            current_user.get('employee_name'), 
            'APPROVED', 
            data.get('comments')
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@offboarding_bp.route('/<int:id>/reject', methods=['POST'])
@role_required(['hr', 'manager', 'accounts'])
def reject(current_user, id):
    data = request.json
    try:
        service.approve_reject(
            id, 
            current_user.get('role'), 
            current_user.get('user_id'), 
            current_user.get('employee_name'), 
            'REJECTED', 
            data.get('comments')
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@offboarding_bp.route('/<int:id>/cancel', methods=['POST'])
@role_required(['hr'])
def cancel(current_user, id):
    try:
        service.cancel_offboarding(id, current_user.get('user_id'), current_user.get('employee_name'))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
