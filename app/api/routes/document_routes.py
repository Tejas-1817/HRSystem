from flask import Blueprint, request, jsonify, send_from_directory
import os
from datetime import datetime
from app.config import Config
from app.models.database import execute_query, execute_single
from app.api.middleware.auth import token_required, role_required

document_bp = Blueprint('documents', __name__)

@document_bp.route("/my-status", methods=["GET"])
@token_required
def get_my_status(current_user):
    try:
        rows = execute_query("SELECT doc_type, status, uploaded_at FROM employee_documents WHERE employee_name=%s", (current_user["employee_name"],))
        return jsonify({"success": True, "documents": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@document_bp.route("/pending-review", methods=["GET"])
@role_required(["hr"])
def get_pending_documents(current_user):
    try:
        rows = execute_query("SELECT * FROM employee_documents WHERE status='pending' OR status='uploaded'")
        return jsonify({"success": True, "pending_documents": rows}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@document_bp.route("/verify/<int:doc_id>", methods=["PUT"])
@role_required(["hr"])
def verify_document(current_user, doc_id):
    try:
        execute_query("""
            UPDATE employee_documents 
            SET status='verified', verified_by=%s, verified_at=NOW() 
            WHERE id=%s
        """, (current_user["employee_name"], doc_id), commit=True)
        return jsonify({"success": True, "message": "Document verified"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@document_bp.route("/download/<int:doc_id>", methods=["GET"])
@token_required
def download_document(current_user, doc_id):
    try:
        doc = execute_single("SELECT * FROM employee_documents WHERE id=%s", (doc_id,))
        if not doc: return jsonify({"success": False, "error": "Document not found"}), 404
        
        # Check access
        if current_user["role"] == "employee" and doc["employee_name"] != current_user["employee_name"]:
            return jsonify({"success": False, "error": "Access denied"}), 403

        directory = os.path.dirname(doc["file_path"])
        filename = os.path.basename(doc["file_path"])
        return send_from_directory(directory, filename)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
