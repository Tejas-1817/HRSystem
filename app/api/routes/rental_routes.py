from flask import Blueprint, request, jsonify, send_file
from app.api.middleware.auth import token_required, role_required
from app.services.rental_service import (
    get_rental_matrix,
    get_vendor_summary,
    get_month_summary,
    get_rental_dashboard_stats,
)
from app.utils.helpers import log_audit_event
from app.utils.excel_utils import generate_rental_report_excel
from datetime import datetime

rental_bp = Blueprint("rentals", __name__)


def _extract_filters(args):
    """Extract common rental filter query params."""
    return {
        "search": args.get("search"),
        "vendor": args.get("vendor"),
        "device_type": args.get("device_type"),
        "status": args.get("status"),
        "department": args.get("department"),
        "year": args.get("year"),
        "month": args.get("month"),
        "active_only": args.get("active_only") == "true",
        "expiring_soon": args.get("expiring_soon") == "true",
    }


@rental_bp.route("/matrix", methods=["GET"])
@role_required(["hr", "admin"])
def get_matrix(current_user):
    """Returns paginated rental matrix."""
    try:
        filters = _extract_filters(request.args)
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 25))
        result = get_rental_matrix(filters, page=page, page_size=page_size, paginate=True)
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_bp.route("/vendor-summary", methods=["GET"])
@role_required(["hr", "admin"])
def vendor_summary(current_user):
    """Returns vendor aggregations for the left-rail panel."""
    try:
        filters = _extract_filters(request.args)
        data = get_vendor_summary(filters)
        return jsonify({"success": True, "vendors": data}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_bp.route("/month-summary", methods=["GET"])
@role_required(["hr", "admin"])
def month_summary(current_user):
    """Returns per-month cost and active asset count."""
    try:
        filters = _extract_filters(request.args)
        data = get_month_summary(filters)
        return jsonify({"success": True, "months": data}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_bp.route("/dashboard-stats", methods=["GET"])
@role_required(["hr", "admin"])
def dashboard_stats(current_user):
    """Returns the 4 summary card stats."""
    try:
        filters = _extract_filters(request.args)
        data = get_rental_dashboard_stats(filters)
        return jsonify({"success": True, **data}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rental_bp.route("/export", methods=["GET"])
@role_required(["hr", "admin"])
def export_rental(current_user):
    """Exports the full filtered rental matrix as an Excel file."""
    try:
        filters = _extract_filters(request.args)
        # Export full dataset (not paginated)
        result = get_rental_matrix(filters, paginate=False)
        rows = result.get("rows", [])

        if not rows:
            return jsonify({"success": False, "error": "No rental assets match the selected filters."}), 404

        generated_by_name = current_user.get("employee_name", "System")
        excel_data = generate_rental_report_excel(rows, generated_by_name)

        log_audit_event(
            user_id=current_user.get("user_id") or current_user.get("id"),
            event_type="rental_report_export",
            description=f"Exported {len(rows)} rental assets to Excel. Filters: {filters}"
        )

        filename = f"Rental_Management_{datetime.now().strftime('%Y_%m_%d_%H_%M')}.xlsx"
        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to export rentals: {str(e)}"}), 500
