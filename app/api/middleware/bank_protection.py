"""
Bank Protection Middleware
===========================
Reusable Flask decorator that enforces the BANK_DETAILS_EDITABLE feature flag.

How it works:
    1. Checks `is_bank_editable()` before the decorated view executes.
    2. If editing is disabled, it:
       a. Writes an audit-log record (user, role, action, IP, timestamp).
       b. Returns HTTP 403 with a standardised JSON body.
       c. Never touches the database.
    3. If editing is enabled, the view runs normally.

Usage (in bank_routes.py):
    from app.api.middleware.bank_protection import bank_write_protected

    @bank_bp.route('/my', methods=['POST', 'PUT'])
    @token_required                   # authenticate first
    @bank_write_protected             # then enforce write lock
    def upsert_my_bank_details(current_user):
        ...

Security notes:
    • Applied AFTER authentication — we always know who attempted the action.
    • Decorator order matters: place @bank_write_protected after @token_required
      / @role_required so current_user is already resolved.
    • No sensitive banking data (account numbers, IFSC, etc.) is ever written
      to audit logs — only metadata (who, when, from where, what action).
"""

import logging
from functools import wraps
from flask import request, jsonify
from app.config.feature_flags import is_bank_editable
from app.models.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# ── Standardised 403 response body ────────────────────────────────────────
_BLOCKED_RESPONSE = {
    "success": False,
    "message": "Bank details editing is currently disabled",
    "code": "BANK_DETAILS_LOCKED",
    "hint": "Bank information is read-only at this time. Please contact your administrator.",
}


def _get_client_ip() -> str:
    """
    Extract the real client IP, respecting common reverse-proxy headers.
    Falls back to REMOTE_ADDR when no proxy header is present.
    """
    # X-Forwarded-For can contain a comma-separated chain; take the first entry
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _log_blocked_attempt(current_user: dict) -> None:
    """
    Write a compliance audit record for a blocked bank-write attempt.

    Fields logged:
        user_id        — internal user PK
        role           — user's role at the time of attempt
        attempted_action — HTTP method + URL path
        ip_address     — client IP
        event_type     — fixed string 'bank_write_blocked'

    Fields intentionally NOT logged (data-minimisation / PCI compliance):
        account_number, IFSC, bank_name, UPI ID, or any other banking payload.
    """
    try:
        user_id  = current_user.get("user_id")
        role     = current_user.get("role", "unknown")
        emp_name = current_user.get("employee_name", "unknown")
        method   = request.method
        path     = request.path
        ip       = _get_client_ip()

        description = (
            f"[BLOCKED] User '{emp_name}' (role={role}, id={user_id}) "
            f"attempted to modify protected bank details — "
            f"{method} {path} from {ip}"
        )

        execute_query(
            """
            INSERT INTO audit_logs (user_id, event_type, description)
            VALUES (%s, %s, %s)
            """,
            (user_id, "bank_write_blocked", description),
            commit=True,
        )

        logger.warning(description)

    except Exception as exc:
        # Audit logging must never crash the main response path.
        logger.error(
            "Failed to write bank_write_blocked audit log: %s", exc, exc_info=True
        )


# ---------------------------------------------------------------------------
# Public decorator
# ---------------------------------------------------------------------------

def bank_write_protected(f):
    """
    Decorator: blocks the decorated view and returns 403 if
    `is_bank_editable()` returns False.

    Apply AFTER @token_required / @role_required so that `current_user`
    is already available in kwargs.

    Example:
        @bank_bp.route('/my', methods=['POST', 'PUT'])
        @token_required
        @bank_write_protected
        def upsert_my_bank_details(current_user):
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_bank_editable():
            # Resolve current_user from kwargs (set by @token_required)
            current_user = kwargs.get("current_user", {})
            _log_blocked_attempt(current_user)
            return jsonify(_BLOCKED_RESPONSE), 403

        return f(*args, **kwargs)

    return decorated
