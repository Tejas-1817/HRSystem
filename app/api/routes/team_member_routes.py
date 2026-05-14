"""
Team Member API Routes (Modern Terminology)

This module provides REST API endpoints for team member operations using
modern enterprise terminology. All endpoints follow RESTful standards
and return standardized JSON responses.

Base endpoint: /api/v1/team-members
Legacy support: /api/v1/employees (maintained for backward compatibility)

Usage:
    GET    /api/v1/team-members                    - List all team members
    GET    /api/v1/team-members/<id>              - Get team member details
    POST   /api/v1/team-members                    - Create new team member
    PATCH  /api/v1/team-members/<id>              - Update team member
    DELETE /api/v1/team-members/<id>              - Delete team member
"""

from flask import Blueprint, request, jsonify
import os
import re
import logging
from datetime import datetime
from app.config import Config
from app.models.database import execute_query, execute_single, Transaction
from app.api.middleware.auth import token_required, role_required
from app.services.team_member_service import (
    create_team_member_record, 
    update_team_member_role,
    get_team_member,
    get_team_member_by_name,
    list_team_members,
    update_team_member,
    delete_team_member
)
from app.config.terminology import get_message, get_label, get_audit_event
import mysql.connector

logger = logging.getLogger(__name__)
team_member_bp = Blueprint('team_members', __name__, url_prefix='/api/v1/team-members')


# ═════════════════════════════════════════════════════════════════════════
# SERIALIZERS (Modern Terminology)
# ═════════════════════════════════════════════════════════════════════════

def serialize_team_member(rows):
    """
    Convert database records to API response format with modern terminology.
    
    Maps snake_case database fields to camelCase JSON fields and formats
    data types for API consumption (dates as ISO strings, decimals as floats, etc.).
    """
    if not rows: 
        return rows
    
    is_list = isinstance(rows, list)
    items = rows if is_list else [rows]
    
    for item in items:
        # ─────────────────────────────────────────────────────────────────
        # Date Fields → ISO String + camelCase aliases
        # ─────────────────────────────────────────────────────────────────
        date_fields = [
            ("date_of_birth", "birthDate"),
            ("date_of_joining", "joiningDate"),
            ("created_at", "createdAt"),
            ("updated_at", "updatedAt"),
            ("deleted_at", "deletedAt")
        ]
        for snake, camel in date_fields:
            if item.get(snake):
                val = str(item[snake])
                item[snake] = val
                item[camel] = val
        
        # ─────────────────────────────────────────────────────────────────
        # Numeric Fields → Float/Int + camelCase aliases
        # ─────────────────────────────────────────────────────────────────
        numeric_fields = [
            ("salary", "salary", float),
            ("total_leaves", "totalLeaves", float),
            ("used_leaves", "usedLeaves", float),
            ("remaining_leaves", "remainingLeaves", float),
            ("total_utilization", "totalUtilization", float),
            ("remaining_availability", "remainingAvailability", float),
            ("billable_percentage", "billablePercentage", int)
        ]
        for snake, camel, type_fn in numeric_fields:
            if item.get(snake) is not None:
                try:
                    val = type_fn(item[snake])
                    item[snake] = val
                    item[camel] = val
                except (ValueError, TypeError):
                    pass  # Skip conversion if invalid
        
        # ─────────────────────────────────────────────────────────────────
        # Boolean Fields → camelCase aliases
        # ─────────────────────────────────────────────────────────────────
        if "allow_over_allocation" in item:
            val = bool(item["allow_over_allocation"])
            item["allow_over_allocation"] = val
            item["allowOverAllocation"] = val
        
        # ─────────────────────────────────────────────────────────────────
        # Photo URL Field
        # ─────────────────────────────────────────────────────────────────
        photo = item.get("photo")
        item["photo_url"] = photo if photo else None
    
    return items if is_list else items[0]


# ═════════════════════════════════════════════════════════════════════════
# API ENDPOINTS (Team Member)
# ═════════════════════════════════════════════════════════════════════════

@team_member_bp.route("", methods=["GET"])
@token_required
def list_all_team_members(current_user):
    """
    List all team members with optional filtering.
    
    Query Parameters:
        role: Filter by role (admin, hr, manager, team_member)
        status: Filter by status (working, bench, over_allocated)
        limit: Results per page (default: 100)
        offset: Pagination offset (default: 0)
    
    Returns:
        List of team member records
    """
    try:
        # Only HR/Admin can list all team members
        if current_user.get("role") not in ["hr", "admin"]:
            return jsonify({
                "success": False,
                "error": get_message("permissions_denied", entity_plural=get_label("entity_plural"))
            }), 403
        
        role_filter = request.args.get("role")
        status_filter = request.args.get("status")
        limit = request.args.get("limit", default=100, type=int)
        offset = request.args.get("offset", default=0, type=int)
        
        team_members = list_team_members(
            role_filter=role_filter,
            status_filter=status_filter,
            limit=limit,
            offset=offset
        )
        
        team_members = serialize_team_member(team_members)
        
        return jsonify({
            "success": True,
            "count": len(team_members) if team_members else 0,
            "data": team_members
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing team members: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@team_member_bp.route("/<int:team_member_id>", methods=["GET"])
@token_required
def get_single_team_member(current_user, team_member_id):
    """
    Get details for a specific team member.
    
    Path Parameters:
        team_member_id: Database ID of the team member
    
    Returns:
        Team member record with all details
    """
    try:
        team_member = get_team_member(team_member_id)
        
        if not team_member:
            return jsonify({
                "success": False,
                "error": get_message("not_found_with_id", id=team_member_id)
            }), 404
        
        # Authorization: Users can only view their own profile or HR/Admin can view all
        if current_user.get("role") not in ["hr", "admin"] and \
           current_user.get("employee_name") != team_member.get("name"):
            return jsonify({
                "success": False,
                "error": get_message("permissions_denied", entity_plural=get_label("entity_plural"))
            }), 403
        
        team_member = serialize_team_member(team_member)
        
        return jsonify({
            "success": True,
            "data": team_member
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching team member {team_member_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@team_member_bp.route("", methods=["POST"])
@role_required(["hr", "admin"])
def create_new_team_member(current_user):
    """
    Create a new team member.
    
    Request Body:
        name: Full name of the team member (required)
        email: Email address (required, unique)
        phone: Phone number (optional)
        salary: Salary amount (optional)
        date_of_birth: DOB in YYYY-MM-DD format (optional)
        date_of_joining: DOJ in YYYY-MM-DD format (optional)
        role: User role (admin, hr, manager, team_member) (default: team_member)
    
    Returns:
        Newly created team member record
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400
        
        # Validate required fields
        if not data.get("name"):
            return jsonify({
                "success": False,
                "error": get_message("required_field", field="Name")
            }), 400
        
        if not data.get("email"):
            return jsonify({
                "success": False,
                "error": get_message("required_field", field="Email")
            }), 400
        
        role = data.get("role", "team_member")
        
        with Transaction() as cursor:
            try:
                team_member_id, original_name = create_team_member_record(data, role, cursor)
            except ValueError as ve:
                return jsonify({"success": False, "error": str(ve)}), 400
        
        # Fetch and return the created record
        team_member = get_team_member_by_name(team_member_id)
        team_member = serialize_team_member(team_member)
        
        return jsonify({
            "success": True,
            "message": get_message("created_with_name", name=original_name),
            "data": team_member
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating team member: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@team_member_bp.route("/<int:team_member_id>", methods=["PATCH"])
@role_required(["hr", "admin"])
def update_single_team_member(current_user, team_member_id):
    """
    Update team member information.
    
    Path Parameters:
        team_member_id: Database ID of the team member
    
    Request Body:
        email: New email (optional)
        phone: New phone (optional)
        salary: New salary (optional)
        date_of_birth: New DOB (optional)
        date_of_joining: New DOJ (optional)
    
    Returns:
        Updated team member record
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400
        
        updated_team_member = update_team_member(team_member_id, data)
        updated_team_member = serialize_team_member(updated_team_member)
        
        return jsonify({
            "success": True,
            "message": get_message("updated_success"),
            "data": updated_team_member
        }), 200
        
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error updating team member {team_member_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@team_member_bp.route("/<int:team_member_id>", methods=["DELETE"])
@role_required(["admin"])
def delete_single_team_member(current_user, team_member_id):
    """
    Delete a team member (soft delete for audit trail).
    
    Path Parameters:
        team_member_id: Database ID of the team member
    
    Returns:
        Success confirmation
    """
    try:
        result = delete_team_member(team_member_id, current_user.get("user_id"))
        
        return jsonify({
            "success": result["success"],
            "message": result["message"]
        }), 200
        
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error deleting team member {team_member_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@team_member_bp.route("/<int:team_member_id>/role", methods=["PATCH"])
@role_required(["admin"])
def update_team_member_role_endpoint(current_user, team_member_id):
    """
    Update a team member's role (admin-only operation).
    
    Path Parameters:
        team_member_id: Database ID of the team member
    
    Request Body:
        role: New role (admin, hr, manager, team_member) (required)
    
    Returns:
        Success confirmation with role change details
    """
    try:
        data = request.get_json()
        
        if not data or "role" not in data:
            return jsonify({
                "success": False,
                "error": get_message("required_field", field="role")
            }), 400
        
        new_role = data["role"]
        
        result = update_team_member_role(current_user.get("user_id"), team_member_id, new_role)
        
        return jsonify(result), 200 if result["success"] else 400
        
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error updating team member role for {team_member_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@team_member_bp.route("/<int:team_member_id>/allocation-config", methods=["PATCH"])
@role_required(["hr", "manager"])
def update_allocation_config(current_user, team_member_id):
    """
    Allow HR/Managers to enable/disable over-allocation for a team member.
    """
    try:
        data = request.get_json()
        if "allow_over_allocation" not in data:
            return jsonify({"success": False, "error": get_message("required_field", field="allow_over_allocation")}), 400
        
        allow_val = bool(data["allow_over_allocation"])
        
        # 1. Fetch team member to check existence
        team_member = execute_single("SELECT name FROM employee WHERE id = %s", (team_member_id,))
        if not team_member:
            return jsonify({"success": False, "error": get_message("not_found")}), 404
        
        # 2. Update config
        execute_query(
            "UPDATE employee SET allow_over_allocation = %s WHERE id = %s",
            (allow_val, team_member_id),
            commit=True
        )
        
        # 3. Audit Logging
        execute_query(
            "INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)",
            (current_user["user_id"], "config_change", 
             f"HR/Manager {current_user['employee_name']} {'enabled' if allow_val else 'disabled'} over-allocation for {team_member['name']}"),
            commit=True
        )
        
        return jsonify({
            "success": True, 
            "message": get_message("updated_success"),
            "allow_over_allocation": allow_val
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating allocation config for {team_member_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
