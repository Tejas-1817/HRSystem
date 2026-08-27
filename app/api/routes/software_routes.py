from flask import Blueprint, request, jsonify
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required
import json

software_bp = Blueprint('software', __name__)

def _parse_assigned_names(val):
    if not val:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return []

@software_bp.route("/", methods=["GET"], strict_slashes=False)
@token_required
def get_software(current_user):
    try:
        rows = execute_query("SELECT * FROM software_licenses ORDER BY id DESC")
        for row in rows:
            row['assigned_names'] = _parse_assigned_names(row.get('assigned_names'))

        # Calculate stats dynamically
        total = len(rows)
        active_licenses = 0
        renewal_due = 0
        compliant = 0

        for row in rows:
            status = row.get('status', 'Active')
            assigned_count = len(row['assigned_names'])
            
            if status == 'Active':
                active_licenses += assigned_count
            if status == 'Renewal Soon':
                renewal_due += 1
            if status != 'Expired':
                compliant += 1

        compliance = round((compliant / total) * 100) if total > 0 else 0

        return jsonify({
            "success": True,
            "count": total,
            "software": rows,
            "stats": {
                "total": total,
                "active_licenses": active_licenses,
                "renewal_due": renewal_due,
                "compliance": compliance
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@software_bp.route("/", methods=["POST"], strict_slashes=False)
@role_required(["admin"])
def add_software(current_user):
    try:
        data = request.get_json() or {}
        required = ("name", "publisher", "category", "version", "license_type")
        if not all(k in data and data[k] for k in required):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        name = data["name"]
        publisher = data["publisher"]
        category = data["category"]
        version = data["version"]
        license_type = data["license_type"]
        status = data.get("status", "Active")
        assigned_names = json.dumps([])

        execute_query("""
            INSERT INTO software_licenses (name, publisher, category, version, license_type, allocated, status, assigned_names)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, publisher, category, version, license_type, '—', status, assigned_names), commit=True)

        return jsonify({"success": True, "message": "Software asset added successfully"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@software_bp.route("/<int:software_id>", methods=["GET"])
@token_required
def get_single_software(current_user, software_id):
    try:
        row = execute_single("SELECT * FROM software_licenses WHERE id = %s", (software_id,))
        if not row:
            return jsonify({"success": False, "error": "Software asset not found"}), 404
        
        row['assigned_names'] = _parse_assigned_names(row.get('assigned_names'))
        return jsonify({"success": True, "software": row}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@software_bp.route("/<int:software_id>", methods=["PUT"])
@role_required(["admin"])
def update_software(current_user, software_id):
    try:
        data = request.get_json() or {}
        
        # Check if row exists
        existing = execute_single("SELECT * FROM software_licenses WHERE id = %s", (software_id,))
        if not existing:
            return jsonify({"success": False, "error": "Software asset not found"}), 404

        name = data.get("name", existing["name"])
        publisher = data.get("publisher", existing["publisher"])
        category = data.get("category", existing["category"])
        version = data.get("version", existing["version"])
        license_type = data.get("license_type", existing["license_type"])
        status = data.get("status", existing["status"])
        
        assigned_names_raw = data.get("assigned_names")
        if assigned_names_raw is not None:
            assigned_names_list = _parse_assigned_names(assigned_names_raw)
            assigned_names = json.dumps(assigned_names_list)
            # Recalculate allocated count string
            count = len(assigned_names_list)
            allocated = '—' if count == 0 else f"{count} Employee{'s' if count != 1 else ''}"
        else:
            assigned_names = existing["assigned_names"]
            allocated = data.get("allocated", existing["allocated"])

        execute_query("""
            UPDATE software_licenses 
            SET name = %s, publisher = %s, category = %s, version = %s, license_type = %s, allocated = %s, status = %s, assigned_names = %s
            WHERE id = %s
        """, (name, publisher, category, version, license_type, allocated, status, assigned_names, software_id), commit=True)

        return jsonify({"success": True, "message": "Software asset updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@software_bp.route("/<int:software_id>", methods=["DELETE"])
@role_required(["admin"])
def delete_software(current_user, software_id):
    try:
        existing = execute_single("SELECT id FROM software_licenses WHERE id = %s", (software_id,))
        if not existing:
            return jsonify({"success": False, "error": "Software asset not found"}), 404

        execute_query("DELETE FROM software_licenses WHERE id = %s", (software_id,), commit=True)
        return jsonify({"success": True, "message": "Software asset deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
