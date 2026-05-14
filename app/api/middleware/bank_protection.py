"""
Bank Details Protection Middleware

Provides the `bank_edit_protected` decorator — a backend enforcement layer
that blocks ALL bank detail mutation requests when the BANK_DETAILS_EDITABLE
feature flag is disabled.

Security design:
  • Enforced at the API layer, BEFORE any handler logic executes.
  • Bypasses all RBAC — no role (including admin) can circumvent this lock.
  • Audit logs every blocked attempt without exposing sensitive field values.
  • Returns a standardised 403 JSON response for consistent frontend handling.

Usage:
    from app.api.middleware.bank_protection import bank_edit_protected

    @bank_bp.route('/my', methods=['POST', 'PUT'])
    @token_required
    @bank_edit_protected          # ← place AFTER auth decorator
    def upsert_my_bank_details(current_user):
        ...
"""

import logging
from functools import wraps

from flask import request, jsonify, g

from app.config.feature_flags import FeatureFlags
from app.models.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Standardised 403 response body
# ─────────────────────────────────────────────────────────────────────────────
_LOCKED_RESPONSE = {
    "success": False,
    "message": (
        "Bank details editing is currently disabled. "
        "Please contact your administrator."
    ),
    "error_code": "BANK_EDIT_LOCKED",
}


def _get_client_ip() -> str:
    """
    Resolve the real client IP, honouring common reverse-proxy headers.
    Falls back to the direct WSGI remote address.
    """
    # X-Forwarded-For may contain a comma-separated chain; take the leftmost
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def _write_audit_log(current_user: dict) -> None:
    """
    Persist a BLOCKED attempt to audit_logs.

    Fields logged  (no banking field values are ever written):
      - user_id       — from JWT payload
      - event_type    — "bank_edit_blocked"
      - description   — employee name, role, HTTP method, path, client IP
    """
    try:
        employee_name = current_user.get("employee_name", "unknown")
        role          = current_user.get("role", "unknown")
        method        = request.method
        path          = request.path
        ip            = _get_client_ip()
        user_id       = current_user.get("user_id")

        description = (
            f"BLOCKED: Team Member '{employee_name}' (role: {role}) "
            f"attempted {method} on {path} from IP {ip}"
        )

        # Resolve user_id from DB if JWT payload didn't carry it
        if not user_id:
            user_row = execute_single(
                "SELECT id FROM users WHERE employee_name = %s", (employee_name,)
            )
            user_id = user_row["id"] if user_row else None

        execute_query(
            "INSERT INTO audit_logs (user_id, event_type, description) "
            "VALUES (%s, %s, %s)",
            (user_id, "bank_edit_blocked", description),
            commit=True,
        )

        logger.warning(
            "[BankProtection] %s | user=%s | role=%s | ip=%s",
            description,
            employee_name,
            role,
            ip,
        )

    except Exception as exc:  # pragma: no cover — audit failure must never 500 the app
        logger.error("[BankProtection] Failed to write audit log: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Public decorator
# ─────────────────────────────────────────────────────────────────────────────

def bank_edit_protected(f):
    """
    Decorator: blocks bank-detail mutations when BANK_DETAILS_EDITABLE is False.

    Stack order (innermost executes first):
        @bank_bp.route(...)
        @token_required          ← authenticates, injects current_user
        @bank_edit_protected     ← this decorator, must be AFTER auth
        def handler(current_user): ...

    When the flag is False:
      1. Writes an audit log entry (no sensitive values included).
      2. Returns HTTP 403 with the standardised JSON error body.
      3. The actual handler function is NEVER called.

    When the flag is True (editing re-enabled):
      • Passes through transparently — zero performance overhead beyond the
        attribute lookup.
    """
    @wraps(f)
    def protected_view(*args, **kwargs):
        # ── Flag check ────────────────────────────────────────────────────────
        if not FeatureFlags.BANK_DETAILS_EDITABLE:
            # current_user is always present because @token_required ran first
            current_user = kwargs.get("current_user") or (
                args[0] if args else {}
            )
            _write_audit_log(current_user)
            return jsonify(_LOCKED_RESPONSE), 403

        # ── Flag is True — pass through ───────────────────────────────────────
        return f(*args, **kwargs)

    return protected_view
