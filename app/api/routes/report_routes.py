from flask import Blueprint, request, jsonify, send_from_directory
import os
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required
from app.services.billing_service import (
    get_utilization_report, 
    get_billing_ratio_report, 
    get_project_revenue_estimation,
    get_over_allocation_report
)

report_bp = Blueprint('reports', __name__)

@report_bp.route("/resource/utilization", methods=["GET"])
@role_required(["hr", "manager"])
def report_utilization(current_user):
    """Report on working vs bench employees."""
    try:
        report = get_utilization_report()
        return jsonify({"success": True, "report": report}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/resource/billing-ratio", methods=["GET"])
@role_required(["hr", "manager"])
def report_billing_ratio(current_user):
    """Billable vs non-billable ratio."""
    try:
        report = get_billing_ratio_report()
        return jsonify({"success": True, "report": report}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/resource/over-allocated", methods=["GET"])
@role_required(["hr", "manager"])
def report_over_allocated(current_user):
    """List of over-allocated resources."""
    try:
        report = get_over_allocation_report()
        return jsonify({"success": True, "report": report}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/resource/project-billing", methods=["GET"])
@role_required(["hr", "manager"])
def report_project_billing(current_user):
    """Project-wise revenue estimation."""
    try:
        report = get_project_revenue_estimation()
        return jsonify({"success": True, "report": report}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/payslips", methods=["GET"])
@token_required
def view_payslips(current_user):
    try:
        if current_user["role"] in ("manager", "hr"):
            rows = execute_query("SELECT id, employee_name, month, year, created_at FROM payslips ORDER BY year DESC, created_at DESC")
        else:
            rows = execute_query("SELECT id, employee_name, month, year, created_at FROM payslips WHERE employee_name=%s ORDER BY year DESC, created_at DESC", (current_user["employee_name"],))
        return jsonify({"success": True, "payslips": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@report_bp.route("/payslips/download/<int:payslip_id>", methods=["GET"])
@token_required
def download_payslip(current_user, payslip_id):
    try:
        row = execute_single("SELECT * FROM payslips WHERE id=%s", (payslip_id,))
        if not row: return jsonify({"success": False, "error": "Payslip not found"}), 404
        if current_user["role"] == "employee" and row["employee_name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        directory = os.path.dirname(row["file_path"])
        filename = os.path.basename(row["file_path"])
        return send_from_directory(directory, filename)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@report_bp.route("/policies", methods=["GET"])
@token_required
def get_policies(current_user):
    try:
        rows = execute_query("SELECT * FROM policies WHERE is_active=TRUE")
        return jsonify({"success": True, "policies": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/policies", methods=["POST"])
@role_required(["hr"])
def add_policy(current_user):
    """Add a new company policy (HR only)."""
    try:
        data = request.get_json()
        required = ("category", "title", "content")
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": "Missing required fields: category, title, or content"}), 400
            
        execute_query("""
            INSERT INTO policies (category, title, content, updated_by)
            VALUES (%s, %s, %s, %s)
        """, (data["category"], data["title"], data["content"], current_user["employee_name"]), commit=True)
        
        return jsonify({"success": True, "message": "Policy added successfully"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/policies/<int:policy_id>", methods=["PUT"])
@role_required(["hr"])
def update_policy(current_user, policy_id):
    """Update an existing policy (HR only)."""
    try:
        data = request.get_json()
        
        # Check if policy exists
        policy = execute_single("SELECT id FROM policies WHERE id=%s", (policy_id,))
        if not policy:
            return jsonify({"success": False, "error": "Policy not found"}), 404

        # Update fields dynamically or provide defaults
        category = data.get("category")
        title = data.get("title")
        content = data.get("content")
        is_active = data.get("is_active", True)

        query = """
            UPDATE policies 
            SET category=COALESCE(%s, category), 
                title=COALESCE(%s, title), 
                content=COALESCE(%s, content), 
                is_active=%s,
                updated_by=%s
            WHERE id=%s
        """
        execute_query(query, (category, title, content, is_active, current_user["employee_name"], policy_id), commit=True)
        
        return jsonify({"success": True, "message": "Policy updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@report_bp.route("/policies/<int:policy_id>", methods=["DELETE"])
@role_required(["hr"])
def delete_policy(current_user, policy_id):
    """Soft-delete a policy by deactivating it (HR only)."""
    try:
        policy = execute_single("SELECT id FROM policies WHERE id=%s", (policy_id,))
        if not policy:
            return jsonify({"success": False, "error": "Policy not found"}), 404

        execute_query("UPDATE policies SET is_active=FALSE, updated_by=%s WHERE id=%s", 
                     (current_user["employee_name"], policy_id), commit=True)
        
        return jsonify({"success": True, "message": "Policy deactivated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
