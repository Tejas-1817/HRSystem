"""
Department & Designation Management API Routes
───────────────────────────────────────────────
REST API endpoints for dynamic department and designation management.
HR/Admin users can create, update, and deactivate departments/designations
for dropdown population without code changes.

Base endpoints:
    /api/v1/departments                - Department CRUD
    /api/v1/designations               - Designation CRUD
    /api/v1/constants                   - Static constants (genders, employment types)

Usage:
    GET    /api/v1/departments              - List all departments
    POST   /api/v1/departments              - Create department (HR/Admin)
    PATCH  /api/v1/departments/<id>         - Update department (HR/Admin)
    DELETE /api/v1/departments/<id>         - Deactivate department (Admin)

    GET    /api/v1/designations             - List all designations
    POST   /api/v1/designations             - Create designation (HR/Admin)
    PATCH  /api/v1/designations/<id>        - Update designation (HR/Admin)
    DELETE /api/v1/designations/<id>        - Deactivate designation (Admin)

    GET    /api/v1/constants                - Get all dropdown constants
"""

from flask import Blueprint, request, jsonify
import logging
from app.api.middleware.auth import token_required, role_required
from app.services.department_service import (
    list_departments, create_department, update_department,
    deactivate_department, get_department,
    list_designations, create_designation, update_designation,
    deactivate_designation, get_designation,
)
from app.config.constants import (
    get_departments_list, get_designations_list,
    get_genders_list, get_employment_types_list,
)

logger = logging.getLogger(__name__)

department_bp = Blueprint('departments', __name__, url_prefix='/api/v1')


# ═════════════════════════════════════════════════════════════════════════
# CONSTANTS ENDPOINT (Read-only dropdown values)
# ═════════════════════════════════════════════════════════════════════════

@department_bp.route("/constants", methods=["GET"])
@token_required
def get_constants(current_user):
    """
    Get all dropdown constants for form population.
    
    Returns static lists of genders, employment types, and
    dynamically managed departments and designations.
    """
    try:
        # Fetch dynamic departments/designations from DB
        db_departments = list_departments(active_only=True)
        db_designations = list_designations(active_only=True)

        # Use DB values if available, fallback to static constants
        departments = [d['name'] for d in db_departments] if db_departments else get_departments_list()
        designations = [d['name'] for d in db_designations] if db_designations else get_designations_list()

        return jsonify({
            "success": True,
            "data": {
                "departments": departments,
                "designations": designations,
                "genders": get_genders_list(),
                "employment_types": get_employment_types_list(),
            }
        }), 200

    except Exception as e:
        logger.error(f"Error fetching constants: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ═════════════════════════════════════════════════════════════════════════
# DEPARTMENT ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@department_bp.route("/departments", methods=["GET"])
@token_required
def list_all_departments(current_user):
    """
    List all departments for dropdown population.
    
    Query Parameters:
        active_only: Filter to active departments only (default: true)
    """
    try:
        active_only = request.args.get("active_only", "true").lower() == "true"
        departments = list_departments(active_only=active_only)

        # Serialize dates to strings
        for dept in (departments or []):
            for field in ('created_at', 'updated_at'):
                if dept.get(field):
                    dept[field] = str(dept[field])

        return jsonify({
            "success": True,
            "count": len(departments) if departments else 0,
            "data": departments or []
        }), 200

    except Exception as e:
        logger.error(f"Error listing departments: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@department_bp.route("/departments", methods=["POST"])
@role_required(["hr", "admin"])
def create_new_department(current_user):
    """
    Create a new department (HR/Admin only).
    
    Request Body:
        name: Department name (required, unique)
        description: Department description (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get("name"):
            return jsonify({
                "success": False,
                "error": "Department name is required"
            }), 400

        department = create_department(
            name=data["name"],
            description=data.get("description"),
            created_by=current_user.get("employee_name")
        )

        # Serialize dates
        if department:
            for field in ('created_at', 'updated_at'):
                if department.get(field):
                    department[field] = str(department[field])

        return jsonify({
            "success": True,
            "message": f"Department '{data['name']}' created successfully",
            "data": department
        }), 201

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error creating department: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@department_bp.route("/departments/<int:department_id>", methods=["PATCH"])
@role_required(["hr", "admin"])
def update_existing_department(current_user, department_id):
    """
    Update a department (HR/Admin only).
    
    Request Body:
        name: New name (optional)
        description: New description (optional)
        is_active: Active status (optional)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        department = update_department(
            department_id=department_id,
            data=data,
            updated_by=current_user.get("employee_name")
        )

        # Serialize dates
        if department:
            for field in ('created_at', 'updated_at'):
                if department.get(field):
                    department[field] = str(department[field])

        return jsonify({
            "success": True,
            "message": "Department updated successfully",
            "data": department
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error updating department {department_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@department_bp.route("/departments/<int:department_id>", methods=["DELETE"])
@role_required(["admin"])
def deactivate_existing_department(current_user, department_id):
    """
    Deactivate a department (Admin only, soft-delete).
    """
    try:
        result = deactivate_department(
            department_id=department_id,
            deactivated_by=current_user.get("employee_name")
        )

        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error deactivating department {department_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ═════════════════════════════════════════════════════════════════════════
# DESIGNATION ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@department_bp.route("/designations", methods=["GET"])
@token_required
def list_all_designations(current_user):
    """
    List all designations for dropdown population.
    
    Query Parameters:
        active_only: Filter to active designations only (default: true)
        department_id: Filter by department (optional)
    """
    try:
        active_only = request.args.get("active_only", "true").lower() == "true"
        department_id = request.args.get("department_id", type=int)
        designations = list_designations(
            active_only=active_only,
            department_id=department_id
        )

        # Serialize dates
        for desig in (designations or []):
            for field in ('created_at', 'updated_at'):
                if desig.get(field):
                    desig[field] = str(desig[field])

        return jsonify({
            "success": True,
            "count": len(designations) if designations else 0,
            "data": designations or []
        }), 200

    except Exception as e:
        logger.error(f"Error listing designations: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@department_bp.route("/designations", methods=["POST"])
@role_required(["hr", "admin"])
def create_new_designation(current_user):
    """
    Create a new designation (HR/Admin only).
    
    Request Body:
        name: Designation title (required, unique)
        department_id: FK to departments table (optional)
        description: Description (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get("name"):
            return jsonify({
                "success": False,
                "error": "Designation name is required"
            }), 400

        designation = create_designation(
            name=data["name"],
            department_id=data.get("department_id"),
            description=data.get("description"),
            created_by=current_user.get("employee_name")
        )

        # Serialize dates
        if designation:
            for field in ('created_at', 'updated_at'):
                if designation.get(field):
                    designation[field] = str(designation[field])

        return jsonify({
            "success": True,
            "message": f"Designation '{data['name']}' created successfully",
            "data": designation
        }), 201

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error creating designation: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@department_bp.route("/designations/<int:designation_id>", methods=["PATCH"])
@role_required(["hr", "admin"])
def update_existing_designation(current_user, designation_id):
    """
    Update a designation (HR/Admin only).
    
    Request Body:
        name: New name (optional)
        department_id: New department FK (optional)
        description: New description (optional)
        is_active: Active status (optional)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        designation = update_designation(
            designation_id=designation_id,
            data=data,
            updated_by=current_user.get("employee_name")
        )

        # Serialize dates
        if designation:
            for field in ('created_at', 'updated_at'):
                if designation.get(field):
                    designation[field] = str(designation[field])

        return jsonify({
            "success": True,
            "message": "Designation updated successfully",
            "data": designation
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error updating designation {designation_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@department_bp.route("/designations/<int:designation_id>", methods=["DELETE"])
@role_required(["admin"])
def deactivate_existing_designation(current_user, designation_id):
    """
    Deactivate a designation (Admin only, soft-delete).
    """
    try:
        result = deactivate_designation(
            designation_id=designation_id,
            deactivated_by=current_user.get("employee_name")
        )

        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error deactivating designation {designation_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
