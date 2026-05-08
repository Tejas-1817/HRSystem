# ---------------------------------------------------------------------------
# Reimbursement Service — Reference generation, file handling,
#                          RBAC-aware query builder, audit logging
# ---------------------------------------------------------------------------

import os
import uuid
import logging
from datetime import datetime
from app.models.database import execute_query, execute_single
from app.config import Config

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB
RECEIPT_SUBDIR      = "receipts"


# ---------------------------------------------------------------------------
# Reference Generator
# ---------------------------------------------------------------------------

def generate_ref() -> str:
    """
    Generate a sequential human-readable expense reference: EXP-0001, EXP-0042.
    Uses MAX(id) + 1. Thread safety: UNIQUE constraint on ref handles races.
    """
    row = execute_single("SELECT COALESCE(MAX(id), 0) AS max_id FROM reimbursements")
    next_num = (row["max_id"] + 1) if row else 1
    return f"EXP-{next_num:04d}"


# ---------------------------------------------------------------------------
# Receipt File Handler
# ---------------------------------------------------------------------------

def save_receipt(file, employee_name: str) -> str:
    """
    Validate and persist a receipt file upload.

    Validation:
      - Extension must be jpg/jpeg/png/pdf
      - File size must be ≤ 5 MB

    Storage: uploads/receipts/<employee_name>/<uuid>_<original_filename>

    Returns the relative file path (stored in DB).
    Raises ValueError on validation failure.
    """
    if not file or file.filename == "":
        raise ValueError("No file provided.")

    filename  = file.filename.lower()
    ext       = filename.rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Invalid file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Read content to check size
    content = file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError("File size exceeds the 5 MB limit.")
    file.seek(0)  # reset pointer after read

    # Build storage path
    safe_name    = "".join(c if c.isalnum() or c in "-_" else "_" for c in employee_name)
    unique_name  = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    dir_path     = os.path.join(Config.UPLOAD_FOLDER, RECEIPT_SUBDIR, safe_name)
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, unique_name)
    file.save(file_path)

    logger.info(f"Receipt saved: {file_path}")
    return file_path


# ---------------------------------------------------------------------------
# Audit History Logger
# ---------------------------------------------------------------------------

def log_history(reimbursement_id: int, changed_by: str, field: str,
                old_value, new_value, note: str = None) -> None:
    """Append one immutable row to reimbursement_history."""
    execute_query("""
        INSERT INTO reimbursement_history
            (reimbursement_id, changed_by, field, old_value, new_value, note)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        reimbursement_id,
        changed_by,
        field,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None,
        note,
    ), commit=True)


# ---------------------------------------------------------------------------
# RBAC-aware reimbursement fetcher
# ---------------------------------------------------------------------------

def get_reimbursements(current_user: dict, filters: dict) -> list:
    """
    Fetch reimbursements with strict RBAC scoping and optional filters.

    Visibility:
      - employee → own records only
      - manager / hr / admin → all records

    Filters (all optional):
      status, category, employee_name, project_id, from_date, to_date
    """
    role = current_user["role"]
    emp  = current_user["employee_name"]

    conditions = []
    params     = []

    # Scope employees to their own records
    if role == "employee":
        conditions.append("r.employee_name = %s")
        params.append(emp)

    # Optional filters
    if filters.get("status"):
        conditions.append("r.status = %s")
        params.append(filters["status"])

    if filters.get("category"):
        conditions.append("r.category = %s")
        params.append(filters["category"])

    if filters.get("employee_name") and role != "employee":
        conditions.append("r.employee_name = %s")
        params.append(filters["employee_name"])

    if filters.get("project_id"):
        conditions.append("r.project_id = %s")
        params.append(filters["project_id"])

    if filters.get("from_date"):
        conditions.append("r.expense_date >= %s")
        params.append(filters["from_date"])

    if filters.get("to_date"):
        conditions.append("r.expense_date <= %s")
        params.append(filters["to_date"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = execute_query(f"""
        SELECT
            r.id, r.ref, r.employee_name, r.title, r.description,
            r.amount, r.currency, r.expense_date, r.category,
            r.receipt_file IS NOT NULL AS has_receipt,
            r.status, r.approved_by, r.approved_at,
            r.rejection_reason, r.payment_status, r.payment_date,
            r.project_id, r.billable, r.created_at, r.updated_at
        FROM reimbursements r
        {where}
        ORDER BY r.created_at DESC
    """, tuple(params) if params else None)

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
        r["has_receipt"] = bool(r["has_receipt"])
        r["billable"]    = bool(r["billable"])

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_reimbursement_or_404(reimbursement_id: int):
    """Fetch a single reimbursement dict by PK, or None if not found."""
    row = execute_single("SELECT * FROM reimbursements WHERE id = %s", (reimbursement_id,))
    if row:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        row["billable"] = bool(row.get("billable"))
    return row


def get_reimbursement_history(reimbursement_id: int) -> list:
    """Return the full audit trail for a reimbursement, oldest first."""
    rows = execute_query("""
        SELECT id, changed_by, field, old_value, new_value, note, changed_at
        FROM reimbursement_history
        WHERE reimbursement_id = %s
        ORDER BY changed_at ASC
    """, (reimbursement_id,))

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return rows


def can_view_reimbursement(current_user: dict, record: dict) -> bool:
    """Employees may only view their own records. Staff see all."""
    if current_user["role"] == "employee":
        return record["employee_name"] == current_user["employee_name"]
    return True
