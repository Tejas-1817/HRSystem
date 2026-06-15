# ---------------------------------------------------------------------------
# Document Service — Onboarding Document Management
# ===========================================================================
# Encapsulates file validation, storage, CRUD, and verification workflow
# for the onboarding_documents table.  Follows the same patterns as
# reimbursement_service.py (file handling) and declaration_service.py
# (cursor-aware queries).
#
# Public API
# ----------
# - validate_upload_file(file)                 → (extension, mime_type, file_size)
# - save_onboarding_document(file, joinee_id, document_type) → (stored_filename, file_path, file_size, mime_type)
# - delete_document_file(file_path)            → bool
# - get_document_by_id(document_id, cursor)    → dict | None
# - get_documents_by_joinee(joinee_id, cursor) → list[dict]
# - insert_document_record(...)                → int (new id)
# - update_verification(...)                   → None
# - delete_document_record(document_id, cursor)→ None
# - check_auto_verify(joinee_id, cursor)       → bool  (triggers VERIFIED)
# ---------------------------------------------------------------------------

import os
import uuid
import logging
from app.config import Config
from app.models.database import execute_single, execute_query

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

ONBOARDING_UPLOAD_SUBDIR = "onboarding"

# Allowed document_type values (must match the DB ENUM + the user spec)
ALLOWED_DOCUMENT_TYPES = {
    "AADHAR", "PAN", "PASSPORT", "DEGREE_CERTIFICATE",
    "EXPERIENCE_LETTER", "OFFER_LETTER", "BANK_PASSBOOK",
    "PHOTO", "OTHER",
}

# MIME-type → extension mapping for validation
ALLOWED_MIME_TYPES = {
    "image/jpeg":       "jpg",
    "image/png":        "png",
    "image/webp":       "webp",
    "application/pdf":  "pdf",
}

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_LABEL_LENGTH = 255


# ═══════════════════════════════════════════════════════════════════════════
# File Validation
# ═══════════════════════════════════════════════════════════════════════════

def validate_upload_file(file):
    """
    Validate an uploaded file for the onboarding document workflow.

    Checks:
      - File is present and has a filename
      - Extension is in ALLOWED_EXTENSIONS
      - MIME type is in ALLOWED_MIME_TYPES
      - File size ≤ MAX_FILE_SIZE_BYTES

    Returns (extension, mime_type, file_size).
    Raises ValueError on any validation failure.
    """
    if not file or file.filename == "":
        raise ValueError("No file provided.")

    filename = file.filename.lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Invalid file type '.{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS)).upper()}"
        )

    # Determine MIME type from content_type header (Flask/Werkzeug sets this)
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Invalid MIME type '{mime_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES.keys()))}"
        )

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        limit_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise ValueError(f"File too large. Maximum allowed size is {limit_mb:.0f} MB.")

    if file_size == 0:
        raise ValueError("Uploaded file is empty.")

    return ext, mime_type, file_size


# ═══════════════════════════════════════════════════════════════════════════
# File Storage
# ═══════════════════════════════════════════════════════════════════════════

def save_onboarding_document(file, joinee_id, document_type):
    """
    Persist an uploaded onboarding document to the local filesystem.

    Storage path:  uploads/onboarding/<joinee_id>/<joinee_id>_<TYPE>_<uuid4_short>.<ext>

    Parameters
    ----------
    file : FileStorage
        The validated file object from Flask request.files.
    joinee_id : int
        The onboarding joinee's database ID.
    document_type : str
        The document type label (e.g. "PAN", "AADHAR").

    Returns
    -------
    tuple (stored_filename, relative_file_path, file_size, mime_type)
    """
    ext, mime_type, file_size = validate_upload_file(file)

    # Build secure unique filename: <joinee_id>_<TYPE>_<uuid4_short>.<ext>
    short_uuid = uuid.uuid4().hex[:8]
    stored_filename = f"{joinee_id}_{document_type}_{short_uuid}.{ext}"

    # Build directory path
    dir_path = os.path.join(
        Config.UPLOAD_FOLDER, ONBOARDING_UPLOAD_SUBDIR, str(joinee_id)
    )
    os.makedirs(dir_path, exist_ok=True)

    full_path = os.path.join(dir_path, stored_filename)
    file.save(full_path)

    # Store relative path in DB (consistent with reimbursement_service pattern)
    relative_path = os.path.join(dir_path, stored_filename)

    logger.info(
        "Onboarding document saved: joinee_id=%s, type=%s, path=%s",
        joinee_id, document_type, relative_path,
    )

    return stored_filename, relative_path, file_size, mime_type


def delete_document_file(file_path):
    """
    Remove a document file from local storage.

    Returns True if the file was deleted, False if it didn't exist.
    Logs errors but does not raise — file deletion failure should not
    block database cleanup.
    """
    if not file_path:
        return False
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Document file deleted: %s", file_path)
            return True
        else:
            logger.warning("Document file not found for deletion: %s", file_path)
            return False
    except OSError as e:
        logger.error("Failed to delete document file %s: %s", file_path, e)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Data Access — Read
# ═══════════════════════════════════════════════════════════════════════════

def get_document_by_id(document_id, cursor=None):
    """Fetch a single onboarding document by its primary key."""
    query = """
        SELECT od.*, oj.onboarding_status
        FROM   onboarding_documents od
        JOIN   onboarding_joinee oj ON oj.id = od.joinee_id
        WHERE  od.id = %s
    """
    if cursor:
        cursor.execute(query, (document_id,))
        return cursor.fetchone()
    return execute_single(query, (document_id,))


def get_documents_by_joinee(joinee_id, cursor=None):
    """
    Fetch all documents for a joinee.
    Excludes internal file_path for security — only returns safe columns.
    """
    query = """
        SELECT id, document_type, document_label, file_original_name,
               verification_status, rejection_reason,
               uploaded_at, verified_at
        FROM   onboarding_documents
        WHERE  joinee_id = %s
        ORDER  BY uploaded_at DESC
    """
    if cursor:
        cursor.execute(query, (joinee_id,))
        return cursor.fetchall()
    return execute_query(query, (joinee_id,)) or []


# ═══════════════════════════════════════════════════════════════════════════
# Data Access — Write (require a Transaction cursor)
# ═══════════════════════════════════════════════════════════════════════════

def insert_document_record(joinee_id, document_type, document_label,
                           file_original_name, file_path, file_size,
                           mime_type, cursor):
    """
    Insert a new document record into onboarding_documents.
    Returns the new document ID.
    """
    cursor.execute("""
        INSERT INTO onboarding_documents
            (joinee_id, document_type, document_label,
             file_original_name, file_path, file_size_bytes,
             mime_type, verification_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING')
    """, (
        joinee_id, document_type, document_label,
        file_original_name, file_path, file_size,
        mime_type,
    ))
    return cursor.lastrowid


def update_verification(document_id, status, rejection_reason,
                        verified_by, cursor):
    """
    Update verification status on a document.
    Sets verified_by and verified_at timestamp.
    """
    cursor.execute("""
        UPDATE onboarding_documents
        SET    verification_status = %s,
               rejection_reason = %s,
               verified_by = %s,
               verified_at = NOW()
        WHERE  id = %s
    """, (status, rejection_reason, verified_by, document_id))


def delete_document_record(document_id, cursor):
    """Delete a document record from the database."""
    cursor.execute(
        "DELETE FROM onboarding_documents WHERE id = %s",
        (document_id,),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Workflow — Auto-Verify Joinee
# ═══════════════════════════════════════════════════════════════════════════

def check_and_auto_verify_joinee(joinee_id, cursor):
    """
    After a document approval, check if ALL documents AND the declaration
    are APPROVED.  If so, automatically set onboarding_joinee status to
    VERIFIED.

    Returns True if auto-verification was triggered, False otherwise.
    """
    # 1. Check all documents approved
    cursor.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN verification_status = 'APPROVED' THEN 1 ELSE 0 END) AS approved
        FROM   onboarding_documents
        WHERE  joinee_id = %s
    """, (joinee_id,))
    doc_row = cursor.fetchone()

    if not doc_row or doc_row["total"] == 0 or doc_row["approved"] != doc_row["total"]:
        return False

    # 2. Check declaration approved
    cursor.execute("""
        SELECT status
        FROM   onboarding_declaration
        WHERE  joinee_id = %s
        ORDER  BY id DESC
        LIMIT  1
    """, (joinee_id,))
    decl_row = cursor.fetchone()

    if not decl_row or decl_row["status"] != "APPROVED":
        return False

    # 3. Auto-verify
    cursor.execute("""
        UPDATE onboarding_joinee
        SET    onboarding_status = 'VERIFIED'
        WHERE  id = %s
        AND    onboarding_status != 'VERIFIED'
    """, (joinee_id,))

    if cursor.rowcount > 0:
        logger.info(
            "Auto-verified joinee_id=%s (all documents + declaration approved)",
            joinee_id,
        )
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# Audit Logging
# ═══════════════════════════════════════════════════════════════════════════

def log_document_audit(joinee_id, action, new_value, performed_by,
                       notes=None, cursor=None):
    """
    Insert an audit log entry for a document-related action.
    If a cursor is provided, runs within that transaction.
    """
    query = """
        INSERT INTO onboarding_audit_log
            (joinee_id, action, new_value, performed_by, notes)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (joinee_id, action, new_value, performed_by, notes)

    if cursor:
        cursor.execute(query, params)
    else:
        execute_query(query, params, commit=True)


# ═══════════════════════════════════════════════════════════════════════════
# Response Helpers
# ═══════════════════════════════════════════════════════════════════════════

def serialize_document(doc):
    """
    Serialize a document dict for API response.
    Strips internal fields (file_path) and converts dates to ISO strings.
    """
    safe_fields = (
        "id", "document_type", "document_label", "file_original_name",
        "verification_status", "rejection_reason",
        "uploaded_at", "verified_at",
    )
    result = {}
    for key in safe_fields:
        val = doc.get(key)
        if val is not None and hasattr(val, "isoformat"):
            val = val.isoformat()
        result[key] = val
    return result
