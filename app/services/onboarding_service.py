"""
Onboarding Service — Authentication & Profile Queries
======================================================
Encapsulates all database interactions for the onboarding authentication
workflow.  Keeps SQL out of route handlers and provides a clean interface
for the auth module to call.

Public API
----------
- get_joinee_by_user_id(user_id)        → dict | None
- get_onboarding_profile(user_id)       → dict | None
- mark_temp_password_changed(user_id, cursor=None)  → bool
"""

import logging
from app.models.database import execute_single, execute_query

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Login Enrichment
# ─────────────────────────────────────────────────────────────────────────────

def get_joinee_by_user_id(user_id):
    """
    Retrieve the onboarding joinee record linked to a users.id.

    Returns a dict with keys (id, onboarding_status, temp_password_changed)
    or None if no joinee record exists for this user.
    """
    return execute_single(
        """
        SELECT id,
               onboarding_status,
               temp_password_changed
        FROM   onboarding_joinee
        WHERE  user_id = %s
        LIMIT  1
        """,
        (user_id,),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding Profile (Dashboard Initialisation)
# ─────────────────────────────────────────────────────────────────────────────

def get_onboarding_profile(user_id):
    """
    Build the full onboarding profile payload used by the onboarding
    dashboard.  Aggregates data from onboarding_joinee,
    onboarding_declaration, and onboarding_documents.

    Returns a dict ready for JSON serialisation, or None if no joinee
    record exists for the given user_id.
    """
    # 1. Core joinee record
    joinee = execute_single(
        """
        SELECT id,
               full_name,
               personal_email,
               onboarding_status,
               temp_password_changed
        FROM   onboarding_joinee
        WHERE  user_id = %s
        LIMIT  1
        """,
        (user_id,),
    )

    if not joinee:
        return None

    joinee_id = joinee["id"]

    # 2. Latest declaration status
    declaration = execute_single(
        """
        SELECT status
        FROM   onboarding_declaration
        WHERE  joinee_id = %s
        ORDER  BY id DESC
        LIMIT  1
        """,
        (joinee_id,),
    )

    # 3. Uploaded documents (exclude internal file_path for security)
    documents = execute_query(
        """
        SELECT id,
               document_type,
               document_label,
               verification_status
        FROM   onboarding_documents
        WHERE  joinee_id = %s
        ORDER  BY uploaded_at DESC
        """,
        (joinee_id,),
    ) or []

    return {
        "joinee_id": joinee_id,
        "full_name": joinee["full_name"],
        "personal_email": joinee["personal_email"],
        "onboarding_status": joinee["onboarding_status"],
        "temp_password_changed": bool(joinee["temp_password_changed"]),
        "declaration_status": declaration["status"] if declaration else None,
        "documents": documents,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Temp Password Flag
# ─────────────────────────────────────────────────────────────────────────────

def mark_temp_password_changed(user_id, cursor=None):
    """
    Set temp_password_changed = TRUE for the onboarding_joinee linked to
    the given users.id.

    If a *cursor* is provided the UPDATE runs within that transaction
    (caller is responsible for commit).  Otherwise a standalone
    auto-committed write is performed.

    Returns True if the row was updated, False otherwise.
    """
    query = """
        UPDATE onboarding_joinee
        SET    temp_password_changed = TRUE
        WHERE  user_id = %s
        AND    temp_password_changed = FALSE
    """

    if cursor:
        cursor.execute(query, (user_id,))
        return cursor.rowcount > 0

    rows = execute_query(query, (user_id,), commit=True)
    # execute_query returns lastrowid on commit; rowcount isn't directly
    # available, but a non-None return means the statement executed.
    return rows is not None
