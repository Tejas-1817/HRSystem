from app.models.database import get_connection, execute_query, execute_single, Transaction
from flask import Blueprint, request, jsonify
from app.api.middleware.auth import token_required, role_required
from app.utils.helpers import generate_project_id
from app.services.billing_service import sync_employee_status

project_bp = Blueprint('projects', __name__)


def _manager_join_clause():
    # users table is the source of truth for manager identity (id + employee_name)
    return """
        LEFT JOIN users um
          ON um.employee_name = p.manager_name
    """


def _project_select_columns():
    return """
        p.*,
        um.id AS assigned_manager_id,
        COALESCE(um.employee_name, p.manager_name) AS assigned_manager_name
    """


def _resolve_manager_name_from_payload(data):
    """
    Supports either:
      - assigned_manager_id (preferred)
      - manager_name / assigned_manager_name (backward compatible)
    Returns a validated manager employee_name or None.
    """
    assigned_manager_id = data.get("assigned_manager_id")
    manager_name = data.get("manager_name") or data.get("assigned_manager_name")

    if assigned_manager_id not in (None, ""):
        manager = execute_single(
            "SELECT id, employee_name FROM users WHERE id=%s AND role IN ('manager', 'hr')",
            (assigned_manager_id,),
        )
        if not manager:
            raise ValueError("Invalid assigned_manager_id. Manager not found.")
        return manager["employee_name"]

    if manager_name:
        manager = execute_single(
            "SELECT id, employee_name FROM users WHERE employee_name=%s AND role IN ('manager', 'hr')",
            (manager_name,),
        )
        if not manager:
            raise ValueError(f"Invalid manager name '{manager_name}'. User must be HR or Manager.")
        return manager["employee_name"]

    return None


@project_bp.route("/", methods=["GET"])
@token_required
def view_projects(current_user):
    """
    Fetch projects based on role:
    - HR: All projects
    - Manager: Projects they manage OR are assigned to
    - Employee: Projects they are assigned to

    Includes manager identity fields for UI edit flows:
    - assigned_manager_id
    - assigned_manager_name
    """
    try:
        search_id = request.args.get("project_id")
        select_cols = _project_select_columns()
        manager_join = _manager_join_clause()

        if current_user["role"] == "hr":
            if search_id:
                rows = execute_query(
                    f"""
                    SELECT {select_cols}
                    FROM projects p
                    {manager_join}
                    WHERE p.project_id LIKE %s
                    """,
                    (f"%{search_id}%",),
                )
            else:
                rows = execute_query(
                    f"""
                    SELECT {select_cols}
                    FROM projects p
                    {manager_join}
                    """
                )

        elif current_user["role"] == "manager":
            # Managers see projects they direct OR projects where they are team members
            if search_id:
                rows = execute_query(
                    f"""
                    SELECT DISTINCT {select_cols}
                    FROM projects p
                    LEFT JOIN project_assignments pa ON p.id = pa.project_id
                    {manager_join}
                    WHERE (p.manager_name = %s OR pa.employee_name = %s)
                      AND p.project_id LIKE %s
                    """,
                    (current_user["employee_name"], current_user["employee_name"], f"%{search_id}%"),
                )
            else:
                rows = execute_query(
                    f"""
                    SELECT DISTINCT {select_cols}
                    FROM projects p
                    LEFT JOIN project_assignments pa ON p.id = pa.project_id
                    {manager_join}
                    WHERE p.manager_name = %s OR pa.employee_name = %s
                    """,
                    (current_user["employee_name"], current_user["employee_name"]),
                )

        else:
            # Employees see ONLY projects where they are explicitly assigned
            if search_id:
                rows = execute_query(
                    f"""
                    SELECT DISTINCT {select_cols}
                    FROM projects p
                    INNER JOIN project_assignments pa ON p.id = pa.project_id
                    {manager_join}
                    WHERE pa.employee_name = %s AND p.project_id LIKE %s
                    """,
                    (current_user["employee_name"], f"%{search_id}%"),
                )
            else:
                rows = execute_query(
                    f"""
                    SELECT DISTINCT {select_cols}
                    FROM projects p
                    INNER JOIN project_assignments pa ON p.id = pa.project_id
                    {manager_join}
                    WHERE pa.employee_name = %s
                    """,
                    (current_user["employee_name"],),
                )

        return jsonify({"success": True, "projects": rows}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@project_bp.route("/<int:project_id>", methods=["GET"])
@token_required
def get_project(current_user, project_id):
    """Fetch details of a single project, including team members and assigned manager fields."""
    try:
        select_cols = _project_select_columns()
        manager_join = _manager_join_clause()

        if current_user["role"] == "manager":
            row = execute_single(
                f"""
                SELECT DISTINCT {select_cols}
                FROM projects p
                LEFT JOIN project_assignments pa ON p.id = pa.project_id
                {manager_join}
                WHERE p.id = %s AND (p.manager_name = %s OR pa.employee_name = %s)
                """,
                (project_id, current_user["employee_name"], current_user["employee_name"]),
            )

        elif current_user["role"] == "employee":
            row = execute_single(
                f"""
                SELECT {select_cols}
                FROM projects p
                JOIN project_assignments pa ON p.id = pa.project_id
                {manager_join}
                WHERE p.id=%s AND pa.employee_name=%s
                """,
                (project_id, current_user["employee_name"]),
            )

        else:
            row = execute_single(
                f"""
                SELECT {select_cols}
                FROM projects p
                {manager_join}
                WHERE p.id=%s
                """,
                (project_id,),
            )

        if row:
            row["team_members"] = execute_query(
                "SELECT employee_name, assigned_by, assigned_at FROM project_assignments WHERE project_id=%s",
                (project_id,),
            )
            return jsonify({"success": True, "project": row}), 200

        return jsonify({"success": False, "error": "Project not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@project_bp.route("/", methods=["POST"])
@role_required(["hr"])
def add_project(current_user):
    """Create a new project (HR only)."""
    try:
        data = request.get_json()
        if not data or "name" not in data:
            return jsonify({"success": False, "error": "Missing required field: name"}), 400

        # Validate manager (can be role='manager' or role='hr')
        manager_name = _resolve_manager_name_from_payload(data)

        conn = get_connection()
        cursor = conn.cursor()
        project_id_str = generate_project_id(cursor)
        cursor.execute(
            """
            INSERT INTO projects (project_id, name, project_type, status, manager_name, customer_name, contact_person, phone, email, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project_id_str,
                data.get("name"),
                data.get("project_type", "fixed"),
                data.get("status", "ongoing"),
                manager_name,
                data.get("customer_name"),
                data.get("contact_person"),
                data.get("phone"),
                data.get("email"),
                data.get("start_date"),
                data.get("end_date"),
            ),
        )
        conn.commit()
        internal_id = cursor.lastrowid
        return jsonify({
            "success": True, 
            "message": "Project added", 
            "project_id": project_id_str,
            "id": internal_id
        }), 201

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if "conn" in locals():
            conn.close()


@project_bp.route("/<int:project_id>", methods=["PUT"])
@role_required(["hr", "manager"])
def update_project(current_user, project_id):
    """
    Update an existing project.
    - HR can update all fields, including manager assignment.
    - Manager can update non-manager details for only their own projects.
    """
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No fields provided for update"}), 400

        project = execute_single("SELECT * FROM projects WHERE id=%s", (project_id,))
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404

        if current_user["role"] == "manager" and project["manager_name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied. You can only update your own projects."}), 403

        # Managers cannot reassign project manager.
        if current_user["role"] == "manager" and (
            "assigned_manager_id" in data or "manager_name" in data or "assigned_manager_name" in data
        ):
            return jsonify({"success": False, "error": "Only HR can change project manager assignment."}), 403

        manager_name = project.get("manager_name")
        if current_user["role"] == "hr":
            resolved = _resolve_manager_name_from_payload(data)
            if "assigned_manager_id" in data or "manager_name" in data or "assigned_manager_name" in data:
                manager_name = resolved

        update_fields = {
            "name": data.get("name", project.get("name")),
            "project_type": data.get("project_type", project.get("project_type", "fixed")),
            "status": data.get("status", project.get("status")),
            "manager_name": manager_name,
            "customer_name": data.get("customer_name", project.get("customer_name")),
            "contact_person": data.get("contact_person", project.get("contact_person")),
            "phone": data.get("phone", project.get("phone")),
            "email": data.get("email", project.get("email")),
            "start_date": data.get("start_date", project.get("start_date")),
            "end_date": data.get("end_date", project.get("end_date")),
        }

        execute_query(
            """
            UPDATE projects
            SET name=%s, project_type=%s, status=%s, manager_name=%s, customer_name=%s,
                contact_person=%s, phone=%s, email=%s, start_date=%s, end_date=%s
            WHERE id=%s
            """,
            (
                update_fields["name"],
                update_fields["project_type"],
                update_fields["status"],
                update_fields["manager_name"],
                update_fields["customer_name"],
                update_fields["contact_person"],
                update_fields["phone"],
                update_fields["email"],
                update_fields["start_date"],
                update_fields["end_date"],
                project_id,
            ),
            commit=True,
        )

        refreshed = execute_single(
            f"""
            SELECT {_project_select_columns()}
            FROM projects p
            {_manager_join_clause()}
            WHERE p.id=%s
            """,
            (project_id,),
        )

        return jsonify({"success": True, "message": "Project updated", "project": refreshed}), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@project_bp.route("/assign", methods=["POST"])
@role_required(["hr", "manager"])
def assign_employee(current_user):
    """Assign an employee to a project (HR and Managers only)."""
    try:
        data = request.get_json()
        required = ("project_id", "employee_name")
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": "Missing project_id or employee_name"}), 400

        # Verify the project exists
        project = execute_single("SELECT id FROM projects WHERE id=%s", (data["project_id"],))
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404

        # Managers can only assign to their own projects
        if current_user["role"] == "manager":
            proj_data = execute_single("SELECT manager_name FROM projects WHERE id=%s", (data["project_id"],))
            if proj_data["manager_name"] != current_user["employee_name"]:
                return jsonify({"success": False, "error": "Access denied. You can only manage assignments for your own projects."}), 403

        billable_pct = int(data.get("billable_percentage", 100))
        
        # 1. Fetch employee allocation config
        emp = execute_single("SELECT allow_over_allocation FROM employee WHERE name=%s", (data["employee_name"],))
        if not emp:
            return jsonify({"success": False, "error": "Employee not found"}), 404
        
        # 2. Calculate current total allocation
        current_total = execute_single(
            "SELECT SUM(billable_percentage) as total FROM project_assignments WHERE employee_name=%s",
            (data["employee_name"],)
        )["total"] or 0
        
        projected_total = current_total + billable_pct
        
        # 3. Apply Over-allocation rules
        if projected_total > 100:
            if not emp["allow_over_allocation"]:
                return jsonify({
                    "success": False,
                    "error": f"Allocation exceeds 100% ({projected_total}%). Over-allocation is not enabled for this employee.",
                    "current_total": current_total
                }), 400
            
            if projected_total > 150:
                return jsonify({
                    "success": False, 
                    "error": f"Allocation exceeds 150% hard cap ({projected_total}%). Assignment denied."
                }), 400
            
            # Log over-allocation event
            execute_query(
                "INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)",
                (current_user["user_id"], "over_allocation_alert", f"Employee {data['employee_name']} assigned to {projected_total}% capacity (Project ID: {data['project_id']})"),
                commit=True
            )

        with Transaction() as cursor:
            execute_query(
                """
                INSERT INTO project_assignments (project_id, employee_name, is_billable, billable_percentage, assigned_by)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    is_billable = VALUES(is_billable),
                    billable_percentage = VALUES(billable_percentage),
                    assigned_by = VALUES(assigned_by)
                """,
                (
                    data["project_id"], 
                    data["employee_name"], 
                    data.get("is_billable", True), 
                    billable_pct,
                    current_user["employee_name"]
                ),
                cursor=cursor
            )
            
            # Sync employee status to 'working'
            sync_employee_status(data["employee_name"], cursor=cursor)

        return jsonify({"success": True, "message": f"Employee {data['employee_name']} assigned to project"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@project_bp.route("/assign", methods=["DELETE"])
@role_required(["hr", "manager"])
def remove_assignment(current_user):
    """Remove an employee from a project assignment."""
    try:
        data = request.get_json()
        required = ("project_id", "employee_name")
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": "Missing project_id or employee_name"}), 400

        # Managers can only remove from their own projects
        if current_user["role"] == "manager":
            proj_data = execute_single("SELECT manager_name FROM projects WHERE id=%s", (data["project_id"],))
            if proj_data["manager_name"] != current_user["employee_name"]:
                return jsonify({"success": False, "error": "Access denied. You can only manage assignments for your own projects."}), 403

        with Transaction() as cursor:
            execute_query(
                "DELETE FROM project_assignments WHERE project_id=%s AND employee_name=%s",
                (data["project_id"], data["employee_name"]),
                cursor=cursor
            )
            # Sync employee status (may revert to 'bench' if no other projects exist)
            sync_employee_status(data["employee_name"], cursor=cursor)

        return jsonify({"success": True, "message": "Assignment removed"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@project_bp.route("/assign", methods=["PUT"])
@role_required(["hr", "manager"])
def update_assignment(current_user):
    """
    Update billable status or percentage for an existing assignment.
    """
    try:
        data = request.get_json()
        required = ("project_id", "employee_name")
        if not all(k in data for k in required):
            return jsonify({"success": False, "error": "Missing project_id or employee_name"}), 400

        # Verify management rights
        if current_user["role"] == "manager":
            proj_data = execute_single("SELECT manager_name FROM projects WHERE id=%s", (data["project_id"],))
            if not proj_data or proj_data["manager_name"] != current_user["employee_name"]:
                return jsonify({"success": False, "error": "Access denied. You can only manage assignments for your own projects."}), 403

        billable_pct = data.get("billable_percentage")
        if billable_pct is not None:
            billable_pct = int(billable_pct)
            
            # 1. Fetch employee allocation config
            emp = execute_single("SELECT allow_over_allocation FROM employee WHERE name=%s", (data["employee_name"],))
            
            # 2. Calculate projected total (sum of others + this one)
            other_total = execute_single(
                "SELECT SUM(billable_percentage) as total FROM project_assignments WHERE employee_name=%s AND project_id != %s",
                (data["employee_name"], data["project_id"])
            )["total"] or 0
            
            projected_total = other_total + billable_pct
            
            if projected_total > 100:
                if not emp["allow_over_allocation"]:
                    return jsonify({
                        "success": False,
                        "error": f"Update fails: total allocation would reach {projected_total}%. Enable over-allocation first."
                    }), 400
                if projected_total > 150:
                    return jsonify({"success": False, "error": f"Update fails: total allocation would exceed 150% hard cap ({projected_total}%)."}), 400
                
                # Log over-allocation event
                execute_query(
                    "INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)",
                    (current_user["user_id"], "over_allocation_alert", f"Employee {data['employee_name']} utilization updated to {projected_total}%."),
                    commit=True
                )

        # Build update clause
        updates = []
        params = []
        if "is_billable" in data:
            updates.append("is_billable = %s")
            params.append(data["is_billable"])
        if billable_pct is not None:
            updates.append("billable_percentage = %s")
            params.append(billable_pct)

        if not updates:
            return jsonify({"success": False, "error": "No fields provided for update"}), 400

        params.extend([data["project_id"], data["employee_name"]])
        
        execute_query(
            f"UPDATE project_assignments SET {', '.join(updates)} WHERE project_id=%s AND employee_name=%s",
            tuple(params),
            commit=True
        )

        return jsonify({"success": True, "message": "Assignment updated"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@project_bp.route("/<int:project_id>", methods=["DELETE"])
@role_required(["hr"])
def delete_project(current_user, project_id):
    """
    Delete a project (HR only).
    Cascades to project_assignments and syncs employee statuses.
    """
    try:
        # 1. Verify project exists and get team members for status syncing
        project = execute_single("SELECT name FROM projects WHERE id=%s", (project_id,))
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        assigned_employees = execute_query(
            "SELECT employee_name FROM project_assignments WHERE project_id=%s",
            (project_id,)
        )
        
        with Transaction() as cursor:
            # 2. Delete project (Foreign key ON DELETE CASCADE handles assignments)
            execute_query("DELETE FROM projects WHERE id=%s", (project_id,), cursor=cursor)
            
            # 3. Trigger status sync for all affected employees
            for item in assigned_employees:
                sync_employee_status(item["employee_name"], cursor=cursor)
        
        return jsonify({
            "success": True, 
            "message": f"Project '{project['name']}' deleted successfully and employee statuses synchronized."
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
