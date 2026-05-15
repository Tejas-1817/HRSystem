"""
Team Member Profile Routes — /profile/<employee_name>

This module provides the missing endpoint that the HRMS frontend calls when
HR clicks on a team member card.  Previously this route did NOT exist, which
is why Flask returned an unhandled error (500/404) when called.

Registered prefix:  /profile
Example URL:        /profile/T_Tejas%20Vatane

RBAC:
  - admin / hr  → can view any team member profile
  - manager     → can view profiles of team members assigned to their projects
  - team_member / employee → can only view their own profile

Safe Slug / URL Generation:
  - URL-decodes the employee_name path segment automatically (handles %20, +, etc.)
  - Validates the name against an allowlist regex (alphanumeric, _, space, hyphen)
  - Returns structured JSON; NEVER leaks stack traces to the client
"""

from flask import Blueprint, jsonify, request
from urllib.parse import unquote_plus
import re
import logging

from app.api.middleware.auth import token_required
from app.models.database import execute_single, execute_query
from app.api.routes.employee_routes import serialize_employee

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

# ── Validation ─────────────────────────────────────────────────────────────

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-\. ]{1,120}$")


def _decode_and_validate(raw: str):
    """
    URL-decode the path segment and validate it is safe.

    Returns (decoded_name, error_message).
    If validation passes, error_message is None.
    """
    try:
        # Handle both %20-style and +-style encoding
        decoded = unquote_plus(raw).strip()
    except Exception:
        return None, "Invalid URL encoding in employee name"

    if not decoded:
        return None, "Employee name cannot be empty"

    if not _SAFE_NAME_RE.match(decoded):
        return None, "Employee name contains invalid characters"

    return decoded, None


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_profile_query():
    """
    Full profile query: employee + user role + leave summary + project utilization.
    Returns the SQL string (parameterised with one placeholder: employee name).
    """
    return """
        SELECT
            e.*,
            u.role,
            u.username,
            u.is_active,
            u.created_at        AS account_created_at,
            COALESCE(lb.total,  0)   AS total_leaves,
            COALESCE(lb.used,   0)   AS used_leaves,
            COALESCE(lb.remaining,0) AS remaining_leaves,
            COALESCE(util.total_utilization, 0)                        AS total_utilization,
            GREATEST(0, 100 - COALESCE(util.total_utilization, 0))     AS remaining_availability
        FROM employee e
        LEFT JOIN users u ON e.name = u.employee_name
        LEFT JOIN (
            SELECT employee_name,
                   SUM(total_leaves)              AS total,
                   SUM(used_leaves)               AS used,
                   SUM(total_leaves - used_leaves) AS remaining
            FROM leave_balance
            GROUP BY employee_name
        ) lb ON e.name = lb.employee_name
        LEFT JOIN (
            SELECT pa.employee_name,
                   SUM(pa.billable_percentage) AS total_utilization
            FROM project_assignments pa
            JOIN projects p ON pa.project_id = p.id
            WHERE p.status NOT IN ('completed', 'closed', 'cancelled')
            GROUP BY pa.employee_name
        ) util ON e.name = util.employee_name
        WHERE e.name = %s
        LIMIT 1
    """


def _get_active_projects(employee_name: str):
    """Return lightweight list of projects the team member is currently assigned to."""
    try:
        return execute_query(
            """
            SELECT p.project_id, p.name, p.status,
                   pa.billable_percentage, pa.is_billable
            FROM project_assignments pa
            JOIN projects p ON pa.project_id = p.id
            WHERE pa.employee_name = %s
              AND p.status NOT IN ('completed', 'closed', 'cancelled')
            ORDER BY p.name ASC
            """,
            (employee_name,),
        ) or []
    except Exception as exc:
        logger.warning("Could not fetch projects for %s: %s", employee_name, exc)
        return []


def _get_leave_breakdown(employee_name: str):
    """Return per-leave-type breakdown for the team member."""
    try:
        return execute_query(
            """
            SELECT leave_type, total_leaves, used_leaves,
                   (total_leaves - used_leaves) AS remaining_leaves
            FROM leave_balance
            WHERE employee_name = %s
            ORDER BY leave_type
            """,
            (employee_name,),
        ) or []
    except Exception as exc:
        logger.warning("Could not fetch leave breakdown for %s: %s", employee_name, exc)
        return []


# ── RBAC helper ────────────────────────────────────────────────────────────

def _can_view(current_user: dict, target_employee_name: str) -> bool:
    """
    Return True if the requesting user is authorised to view this profile.

      admin / hr   → always
      manager      → only if the target is on one of their projects
      others       → only their own profile
    """
    role = current_user.get("role", "")
    requester_name = current_user.get("employee_name", "")

    if role in ("admin", "hr"):
        return True

    # Own profile is always visible
    if requester_name == target_employee_name:
        return True

    if role == "manager":
        # Manager can see team members who share a project with them
        try:
            shared = execute_single(
                """
                SELECT 1 FROM project_assignments pa_manager
                JOIN project_assignments pa_target
                  ON pa_manager.project_id = pa_target.project_id
                WHERE pa_manager.employee_name = %s
                  AND pa_target.employee_name  = %s
                LIMIT 1
                """,
                (requester_name, target_employee_name),
            )
            return shared is not None
        except Exception as exc:
            logger.warning("RBAC project check failed: %s", exc)
            return False

    return False


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@profile_bp.route("/<path:employee_name_raw>", methods=["GET"])
@token_required
def get_team_member_profile(current_user, employee_name_raw):
    """
    GET /profile/<employee_name>

    Fetch full profile for a team member by their system name (e.g. T_Tejas Vatane).
    The name is URL-decoded automatically so %20 spaces work correctly.

    Response shape:
    {
        "success": true,
        "data": {
            "profile":        { ...employee fields... },
            "active_projects": [...],
            "leave_breakdown": [...]
        }
    }
    """
    # ── 1. Decode & sanitize the URL segment ──────────────────────────────
    employee_name, decode_err = _decode_and_validate(employee_name_raw)
    if decode_err:
        logger.warning(
            "Profile request with invalid name segment '%s' from user %s",
            employee_name_raw,
            current_user.get("employee_name"),
        )
        return jsonify({"success": False, "message": decode_err}), 400

    logger.info(
        "Profile request for '%s' by %s (%s)",
        employee_name,
        current_user.get("employee_name"),
        current_user.get("role"),
    )

    # ── 2. RBAC check ─────────────────────────────────────────────────────
    if not _can_view(current_user, employee_name):
        logger.warning(
            "Unauthorised profile access: %s (%s) tried to view %s",
            current_user.get("employee_name"),
            current_user.get("role"),
            employee_name,
        )
        return jsonify({
            "success": False,
            "message": "You are not authorised to view this team member's profile.",
        }), 403

    # ── 3. Fetch profile record ────────────────────────────────────────────
    try:
        profile = execute_single(_build_profile_query(), (employee_name,))
    except Exception as exc:
        logger.error(
            "Database error fetching profile for '%s': %s",
            employee_name,
            exc,
            exc_info=True,
        )
        return jsonify({
            "success": False,
            "message": "A database error occurred. Please try again later.",
        }), 500

    # ── 4. Graceful 404 (no crash) ─────────────────────────────────────────
    if not profile:
        logger.info("Profile not found for employee name: '%s'", employee_name)
        return jsonify({
            "success": False,
            "message": f"Team member '{employee_name}' was not found.",
        }), 404

    # ── 5. Serialize (safe datetime / decimal conversion) ─────────────────
    try:
        serialized = serialize_employee(profile)
    except Exception as exc:
        logger.error(
            "Serialization error for profile '%s': %s",
            employee_name,
            exc,
            exc_info=True,
        )
        return jsonify({
            "success": False,
            "message": "Failed to format profile data.",
        }), 500

    # ── 6. Fetch supplementary data (non-fatal if they fail) ──────────────
    active_projects = _get_active_projects(employee_name)
    leave_breakdown = _get_leave_breakdown(employee_name)

    # ── 7. Return structured response ─────────────────────────────────────
    return jsonify({
        "success": True,
        "data": {
            "profile": serialized,
            "active_projects": active_projects,
            "leave_breakdown": leave_breakdown,
        },
    }), 200


# ── Utility: safe slug generator ──────────────────────────────────────────

def build_profile_url(employee_name: str, base_url: str = "") -> str:
    """
    Generate a safe, URL-encoded profile URL for a given employee system name.

    Usage (frontend / email templates):
        url = build_profile_url("T_Tejas Vatane")
        # → "/profile/T_Tejas%20Vatane"
    """
    from urllib.parse import quote
    safe_segment = quote(employee_name, safe="")
    return f"{base_url}/profile/{safe_segment}"
