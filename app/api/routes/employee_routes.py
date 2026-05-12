from flask import Blueprint, request, jsonify
import os
import re
import logging
from datetime import datetime
from app.config import Config
from app.models.database import execute_query, execute_single, Transaction
from app.api.middleware.auth import token_required, role_required
from app.services.employee_service import create_employee_record, update_employee_role
import mysql.connector

logger = logging.getLogger(__name__)
employee_bp = Blueprint('employees', __name__)

def serialize_employee(rows):
    """Convert date, datetime, and decimal fields to serializable formats with camelCase aliases."""
    if not rows: return rows
    is_list = isinstance(rows, list)
    items = rows if is_list else [rows]
    for item in items:
        # Dates to Strings + CamelCase aliases
        date_fields = [("date_of_birth", "birthDate"), ("date_of_joining", "joiningDate"), ("created_at", "createdAt")]
        for snake, camel in date_fields:
            if item.get(snake):
                val = str(item[snake])
                item[snake] = val
                item[camel] = val
        
        # Numbers to Float/Int + CamelCase aliases
        # We keep leaves as int if they have no decimal part, otherwise float
        numeric_fields = [
            ("salary", "salary", float),
            ("total_leaves", "totalLeaves", float),
            ("used_leaves", "usedLeaves", float),
            ("remaining_leaves", "remainingLeaves", float),
            ("total_utilization", "totalUtilization", float),
            ("remaining_availability", "remainingAvailability", float)
        ]
        for snake, camel, type_fn in numeric_fields:
            if item.get(snake) is not None:
                val = type_fn(item[snake])
                item[snake] = val
                item[camel] = val
                
        # Boolean handling
        if "allow_over_allocation" in item:
            val = bool(item["allow_over_allocation"])
            item["allow_over_allocation"] = val
            item["allowOverAllocation"] = val

        # Photo URL: expose as photo_url for frontend consumption
        # The raw 'photo' field stores the relative path (e.g. /uploads/photos/uuid.jpg)
        # which is directly usable as a URL when the backend serves /uploads/
        photo = item.get("photo")
        item["photo_url"] = photo if photo else None
            
    return items if is_list else items[0]


@employee_bp.route("/<int:emp_id>/allocation-config", methods=["PATCH"])
@role_required(["hr", "manager"])
def update_allocation_config(current_user, emp_id):
    """
    Allow HR/Managers to enable/disable over-allocation for an employee.
    """
    try:
        data = request.get_json()
        if "allow_over_allocation" not in data:
            return jsonify({"success": False, "error": "Missing field: allow_over_allocation"}), 400
        
        allow_val = bool(data["allow_over_allocation"])
        
        # 1. Fetch employee to check existence
        employee = execute_single("SELECT name FROM employee WHERE id = %s", (emp_id,))
        if not employee:
            return jsonify({"success": False, "error": "Employee not found"}), 404
        
        # 2. Update config
        execute_query(
            "UPDATE employee SET allow_over_allocation = %s WHERE id = %s",
            (allow_val, emp_id),
            commit=True
        )
        
        # 3. Audit Logging
        execute_query(
            "INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)",
            (current_user["user_id"], "config_change", f"HR/Mgr {current_user['employee_name']} {'enabled' if allow_val else 'disabled'} over-allocation for {employee['name']}"),
            commit=True
        )
        
        return jsonify({
            "success": True, 
            "message": f"Over-allocation configuration updated for {employee['name']}",
            "allow_over_allocation": allow_val
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating allocation config for {emp_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@employee_bp.route("/", methods=["GET"])
@token_required
def view_employees(current_user):
    try:
        if current_user["role"] in ("admin", "manager", "hr"):
            query = """
                SELECT e.*, u.role,
                       COALESCE(lb.total, 0) as total_leaves, 
                       COALESCE(lb.used, 0) as used_leaves, 
                       COALESCE(lb.remaining, 0) as remaining_leaves,
                       COALESCE(util.total_utilization, 0) as total_utilization,
                       GREATEST(0, 100 - COALESCE(util.total_utilization, 0)) as remaining_availability
                FROM employee e
                LEFT JOIN users u ON e.name = u.employee_name
                LEFT JOIN (
                    SELECT employee_name, 
                           SUM(total_leaves) as total, 
                           SUM(used_leaves) as used, 
                           SUM(total_leaves - used_leaves) as remaining
                    FROM leave_balance
                    GROUP BY employee_name
                ) lb ON e.name = lb.employee_name
                LEFT JOIN (
                    SELECT pa.employee_name, SUM(pa.billable_percentage) as total_utilization
                    FROM project_assignments pa
                    JOIN projects p ON pa.project_id = p.id
                    WHERE p.status NOT IN ('completed', 'closed', 'cancelled')
                    GROUP BY pa.employee_name
                ) util ON e.name = util.employee_name
            """
            rows = execute_query(query)
        else:
            query = """
                SELECT e.*, u.role,
                       COALESCE(lb.total, 0) as total_leaves, 
                       COALESCE(lb.used, 0) as used_leaves, 
                       COALESCE(lb.remaining, 0) as remaining_leaves
                FROM employee e
                LEFT JOIN users u ON e.name = u.employee_name
                LEFT JOIN (
                    SELECT employee_name, 
                           SUM(total_leaves) as total, 
                           SUM(used_leaves) as used, 
                           SUM(total_leaves - used_leaves) as remaining
                    FROM leave_balance
                    GROUP BY employee_name
                ) lb ON e.name = lb.employee_name
                WHERE e.name = %s
            """
            rows = execute_query(query, (current_user["employee_name"],))
        from app.services.leave_service import allocate_default_leaves
        # Auto-allocate if missing (common for new employees or legacy data)
        for row in rows:
            if row.get("total_leaves") == 0:
                # Check for actual records
                has_records = execute_single("SELECT 1 FROM leave_balance WHERE employee_name = %s LIMIT 1", (row["name"],))
                if not has_records:
                    allocate_default_leaves(row["name"])
                    # Refresh this row's leave data (simple way)
                    updated_lb = execute_single("""
                        SELECT SUM(total_leaves) as total, SUM(used_leaves) as used, SUM(total_leaves - used_leaves) as remaining
                        FROM leave_balance WHERE employee_name = %s
                    """, (row["name"],))
                    if updated_lb:
                        row["total_leaves"] = updated_lb["total"]
                        row["used_leaves"] = updated_lb["used"]
                        row["remaining_leaves"] = updated_lb["remaining"]

        return jsonify({"success": True, "employees": serialize_employee(rows)}), 200
    except Exception as e:
        logger.error(f"Error fetching employees: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@employee_bp.route("/<int:emp_id>", methods=["GET"])
@token_required
def get_employee(current_user, emp_id):
    try:
        query = """
            SELECT e.*, u.role,
                   COALESCE(lb.total, 0) as total_leaves, 
                   COALESCE(lb.used, 0) as used_leaves, 
                   COALESCE(lb.remaining, 0) as remaining_leaves,
                   COALESCE(util.total_utilization, 0) as total_utilization,
                   GREATEST(0, 100 - COALESCE(util.total_utilization, 0)) as remaining_availability
            FROM employee e
            LEFT JOIN users u ON e.name = u.employee_name
            LEFT JOIN (
                SELECT employee_name, 
                       SUM(total_leaves) as total, 
                       SUM(used_leaves) as used, 
                       SUM(total_leaves - used_leaves) as remaining
                FROM leave_balance
                GROUP BY employee_name
            ) lb ON e.name = lb.employee_name
            LEFT JOIN (
                SELECT pa.employee_name, SUM(pa.billable_percentage) as total_utilization
                FROM project_assignments pa
                JOIN projects p ON pa.project_id = p.id
                WHERE p.status NOT IN ('completed', 'closed', 'cancelled')
                GROUP BY pa.employee_name
            ) util ON e.name = util.employee_name
            WHERE e.id = %s
        """
        row = execute_single(query, (emp_id,))
        if not row: 
            return jsonify({"success": False, "error": "Employee not found"}), 404
        
        if current_user["role"] == "employee" and row["name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        # ── Auto-allocate leaves if missing (graceful fallback) ────────
        if row.get("total_leaves") == 0:
            has_records = execute_single(
                "SELECT 1 FROM leave_balance WHERE employee_name = %s LIMIT 1", 
                (row["name"],)
            )
            if not has_records:
                try:
                    from app.services.leave_service import allocate_default_leaves
                    allocate_default_leaves(row["name"])
                    # Refresh data after allocation
                    updated_lb = execute_single("""
                        SELECT SUM(total_leaves) as total, SUM(used_leaves) as used, 
                               SUM(total_leaves - used_leaves) as remaining
                        FROM leave_balance WHERE employee_name = %s
                    """, (row["name"],))
                    if updated_lb:
                        row["total_leaves"] = updated_lb["total"] or 0
                        row["used_leaves"] = updated_lb["used"] or 0
                        row["remaining_leaves"] = updated_lb["remaining"] or 0
                except Exception as alloc_error:
                    logger.error(f"Failed to allocate leaves for {row['name']}: {alloc_error}")
                    # Don't fail the endpoint — just log it

        return jsonify({"success": True, "employee": serialize_employee(row)}), 200
    except Exception as e:
        logger.error(f"Error fetching employee {emp_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to fetch employee details"}), 500

@employee_bp.route("/", methods=["POST"])
@role_required(["hr"])
def add_employee(current_user):
    try:
        # Support both form-data (multipart) and JSON requests
        if request.content_type and 'json' in request.content_type:
            data = request.get_json(silent=True) or {}

        else:
            data = request.form

        # Collect file paths if any files were uploaded (multipart only)
        # Note: In a production system, these would be saved to a cloud storage (e.g. S3)
        files = {}
        for file_key in ["pdf_file", "docx_file", "photo"]:
            file = request.files.get(file_key)
            if file and file.filename != "":
                file_path = os.path.join(Config.UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                files[f"{file_key}_path"] = file_path
            else:
                files[f"{file_key}_path"] = None

        # Merge data and file paths
        data = {**data, **files}
        role = data.get("role", "employee")

        with Transaction() as cursor:
            # Atomic creation of employee and leaves
            employee_name, original_name = create_employee_record(data, role, cursor)

        from app.services.employee_service import DEFAULT_TEMP_PASSWORD
        username = data.get("email") or data.get("username")
        logger.info(f"HR {current_user['employee_name']} successfully added employee {employee_name} with login: {username}")
        return jsonify({
            "success": True, 
            "message": f"Employee added as {employee_name}. Login username: {username} (Default Password: {DEFAULT_TEMP_PASSWORD})"
        }), 201

    except mysql.connector.IntegrityError as e:
        logger.warning(f"Failed to add employee due to database constraint: {e}")
        return jsonify({"success": False, "error": "An employee with this email or username already exists"}), 409
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error adding employee: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500

@employee_bp.route("/<int:emp_id>", methods=["PUT"])
@role_required(["hr"])
def update_employee(current_user, emp_id):
    """
    HR-only: Update an existing employee's details.

    Accepts JSON body with any subset of editable fields:
    {
      "name":            "Kartik D",        // display name
      "phone":           "9876543210",
      "salary":          75000,
      "date_of_birth":   "1995-06-15",      // YYYY-MM-DD
      "date_of_joining": "2022-01-10",      // YYYY-MM-DD
      "status":          "working"          // working | bench | over_allocated
    }

    Fields NOT accepted (managed separately):
      email, photo, pdf_file, docx_file — handled by dedicated upload endpoints.
    """
    try:
        data = request.get_json(silent=True) or {}

        # ── 1. Verify employee exists ──────────────────────────────────────
        existing = execute_single(
            "SELECT id, name, email FROM employee WHERE id = %s", (emp_id,)
        )
        if not existing:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        # ── 2. Build update query from only the fields provided ───────────
        ALLOWED_FIELDS = {
            "name", "phone", "salary",
            "date_of_birth", "date_of_joining", "status", "email",
        }

        VALID_STATUSES = {"working", "bench", "over_allocated"}

        updates = {}
        for field in ALLOWED_FIELDS:
            if field in data:
                updates[field] = data[field]

        if not updates:
            return jsonify({
                "success": False,
                "error":   "No updatable fields provided. Accepted: name, phone, email, "
                           "salary, date_of_birth, date_of_joining, status."
            }), 400

        # ── 3. Field-level validation ──────────────────────────────────────
        if "status" in updates and updates["status"] not in VALID_STATUSES:
            return jsonify({
                "success": False,
                "error":   f"Invalid status '{updates['status']}'. "
                           f"Use: {', '.join(sorted(VALID_STATUSES))}"
            }), 400

        if "salary" in updates:
            try:
                updates["salary"] = float(updates["salary"])
                if updates["salary"] < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error":   "salary must be a non-negative number."
                }), 400

        for date_field in ("date_of_birth", "date_of_joining"):
            if date_field in updates:
                try:
                    datetime.strptime(updates[date_field], "%Y-%m-%d")
                except (TypeError, ValueError):
                    return jsonify({
                        "success": False,
                        "error":   f"{date_field} must be in YYYY-MM-DD format."
                    }), 400

        if "name" in updates:
            name_val = str(updates["name"]).strip()
            if not name_val:
                return jsonify({"success": False, "error": "name cannot be empty."}), 400
            updates["name"] = name_val

        if "phone" in updates and updates["phone"]:
            phone_val = str(updates["phone"]).strip()
            if not re.match(r"^\+?[\d\s\-]{7,15}$", phone_val):
                return jsonify({
                    "success": False,
                    "error":   "phone must be a valid phone number (7–15 digits)."
                }), 400
            updates["phone"] = phone_val

        # ── Email: format + uniqueness validation ──────────────────────────
        if "email" in updates:
            email_val = str(updates["email"]).strip().lower()

            # 1. Format check
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_val):
                return jsonify({
                    "success": False,
                    "error":   "Invalid email format. Please provide a valid email address."
                }), 400

            # 2. Uniqueness check in employee table
            conflict_emp = execute_single(
                "SELECT id FROM employee WHERE email = %s AND id != %s",
                (email_val, emp_id)
            )
            if conflict_emp:
                return jsonify({
                    "success": False,
                    "error":   f"Email '{email_val}' is already registered to another employee."
                }), 409

            # 3. Uniqueness check in users table (username = email)
            conflict_user = execute_single(
                "SELECT id FROM users WHERE username = %s",
                (email_val,)
            )
            # Allow if the conflict is the same employee's own user account
            own_user = execute_single(
                "SELECT id FROM users WHERE username = %s AND employee_name = %s",
                (existing["email"], existing["name"])
            )
            if conflict_user and (not own_user or conflict_user["id"] != own_user["id"]):
                return jsonify({
                    "success": False,
                    "error":   f"Email '{email_val}' is already in use as a login username."
                }), 409

            updates["email"] = email_val

        # ── 4. Execute UPDATE ──────────────────────────────────────────────
        set_clause = ", ".join(f"{col} = %s" for col in updates)
        values     = list(updates.values()) + [emp_id]

        execute_query(
            f"UPDATE employee SET {set_clause} WHERE id = %s",
            tuple(values),
            commit=True
        )

        # ── 5. Sync name change into dependent tables ──────────────────────
        old_name  = existing["name"]
        old_email = existing["email"]
        new_name  = updates.get("name")
        new_email = updates.get("email")

        # 5a. Cascade name rename across all dependent tables
        if new_name and new_name != old_name:
            for table in (
                "users", "leave_balance", "leaves", "timesheets",
                "attendance", "notifications", "project_assignments",
                "bank_details", "employee_documents", "payslips",
                "helpdesk_tickets",
            ):
                try:
                    execute_query(
                        f"UPDATE {table} SET employee_name = %s WHERE employee_name = %s",
                        (new_name, old_name), commit=True
                    )
                except Exception:
                    pass  # table may not have employee_name column

            execute_query(
                "UPDATE users SET original_name = %s WHERE employee_name = %s",
                (new_name, new_name), commit=True
            )

        # 5b. Sync email change → users.username (login credential)
        # CRITICAL: users.username IS the login email. Must stay in sync.
        if new_email and new_email != old_email:
            try:
                execute_query(
                    "UPDATE users SET username = %s WHERE username = %s",
                    (new_email, old_email), commit=True
                )
                logger.info(
                    f"Synced users.username from '{old_email}' to '{new_email}' "
                    f"for employee ID {emp_id}"
                )
            except Exception as sync_err:
                # Rollback the employee email change to keep data consistent
                execute_query(
                    "UPDATE employee SET email = %s WHERE id = %s",
                    (old_email, emp_id), commit=True
                )
                logger.error(f"Failed to sync users.username for emp {emp_id}: {sync_err}")
                return jsonify({
                    "success": False,
                    "error":   "Email update failed: could not sync login credentials. "
                               "Please try again or contact support."
                }), 500

        # ── 6. Audit log ───────────────────────────────────────────────────
        changed_fields = ", ".join(updates.keys())
        execute_query(
            "INSERT INTO audit_logs (user_id, event_type, description) VALUES (%s, %s, %s)",
            (
                current_user["user_id"],
                "employee_update",
                f"HR '{current_user['employee_name']}' updated employee ID {emp_id} "
                f"(was: {old_name}). Fields changed: {changed_fields}."
            ),
            commit=True
        )

        # ── 7. Return refreshed employee record ────────────────────────────
        refreshed = execute_single(
            "SELECT * FROM employee WHERE id = %s", (emp_id,)
        )

        logger.info(
            f"HR {current_user['employee_name']} updated employee ID {emp_id} "
            f"({old_name}) — fields: {changed_fields}"
        )

        return jsonify({
            "success":  True,
            "message":  f"Employee record updated successfully.",
            "employee": serialize_employee(refreshed),
        }), 200

    except Exception as e:
        logger.error(f"Error updating employee {emp_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@employee_bp.route("/<int:emp_id>", methods=["DELETE"])
@role_required(["hr"])
def delete_employee(current_user, emp_id):
    try:
        # 1. Fetch employee details first
        employee = execute_single("SELECT name, email FROM employee WHERE id = %s", (emp_id,))
        if not employee:
            return jsonify({"success": False, "error": "Employee not found"}), 404
        
        emp_name = employee["name"]
        
        logger.info(f"HR {current_user['employee_name']} is deleting employee {emp_name} (ID: {emp_id})")

        with Transaction() as cursor:
            # 2. Sequential deletion from all linked tables to maintain integrity
            # We follow a "leaves first, trunk last" approach
            related_tables = [
                "attendance", "bank_details", "employee_documents", 
                "leave_balance", "leaves", "notifications", 
                "payslips", "project_assignments", "timesheets", "users"
            ]
            
            for table in related_tables:
                cursor.execute(f"DELETE FROM {table} WHERE employee_name = %s", (emp_name,))
            
            # 3. Finally, delete the employee record itself
            cursor.execute("DELETE FROM employee WHERE id = %s", (emp_id,))

        logger.info(f"Successfully deleted all records for {emp_name}")
        return jsonify({
            "success": True, 
            "message": f"Employee {emp_name} and all associated data have been permanently deleted."
        }), 200

    except Exception as e:
        logger.error(f"Error deleting employee {emp_id}: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@employee_bp.route("/<int:emp_id>/role", methods=["PUT"])
@role_required(["admin"])
def change_employee_role(current_user, emp_id):
    """
    Admin-only: Update an employee's role.
    This triggers a cascade rename across the entire system.
    """
    try:
        data = request.get_json() or {}
        new_role = data.get("role")
        
        if not new_role:
            return jsonify({"success": False, "error": "New role is required"}), 400

        # Note: employee_id in routes is often the database ID of the employee table.
        # But update_employee_role takes the user_id.
        # Let's find the user_id for this employee.
        user = execute_single("""
            SELECT u.id FROM users u
            JOIN employee e ON u.employee_name = e.name
            WHERE e.id = %s
        """, (emp_id,))
        
        if not user:
            return jsonify({"success": False, "error": "User account for this employee not found"}), 404

        result = update_employee_role(current_user["user_id"], user["id"], new_role)
        return jsonify(result), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating role for employee {emp_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ── Profile Photo Management ──────────────────────────────────────────────

@employee_bp.route("/<int:emp_id>/photo", methods=["POST"])
@token_required
def upload_photo(current_user, emp_id):
    """
    Upload or replace a profile photo for an employee.

    - Employees can upload their own photo.
    - HR / Admin can upload for any employee.
    - Accepts multipart/form-data with a 'photo' file field.
    - Allowed types: PNG, JPG, JPEG, WEBP, GIF (max 2 MB).
    """
    try:
        from app.utils.file_upload import save_upload, ALLOWED_IMAGE_EXTENSIONS

        # 1. Verify employee exists
        employee = execute_single("SELECT id, name, photo FROM employee WHERE id = %s", (emp_id,))
        if not employee:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        # 2. RBAC: employees can only update their own photo
        if current_user["role"] == "employee" and employee["name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied. You can only update your own photo."}), 403

        # 3. Validate file presence
        if "photo" not in request.files:
            return jsonify({"success": False, "error": "No 'photo' file provided in the request"}), 400

        file = request.files["photo"]
        if file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400

        # 4. Save file (UUID-named, under uploads/photos/)
        photo_url = save_upload(file, folder="photos", allowed=ALLOWED_IMAGE_EXTENSIONS)

        # 5. Delete old photo file if it exists
        old_photo = employee.get("photo")
        if old_photo:
            old_path = old_photo.lstrip("/")  # /uploads/photos/xxx.jpg -> uploads/photos/xxx.jpg
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    logger.warning(f"Could not delete old photo file: {old_path}")

        # 6. Update database
        execute_query(
            "UPDATE employee SET photo = %s WHERE id = %s",
            (photo_url, emp_id),
            commit=True,
        )

        logger.info(f"Photo uploaded for employee {employee['name']} (ID: {emp_id}): {photo_url}")

        return jsonify({
            "success": True,
            "message": "Profile photo uploaded successfully",
            "photo_url": photo_url,
        }), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error uploading photo for employee {emp_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500


@employee_bp.route("/<int:emp_id>/photo", methods=["DELETE"])
@token_required
def delete_photo(current_user, emp_id):
    """
    Remove an employee's profile photo.

    - Employees can delete their own photo.
    - HR / Admin can delete for any employee.
    """
    try:
        # 1. Verify employee exists
        employee = execute_single("SELECT id, name, photo FROM employee WHERE id = %s", (emp_id,))
        if not employee:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        # 2. RBAC
        if current_user["role"] == "employee" and employee["name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied"}), 403

        old_photo = employee.get("photo")
        if not old_photo:
            return jsonify({"success": False, "error": "No photo to delete"}), 404

        # 3. Delete file from disk
        old_path = old_photo.lstrip("/")
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                logger.warning(f"Could not delete photo file: {old_path}")

        # 4. Clear database field
        execute_query(
            "UPDATE employee SET photo = NULL WHERE id = %s",
            (emp_id,),
            commit=True,
        )

        logger.info(f"Photo deleted for employee {employee['name']} (ID: {emp_id})")
        return jsonify({"success": True, "message": "Profile photo removed"}), 200

    except Exception as e:
        logger.error(f"Error deleting photo for employee {emp_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal server error"}), 500

