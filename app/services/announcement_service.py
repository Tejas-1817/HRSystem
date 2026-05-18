import os
import uuid
import logging
import re
import threading
from datetime import datetime
from app.models.database import execute_query, execute_single
from app.config import Config

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB
ANNOUNCEMENT_SUBDIR = "announcements"


# ---------------------------------------------------------------------------
# Attachment File Handler
# ---------------------------------------------------------------------------

def save_attachment(file, username: str) -> str:
    """
    Validate and persist an announcement attachment (PDF/images).

    Validation:
      - Extension must be jpg/jpeg/png/pdf
      - File size must be ≤ 5 MB

    Storage: uploads/announcements/<username>/<uuid>_<filename>

    Returns the relative file path.
    Raises ValueError on validation failure.
    """
    if not file or file.filename == "":
        raise ValueError("No file provided.")

    filename = file.filename.lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Invalid file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Check file size
    content = file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError("File size exceeds the 5 MB limit.")
    file.seek(0)  # reset pointer

    # Build unique safe storage name
    safe_username = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
    unique_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    dir_path = os.path.join(Config.UPLOAD_FOLDER, ANNOUNCEMENT_SUBDIR, safe_username)
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, unique_name)
    file.save(file_path)

    logger.info(f"Announcement attachment saved: {file_path}")
    return file_path


# ---------------------------------------------------------------------------
# XSS Sanitizer Helper
# ---------------------------------------------------------------------------

def sanitize_html(text: str) -> str:
    """
    Perform safe lightweight sanitization to prevent XSS.
    Strips script tags, iframe tags, on* event handlers, and javascript: protocols.
    """
    if not text:
        return ""
    
    # 1. Remove script tags and content
    text = re.sub(r'(?i)<script.*?>.*?</script>', '', text, flags=re.DOTALL)
    
    # 2. Remove iframe tags and content
    text = re.sub(r'(?i)<iframe.*?>.*?</iframe>', '', text, flags=re.DOTALL)
    
    # 3. Strip inline event handlers: e.g. onclick="alert(1)", onmouseover='evil()'
    # Captures attributes starting with "on" followed by word characters and equal sign
    text = re.sub(r'(?i)\bon\w+\s*=\s*["\'].*?["\']', '', text)
    text = re.sub(r'(?i)\bon\w+\s*=\s*[^\s>]+', '', text)
    
    # 4. Block javascript: protocols in href attributes
    text = re.sub(r'(?i)href\s*=\s*["\']\s*javascript:.*?["\']', 'href="#"', text)
    
    return text


# ---------------------------------------------------------------------------
# RBAC Query Builder with Pagination
# ---------------------------------------------------------------------------

def get_announcements_paginated(user_role: str, filters: dict, page: int = 1, limit: int = 10) -> dict:
    """
    Fetches announcements with strict role-based access scoping and pagination.

    Visibility:
      - employee / manager -> Only show active, published announcements (status = 'published', expires_at > NOW())
      - hr / admin         -> See all announcements with optional filters (status, include_expired)

    Pagination details:
      page  -> 1-indexed page number
      limit -> Number of items per page
    """
    conditions = []
    params = []

    # 1. Scope based on role
    if user_role in ("employee", "manager"):
        conditions.append("status = 'published'")
        conditions.append("expires_at > NOW()")
    else:
        # HR and Admin optional filters
        if filters.get("status"):
            conditions.append("status = %s")
            params.append(filters["status"])
        
        # Expiry filtering: default is to show everything unless explicitly filtered
        if filters.get("active_only") in (True, "true", "1"):
            conditions.append("expires_at > NOW()")
        elif filters.get("expired_only") in (True, "true", "1"):
            conditions.append("expires_at <= NOW()")

    # Search filter
    if filters.get("q"):
        conditions.append("(title LIKE %s OR description LIKE %s)")
        search_term = f"%{filters['q']}%"
        params.extend([search_term, search_term])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count query
    count_query = f"SELECT COUNT(*) AS total FROM announcements {where}"
    total_row = execute_single(count_query, tuple(params) if params else None)
    total = total_row["total"] if total_row else 0

    # Calculate offset
    offset = max(0, (page - 1) * limit)

    # Fetch query
    fetch_query = f"""
        SELECT id, title, description, status, attachment_path, created_by, updated_by, created_at, updated_at, expires_at
        FROM announcements
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    
    fetch_params = list(params)
    fetch_params.extend([limit, offset])

    rows = execute_query(fetch_query, tuple(fetch_params))

    # Convert Datetime objects to ISO strings
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
        # Add a short description preview helper
        desc_stripped = re.sub('<[^<]+?>', '', r["description"])  # Strip HTML tags for preview
        r["short_description"] = desc_stripped[:120] + "..." if len(desc_stripped) > 120 else desc_stripped

    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return {
        "announcements": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


# ---------------------------------------------------------------------------
# Asynchronous Background Email Dispatcher
# ---------------------------------------------------------------------------

def _bg_send_emails(app, title: str, description: str, announcement_id: int):
    """Worker function to run in a background thread and send email alerts."""
    with app.app_context():
        try:
            logger.info("BG thread started to fetch employee emails for announcements...")
            
            # Fetch all distinct employee emails
            rows = execute_query("""
                SELECT DISTINCT email 
                FROM employee 
                WHERE email IS NOT NULL AND email != ''
            """)
            
            emails = [r["email"] for r in rows]
            if not emails:
                logger.info("No active employee email addresses found. Skipping email alerts.")
                return

            from app.utils.email_service import send_announcement_email
            
            logger.info(f"Dispatched background announcement email notification to {len(emails)} employees.")
            
            for email in emails:
                try:
                    send_announcement_email(email, title, description)
                except Exception as ex:
                    logger.error(f"Error sending announcement email to {email}: {ex}")

        except Exception as e:
            logger.error(f"Unhandled error in background email dispatch: {e}")


def dispatch_announcement_emails(app, title: str, description: str, announcement_id: int):
    """Spawns an asynchronous background thread to alert all employees."""
    thread = threading.Thread(
        target=_bg_send_emails,
        args=(app, title, description, announcement_id),
        daemon=True
    )
    thread.start()
    logger.info("Asynchronous background email dispatch thread spawned successfully.")
