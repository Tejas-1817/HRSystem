from flask import Blueprint, request, jsonify
from app.api.middleware.auth import token_required, role_required
from app.services.device_service import (
    list_devices, get_device_by_id, create_device,
    assign_device, return_device, get_device_history,
    add_device_image, get_employee_devices, soft_delete_device
)
from app.services.device_agreement_service import (
    get_pending_agreement, accept_agreement,
    reject_agreement, get_acceptance_status
)
from app.services.inventory_service import (
    get_inventory_dashboard, get_low_stock_alerts,
    list_catalog, create_catalog_entry, update_catalog_entry,
    update_device_status, get_asset_lifecycle, reconcile_stock,
    get_stock_by_catalog,
)
from app.utils.file_upload import save_upload

device_bp = Blueprint("devices", __name__)

@device_bp.route("/", methods=["GET"])
@role_required(["hr"])
def get_all_devices(current_user):
    filters = {
        "status": request.args.get("status"),
        "brand": request.args.get("brand"),
        "device_type": request.args.get("device_type"),
        "search": request.args.get("search")
    }
    devices = list_devices(filters)
    return jsonify({"success": True, "devices": devices, "count": len(devices)}), 200

@device_bp.route("/", methods=["POST"])
@role_required(["hr"])
def add_device(current_user):
    data = request.get_json() or {}
    required = ["brand", "model", "serial_number"]
    if not all(k in data for k in required):
        return jsonify({"success": False, "error": "brand, model, and serial_number are required"}), 400
    
    try:
        data["added_by"] = current_user["employee_name"]
        device_id = create_device(data)
        return jsonify({"success": True, "device_id": device_id, "message": "Device created"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@device_bp.route("/<int:device_id>", methods=["GET"])
@token_required
def get_device(current_user, device_id):
    device = get_device_by_id(device_id)
    if not device:
        return jsonify({"success": False, "error": "Device not found"}), 404
    
    # RBAC check: employees can only view if assigned to them or if they are HR
    if current_user["role"] not in ("hr", "admin"):
        # Check current assignment
        assignments = get_employee_devices(current_user["employee_name"])
        if not any(d["id"] == device_id for d in assignments):
            return jsonify({"success": False, "error": "Access denied"}), 403
            
    return jsonify({"success": True, "device": device}), 200

@device_bp.route("/<int:device_id>/assign", methods=["POST"])
@role_required(["hr"])
def allocate_device(current_user, device_id):
    data = request.get_json() or {}
    employee_name = data.get("employee_name")
    if not employee_name:
        return jsonify({"success": False, "error": "employee_name is required"}), 400
    
    if assign_device(device_id, employee_name):
        return jsonify({"success": True, "message": f"Device assigned to {employee_name}. Awaiting acceptance."}), 200
    return jsonify({"success": False, "error": "Device not found or not available. Only devices with status 'Available' can be assigned."}), 400

@device_bp.route("/<int:device_id>/return", methods=["POST"])
@role_required(["hr"])
def deallocate_device(current_user, device_id):
    if return_device(device_id):
        return jsonify({"success": True, "message": "Device returned successfully"}), 200
    return jsonify({"success": False, "error": "Device not found"}), 404

@device_bp.route("/<int:device_id>/upload-image", methods=["POST"])
@role_required(["hr"])
def upload_image(current_user, device_id):
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image part in request"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
        
    try:
        image_url = save_upload(file, folder="devices")
        image_id = add_device_image(device_id, image_url)
        return jsonify({"success": True, "image_id": image_id, "image_url": image_url}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@device_bp.route("/my-devices", methods=["GET"])
@token_required
def get_my_gear(current_user):
    devices = get_employee_devices(current_user["employee_name"])
    return jsonify({"success": True, "devices": devices}), 200

@device_bp.route("/<int:device_id>/history", methods=["GET"])
@role_required(["hr"])
def get_history(current_user, device_id):
    history = get_device_history(device_id)
    return jsonify({"success": True, "history": history}), 200


@device_bp.route("/<int:device_id>", methods=["DELETE"])
@role_required(["hr"])
def delete_device(current_user, device_id):
    """
    Soft-delete a device (HR / Admin only).

    Validation blocks deletion if the device is:
    - Currently assigned to an employee
    - Under repair
    - Linked to open helpdesk tickets
    """
    try:
        result = soft_delete_device(
            device_id=device_id,
            deleted_by=current_user["employee_name"],
        )
        return jsonify({
            "success": True,
            "message": f"Device {result['device_label']} deleted successfully.",
            **result,
        }), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# Inventory Management Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@device_bp.route("/inventory", methods=["GET"])
@role_required(["hr"])
def inventory_dashboard(current_user):
    """Full inventory dashboard: stock by status, category, brand + low stock alerts."""
    try:
        dashboard = get_inventory_dashboard()
        return jsonify({"success": True, **dashboard}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/inventory/low-stock", methods=["GET"])
@role_required(["hr"])
def low_stock_alerts(current_user):
    """Low-stock alerts: catalog entries where available < threshold."""
    try:
        alerts = get_low_stock_alerts()
        return jsonify({"success": True, "alerts": alerts, "count": len(alerts)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/inventory/reconcile", methods=["GET"])
@role_required(["hr"])
def stock_reconciliation(current_user):
    """Stock reconciliation: compare device statuses vs assignment state."""
    try:
        report = reconcile_stock()
        return jsonify({"success": True, **report}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/catalog", methods=["GET"])
@role_required(["hr"])
def get_catalog(current_user):
    """List all catalog SKUs with real-time stock counts."""
    try:
        catalog = list_catalog()
        return jsonify({"success": True, "catalog": catalog, "count": len(catalog)}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/catalog", methods=["POST"])
@role_required(["hr"])
def add_catalog_entry(current_user):
    """Add a new catalog SKU."""
    data = request.get_json() or {}
    required = ["category", "brand", "model"]
    if not all(k in data for k in required):
        return jsonify({"success": False, "error": "category, brand, and model are required"}), 400
    try:
        entry_id = create_catalog_entry(data)
        return jsonify({"success": True, "catalog_id": entry_id, "message": "Catalog entry created"}), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/catalog/<int:catalog_id>", methods=["PUT"])
@role_required(["hr"])
def edit_catalog_entry(current_user, catalog_id):
    """Update a catalog SKU."""
    data = request.get_json() or {}
    try:
        if update_catalog_entry(catalog_id, data):
            return jsonify({"success": True, "message": "Catalog entry updated"}), 200
        return jsonify({"success": False, "error": "Catalog entry not found"}), 404
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/catalog/<int:catalog_id>/stock", methods=["GET"])
@role_required(["hr"])
def catalog_stock(current_user, catalog_id):
    """Stock counts for a specific catalog SKU."""
    try:
        result = get_stock_by_catalog(catalog_id)
        if not result:
            return jsonify({"success": False, "error": "Catalog entry not found"}), 404
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/<int:device_id>/status", methods=["PATCH"])
@role_required(["hr"])
def change_device_status(current_user, device_id):
    """Change a device's status (Available ↔ Under Repair, Retired)."""
    data = request.get_json() or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"success": False, "error": "status is required"}), 400
    try:
        result = update_device_status(device_id, new_status,
                                       current_user["employee_name"],
                                       data.get("notes"))
        return jsonify({"success": True, "message": f"Status changed to {new_status}", **result}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/<int:device_id>/lifecycle", methods=["GET"])
@role_required(["hr"])
def device_lifecycle(current_user, device_id):
    """Full asset lifecycle timeline."""
    try:
        result = get_asset_lifecycle(device_id)
        if not result:
            return jsonify({"success": False, "error": "Device not found"}), 404
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# Device Assignment Acceptance Workflow
# ══════════════════════════════════════════════════════════════════════════════

@device_bp.route("/<int:device_id>/agreement", methods=["GET"])
@token_required
def view_agreement(current_user, device_id):
    """
    Fetch the personalised device usage agreement for the currently
    assigned employee.  Returns the full agreement text, device details,
    and version identifier.

    - Employees see their own pending agreement.
    - HR/Admin can view any device's pending agreement.
    """
    try:
        # Determine whose agreement to fetch
        if current_user["role"] in ("hr", "admin"):
            # HR can view the agreement for whoever is currently assigned
            from app.models.database import execute_single
            assignment = execute_single("""
                SELECT employee_name FROM device_assignments
                WHERE device_id = %s AND returned_date IS NULL
                  AND acceptance_status = 'pending'
                ORDER BY assigned_date DESC LIMIT 1
            """, (device_id,))
            if not assignment:
                return jsonify({"success": False, "error": "No pending assignment for this device"}), 404
            target_employee = assignment["employee_name"]
        else:
            target_employee = current_user["employee_name"]

        agreement = get_pending_agreement(device_id, target_employee)
        if not agreement:
            return jsonify({
                "success": False,
                "error": "No pending device agreement found for you on this device."
            }), 404

        return jsonify({"success": True, "agreement": agreement}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/<int:device_id>/accept", methods=["POST"])
@token_required
def accept_device(current_user, device_id):
    """
    Accept a device assignment with a digital signature.

    Expects multipart/form-data with:
    - 'signature': image file (PNG/JPG/JPEG/WEBP — the drawn or uploaded signature)
    - 'assignment_id': the ID of the assignment being accepted

    Only the assigned employee can call this endpoint.
    """
    try:
        # 1. Validate signature file
        if "signature" not in request.files:
            return jsonify({
                "success": False,
                "error": "No 'signature' file provided. Please draw or upload your signature."
            }), 400

        signature_file = request.files["signature"]
        if signature_file.filename == "":
            return jsonify({"success": False, "error": "Empty signature filename"}), 400

        # 2. Get assignment_id (from form data or JSON-encoded field)
        assignment_id = request.form.get("assignment_id")
        if not assignment_id:
            return jsonify({
                "success": False,
                "error": "assignment_id is required"
            }), 400

        # 3. Process acceptance
        result = accept_agreement(
            assignment_id=int(assignment_id),
            employee_name=current_user["employee_name"],
            signature_file=signature_file,
            ip_address=request.remote_addr,
        )

        return jsonify({"success": True, "message": "Device agreement accepted successfully", **result}), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/<int:device_id>/reject", methods=["POST"])
@token_required
def reject_device(current_user, device_id):
    """
    Reject a device assignment.

    Expects JSON body:
    - 'assignment_id': the ID of the assignment being rejected
    - 'reason': (optional) reason for rejection

    Only the assigned employee can call this endpoint.
    """
    try:
        data = request.get_json() or {}
        assignment_id = data.get("assignment_id")
        if not assignment_id:
            return jsonify({"success": False, "error": "assignment_id is required"}), 400

        result = reject_agreement(
            assignment_id=int(assignment_id),
            employee_name=current_user["employee_name"],
            reason=data.get("reason"),
        )

        return jsonify({"success": True, "message": "Device assignment rejected", **result}), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@device_bp.route("/<int:device_id>/acceptance-status", methods=["GET"])
@token_required
def device_acceptance_status(current_user, device_id):
    """
    View the acceptance status for a device's current assignment.

    - HR/Admin: can view any device.
    - Employee: can view only their own assigned devices.
    """
    try:
        status = get_acceptance_status(device_id)

        # RBAC for employees: only view own assignment
        if current_user["role"] not in ("hr", "admin"):
            if status.get("assigned") and status.get("employee_name") != current_user["employee_name"]:
                return jsonify({"success": False, "error": "Access denied"}), 403

        return jsonify({"success": True, "status": status}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

