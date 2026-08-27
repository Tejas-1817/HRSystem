from flask import Blueprint, request, jsonify
from app.api.middleware.auth import token_required, role_required
from app.services.rental_invoice_service import (
    get_invoices,
    pay_invoice,
    get_invoice_history,
    get_invoice_dashboard_stats,
    check_and_generate_invoices
)

rental_invoice_bp = Blueprint("rental_invoices", __name__)


def _ensure_vendor_invoice_columns():
    try:
        from app.models.database import execute_query
        cols = [
            ('uploaded_file_path', 'VARCHAR(255) NULL'),
            ('uploaded_file_name', 'VARCHAR(255) NULL'),
            ('uploaded_file_type', 'VARCHAR(50) NULL'),
            ('uploaded_file_size', 'INT NULL'),
            ('uploaded_at', 'TIMESTAMP NULL')
        ]
        for cname, cdef in cols:
            try:
                execute_query(f"ALTER TABLE vendor_invoices ADD COLUMN {cname} {cdef}", commit=True)
            except Exception:
                pass
    except Exception:
        pass


ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>", methods=["GET"])
@role_required(["hr", "admin"])
def get_vendor_invoice_details(current_user, vendor_name):
    """Returns full vendor invoice details: meta + all assets + financials + uploaded invoice info."""
    try:
        from app.models.database import execute_single, execute_query
        _ensure_vendor_invoice_columns()
        inv = execute_single(
            """SELECT vendor_name, invoice_number, status, created_at,
                      uploaded_file_path, uploaded_file_name, uploaded_file_type, uploaded_file_size, uploaded_at
               FROM vendor_invoices WHERE vendor_name = %s""",
            (vendor_name,)
        )
        if not inv:
            return jsonify({"success": False, "error": "Vendor invoice not found."}), 404

        for k, v in list(inv.items()):
            if hasattr(v, 'isoformat'):
                inv[k] = v.isoformat()

        uploaded_inv = None
        if inv.get("uploaded_file_path"):
            uploaded_inv = {
                "file_name": inv.get("uploaded_file_name") or "Vendor_Invoice",
                "file_type": inv.get("uploaded_file_type") or "application/octet-stream",
                "file_size": inv.get("uploaded_file_size") or 0,
                "uploaded_at": inv.get("uploaded_at"),
                "view_url": f"/api/rentals/vendor-invoice/{vendor_name}/file",
                "download_url": f"/api/rentals/vendor-invoice/{vendor_name}/download"
            }

        # All active rented devices for this vendor
        assets = execute_query("""
            SELECT d.id, d.brand, d.model, d.serial_number, d.asset_id, d.device_type,
                   d.rental_start_date, d.rental_end_date, d.rental_cost, d.next_due_date,
                   da.employee_name AS assigned_to
            FROM devices d
            LEFT JOIN device_assignments da ON d.id = da.device_id AND da.returned_date IS NULL
            WHERE d.vendor_name = %s AND d.ownership_type = 'Rented' AND d.is_deleted = FALSE
            ORDER BY d.rental_start_date ASC
        """, (vendor_name,))

        # Paid amount: sum of all payments made for this vendor's devices
        paid_row = execute_single("""
            SELECT COALESCE(SUM(rp.amount), 0) AS paid_total
            FROM rental_payments rp
            JOIN devices d ON rp.device_id = d.id
            WHERE d.vendor_name = %s AND d.is_deleted = FALSE
        """, (vendor_name,))
        paid_amount = float(paid_row['paid_total']) if paid_row else 0.0

        # Per-device: determine if at least one invoice is 'Paid'
        device_paid_statuses = {}
        if assets:
            device_ids = [a['id'] for a in assets]
            placeholders = ', '.join(['%s'] * len(device_ids))
            paid_devices = execute_query(f"""
                SELECT DISTINCT device_id FROM rental_invoices
                WHERE device_id IN ({placeholders}) AND status = 'Paid'
            """, tuple(device_ids))
            for row in paid_devices:
                device_paid_statuses[row['device_id']] = True

        total_payable = 0.0
        earliest_due = None
        for a in assets:
            for k, v in a.items():
                if hasattr(v, 'isoformat'):
                    a[k] = v.isoformat()
                elif hasattr(v, 'as_tuple'):
                    a[k] = float(v)
            total_payable += float(a.get('rental_cost') or 0)
            nd = a.get('next_due_date')
            if nd:
                if earliest_due is None or nd < earliest_due:
                    earliest_due = nd
            # Attach payment status per asset
            a['payment_status'] = 'Paid' if device_paid_statuses.get(a['id']) else 'Unpaid'

        remaining_amount = max(0.0, total_payable - paid_amount)

        return jsonify({
            "success": True,
            "invoice": {
                **inv,
                "total_assets": len(assets),
                "total_payable": total_payable,
                "paid_amount": paid_amount,
                "remaining_amount": remaining_amount,
                "due_date": earliest_due,
                "uploaded_invoice": uploaded_inv
            },
            "assets": assets
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>/upload", methods=["POST"])
@role_required(["hr", "admin"])
def upload_vendor_invoice_file(current_user, vendor_name):
    """Upload a vendor invoice file (PDF, JPG, PNG) and associate with vendor."""
    try:
        from werkzeug.utils import secure_filename
        import os, time
        from app.models.database import execute_single, execute_query

        _ensure_vendor_invoice_columns()

        file = request.files.get("file") or request.files.get("vendor_invoice")
        if not file or not file.filename:
            return jsonify({"success": False, "error": "No file selected."}), 400

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({"success": False, "error": "Invalid file type. Only PDF, JPG, and PNG files are allowed."}), 400

        inv = execute_single("SELECT vendor_name FROM vendor_invoices WHERE vendor_name = %s", (vendor_name,))
        if not inv:
            inv_num = f"INV-{time.strftime('%Y')}-{int(time.time())}"
            execute_query(
                "INSERT INTO vendor_invoices (vendor_name, invoice_number, status) VALUES (%s, %s, 'Pending')",
                (vendor_name, inv_num), commit=True
            )

        upload_dir = os.path.join(os.getcwd(), 'uploads', 'vendor_invoices')
        os.makedirs(upload_dir, exist_ok=True)

        original_filename = secure_filename(file.filename) or f"invoice.{ext}"
        saved_filename = f"{secure_filename(vendor_name)}_{int(time.time())}_{original_filename}"
        saved_path = os.path.join(upload_dir, saved_filename)

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        file.save(saved_path)

        mime = file.mimetype or ('application/pdf' if ext == 'pdf' else f'image/{ext}')
        execute_query("""
            UPDATE vendor_invoices
            SET uploaded_file_path = %s,
                uploaded_file_name = %s,
                uploaded_file_type = %s,
                uploaded_file_size = %s,
                uploaded_at = CURRENT_TIMESTAMP
            WHERE vendor_name = %s
        """, (saved_path, original_filename, mime, file_size, vendor_name), commit=True)

        return jsonify({
            "success": True,
            "message": "Vendor invoice uploaded successfully.",
            "uploaded_invoice": {
                "file_name": original_filename,
                "file_type": mime,
                "file_size": file_size,
                "uploaded_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                "view_url": f"/api/rentals/vendor-invoice/{vendor_name}/file",
                "download_url": f"/api/rentals/vendor-invoice/{vendor_name}/download"
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>/file", methods=["GET"])
@role_required(["hr", "admin"])
def get_vendor_invoice_file(current_user, vendor_name):
    """View uploaded vendor invoice document inline in browser."""
    try:
        import os
        from flask import send_file
        from app.models.database import execute_single

        inv = execute_single("SELECT uploaded_file_path, uploaded_file_name, uploaded_file_type FROM vendor_invoices WHERE vendor_name = %s", (vendor_name,))
        if not inv or not inv.get("uploaded_file_path") or not os.path.exists(inv["uploaded_file_path"]):
            return jsonify({"success": False, "error": "Uploaded invoice document not found."}), 404

        return send_file(
            inv["uploaded_file_path"],
            mimetype=inv.get("uploaded_file_type") or 'application/octet-stream',
            as_attachment=False
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>/download", methods=["GET"])
@role_required(["hr", "admin"])
def download_vendor_invoice_file(current_user, vendor_name):
    """Download uploaded vendor invoice document."""
    try:
        import os
        from flask import send_file
        from app.models.database import execute_single

        inv = execute_single("SELECT uploaded_file_path, uploaded_file_name, uploaded_file_type FROM vendor_invoices WHERE vendor_name = %s", (vendor_name,))
        if not inv or not inv.get("uploaded_file_path") or not os.path.exists(inv["uploaded_file_path"]):
            return jsonify({"success": False, "error": "Uploaded invoice document not found."}), 404

        return send_file(
            inv["uploaded_file_path"],
            mimetype=inv.get("uploaded_file_type") or 'application/octet-stream',
            as_attachment=True,
            download_name=inv.get("uploaded_file_name") or f"{vendor_name}_invoice"
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>/upload", methods=["DELETE"])
@role_required(["hr", "admin"])
def delete_vendor_invoice_file(current_user, vendor_name):
    """Delete uploaded vendor invoice document."""
    try:
        import os
        from app.models.database import execute_single, execute_query

        inv = execute_single("SELECT uploaded_file_path FROM vendor_invoices WHERE vendor_name = %s", (vendor_name,))
        if inv and inv.get("uploaded_file_path") and os.path.exists(inv["uploaded_file_path"]):
            try:
                os.remove(inv["uploaded_file_path"])
            except Exception:
                pass

        execute_query("""
            UPDATE vendor_invoices
            SET uploaded_file_path = NULL,
                uploaded_file_name = NULL,
                uploaded_file_type = NULL,
                uploaded_file_size = NULL,
                uploaded_at = NULL
            WHERE vendor_name = %s
        """, (vendor_name,), commit=True)

        return jsonify({"success": True, "message": "Uploaded invoice removed."}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>", methods=["PUT"])
@role_required(["hr", "admin"])
def update_vendor_invoice(current_user, vendor_name):
    """Update master invoice number and/or status for a vendor."""
    try:
        from app.models.database import execute_single, execute_query
        data = request.get_json() or {}
        new_number = (data.get("invoice_number") or "").strip() or None
        new_status = (data.get("status") or "").strip() or None

        valid_statuses = {'Pending', 'Due This Month', 'Overdue', 'Paid', 'Settled'}
        if new_status and new_status not in valid_statuses:
            return jsonify({"success": False, "error": f"Invalid status '{new_status}'."}), 400

        if not new_number and not new_status:
            return jsonify({"success": False, "error": "Nothing to update."}), 400

        if new_number:
            conflict = execute_single(
                "SELECT vendor_name FROM vendor_invoices WHERE invoice_number = %s AND vendor_name != %s",
                (new_number, vendor_name)
            )
            if conflict:
                return jsonify({
                    "success": False,
                    "error": f"Invoice number '{new_number}' is already assigned to '{conflict['vendor_name']}'."
                }), 409

        # Build dynamic SET clause
        set_parts, params = [], []
        if new_number:
            set_parts.append("invoice_number = %s"); params.append(new_number)
        if new_status:
            set_parts.append("status = %s"); params.append(new_status)
        params.append(vendor_name)

        execute_query(
            f"UPDATE vendor_invoices SET {', '.join(set_parts)} WHERE vendor_name = %s",
            tuple(params), commit=True
        )

        # Return updated record
        updated = execute_single("SELECT invoice_number, status FROM vendor_invoices WHERE vendor_name = %s", (vendor_name,))
        return jsonify({"success": True, **(updated or {})}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>/asset-payment", methods=["PUT"])
@role_required(["hr", "admin"])
def update_vendor_asset_payment(current_user, vendor_name):
    """Toggle payment status for an individual asset under a vendor and update vendor invoice status automatically."""
    try:
        from app.models.database import execute_single, execute_query
        data = request.get_json() or {}
        device_id = data.get("device_id")
        status = data.get("status")  # 'Paid' or 'Unpaid'

        if not device_id or status not in ['Paid', 'Unpaid']:
            return jsonify({"success": False, "error": "Invalid payload."}), 400

        if status == 'Paid':
            # Check if there is an existing invoice for this device
            inv = execute_single("SELECT id, total_amount FROM rental_invoices WHERE device_id = %s ORDER BY id DESC LIMIT 1", (device_id,))
            if inv:
                execute_query("UPDATE rental_invoices SET status = 'Paid', payment_date = CURRENT_DATE WHERE id = %s", (inv['id'],), commit=True)
                inv_id = inv['id']
                amt = float(inv['total_amount'] or 0)
            else:
                dev = execute_single("SELECT rental_cost FROM devices WHERE id = %s", (device_id,))
                amt = float(dev['rental_cost'] or 0) if dev else 0.0
                inv_num = f"INV-DEV-{device_id}"
                inv_id = execute_query("""
                    INSERT INTO rental_invoices (invoice_number, device_id, vendor_name, monthly_rental_amount, total_amount, status, payment_date)
                    VALUES (%s, %s, %s, %s, %s, 'Paid', CURRENT_DATE)
                """, (inv_num, device_id, vendor_name, amt, amt), commit=True)
            
            # Record payment if not already recorded
            pay_check = execute_single("SELECT id FROM rental_payments WHERE device_id = %s", (device_id,))
            if not pay_check:
                execute_query("""
                    INSERT INTO rental_payments (invoice_id, device_id, amount, payment_date, payment_mode)
                    VALUES (%s, %s, %s, CURRENT_DATE, 'Bank Transfer')
                """, (inv_id, device_id, amt), commit=True)
        else:
            # Mark unpaid
            execute_query("UPDATE rental_invoices SET status = 'Pending' WHERE device_id = %s", (device_id,), commit=True)
            execute_query("DELETE FROM rental_payments WHERE device_id = %s", (device_id,), commit=True)

        # Check all active devices for this vendor to recalculate vendor invoice status
        devices = execute_query("SELECT id FROM devices WHERE vendor_name = %s AND ownership_type = 'Rented' AND is_deleted = FALSE", (vendor_name,))
        device_ids = [d['id'] for d in devices]
        
        all_paid = False
        if device_ids:
            placeholders = ', '.join(['%s'] * len(device_ids))
            paid_count = execute_single(f"""
                SELECT COUNT(DISTINCT device_id) as count FROM rental_invoices
                WHERE device_id IN ({placeholders}) AND status = 'Paid'
            """, tuple(device_ids))
            if paid_count and paid_count['count'] == len(device_ids):
                all_paid = True

        new_vendor_status = 'Paid' if (all_paid and device_ids) else 'Pending'
        execute_query("UPDATE vendor_invoices SET status = %s WHERE vendor_name = %s", (new_vendor_status, vendor_name), commit=True)

        return jsonify({"success": True, "vendor_status": new_vendor_status}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/vendor-invoice/<path:vendor_name>/pay-all", methods=["POST"])
@role_required(["hr", "admin"])
def pay_all_vendor_assets(current_user, vendor_name):
    """Mark all assets for a vendor as Paid and update vendor invoice status to Paid."""
    try:
        from app.models.database import execute_single, execute_query
        devices = execute_query("SELECT id, rental_cost FROM devices WHERE vendor_name = %s AND ownership_type = 'Rented' AND is_deleted = FALSE", (vendor_name,))
        for d in devices:
            device_id = d['id']
            amt = float(d['rental_cost'] or 0)
            inv = execute_single("SELECT id FROM rental_invoices WHERE device_id = %s ORDER BY id DESC LIMIT 1", (device_id,))
            if inv:
                execute_query("UPDATE rental_invoices SET status = 'Paid', payment_date = CURRENT_DATE WHERE id = %s", (inv['id'],), commit=True)
                inv_id = inv['id']
            else:
                inv_num = f"INV-DEV-{device_id}"
                inv_id = execute_query("""
                    INSERT INTO rental_invoices (invoice_number, device_id, vendor_name, monthly_rental_amount, total_amount, status, payment_date)
                    VALUES (%s, %s, %s, %s, %s, 'Paid', CURRENT_DATE)
                """, (inv_num, device_id, vendor_name, amt, amt), commit=True)

            pay_check = execute_single("SELECT id FROM rental_payments WHERE device_id = %s", (device_id,))
            if not pay_check:
                execute_query("""
                    INSERT INTO rental_payments (invoice_id, device_id, amount, payment_date, payment_mode)
                    VALUES (%s, %s, %s, CURRENT_DATE, 'Bank Transfer')
                """, (inv_id, device_id, amt), commit=True)

        execute_query("UPDATE vendor_invoices SET status = 'Paid' WHERE vendor_name = %s", (vendor_name,), commit=True)
        return jsonify({"success": True, "vendor_status": "Paid"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_invoice_bp.route("/invoices", methods=["GET"])
@role_required(["hr", "admin"])
def list_invoices(current_user):
    """Returns list of filtered invoices."""
    try:
        filters = {
            "status": request.args.get("status"),
            "device_id": request.args.get("device_id"),
            "vendor": request.args.get("vendor"),
            "search": request.args.get("search")
        }
        res = get_invoices(filters)
        return jsonify({"success": True, "invoices": res}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@rental_invoice_bp.route("/invoices/<int:invoice_id>/pay", methods=["POST"])
@role_required(["hr", "admin"])
def process_payment(current_user, invoice_id):
    """Mark invoice as paid and process cycle advancement."""
    try:
        data = request.get_json() or {}
        res = pay_invoice(invoice_id, data)
        return jsonify(res), 200
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@rental_invoice_bp.route("/invoices/dashboard-widgets", methods=["GET"])
@role_required(["hr", "admin"])
def dashboard_widgets(current_user):
    """Returns invoice metrics for dashboard widgets."""
    try:
        res = get_invoice_dashboard_stats()
        return jsonify({"success": True, **res}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@rental_invoice_bp.route("/invoices/history/<device_id>", methods=["GET"])
@role_required(["hr", "admin"])
def invoice_history(current_user, device_id):
    """Returns full invoice/payment history for a device."""
    try:
        res = get_invoice_history(device_id)
        return jsonify({"success": True, **res}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@rental_invoice_bp.route("/invoices/trigger-check", methods=["POST"])
@role_required(["hr", "admin"])
def trigger_check(current_user):
    """Manually triggers automated check (useful for debugging/testing)."""
    try:
        check_and_generate_invoices()
        return jsonify({"success": True, "message": "Manual check completed"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
