"""
Centralized Display Name Service
─────────────────────────────────
Single source of truth for role prefix management across the entire HRMS.

This module enforces the enterprise architecture rule:
  ✅ Database stores CLEAN names  (e.g., "Santosh Jadhav")
  ✅ Display names are generated DYNAMICALLY at runtime

Usage:
    from app.utils.display_name_service import (
        strip_all_prefixes,
        get_display_name,
        get_clean_name,
        enrich_record_with_display_name,
    )
"""

import re
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# ROLE PREFIX STANDARDS (Canonical Mapping)
# ═══════════════════════════════════════════════════════════════════════════

ROLE_PREFIX_MAP = {
    "admin":       "A",
    "hr":          "HR",
    "manager":     "M",
    "team_member": "TM",
}

# All known prefixes that may appear in stored names (legacy + current).
# Ordered longest-first so "HR_" matches before "H_".
_ALL_KNOWN_PREFIXES = ["ADMIN_", "HR_", "TM_", "A_", "H_", "M_", "T_"]

# Compiled regex: matches one or MORE consecutive known prefixes at start.
# e.g.  "A_A_Santosh"  →  strips "A_A_"
#        "T_Kartik"     →  strips "T_"
#        "HR_Riya"      →  strips "HR_"
#        "M_M_M_Tejas"  →  strips "M_M_M_"
_PREFIX_PATTERN = re.compile(
    r"^(?:" + "|".join(re.escape(p) for p in _ALL_KNOWN_PREFIXES) + r")+",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def strip_all_prefixes(name: str) -> str:
    """
    Remove ALL known role prefixes (including repeated/stacked ones) from a name.

    Examples:
        "A_A_Santosh Jadhav"   → "Santosh Jadhav"
        "T_Kartik"             → "Kartik"
        "HR_Riya"              → "Riya"
        "M_M_Tejas"            → "Tejas"
        "ADMIN_John"           → "John"
        "Santosh Jadhav"       → "Santosh Jadhav"  (no prefix — no change)
        ""                     → ""
        None                   → ""
    """
    if not name:
        return ""
    return _PREFIX_PATTERN.sub("", name.strip())


def get_clean_name(possibly_prefixed_name: str) -> str:
    """
    Alias for strip_all_prefixes — extracts the clean human name from
    any potentially corrupted/prefixed name string.

    This is the safe function to call when you don't know if a name
    has a prefix or not.
    """
    return strip_all_prefixes(possibly_prefixed_name)


def get_role_prefix(role: str) -> str:
    """
    Get the standardized prefix string for a given role.

    Returns:
        The prefix WITHOUT trailing underscore (e.g., "A", "HR", "M", "TM").
        Defaults to "TM" for unknown roles.
    """
    if not role:
        return "TM"
    return ROLE_PREFIX_MAP.get(role.lower(), "TM")


def get_display_name(full_name: str, role: str) -> str:
    """
    Generate a display name by prepending the role prefix to the clean name.
    This should ONLY be used for rendering — never for database storage.

    Examples:
        ("Santosh Jadhav", "admin")    → "A_Santosh Jadhav"
        ("Kartik", "employee")         → "TM_Kartik"
        ("Riya", "hr")                 → "HR_Riya"
        ("Tejas", "manager")           → "M_Tejas"
    """
    clean = strip_all_prefixes(full_name)
    if not clean:
        return ""
    prefix = get_role_prefix(role)
    return f"{prefix}_{clean}"


def get_system_id(full_name: str, role: str) -> str:
    """
    Generate a system identifier (used as the DB key in employee.name).
    This is the prefixed form that serves as the FK across tables.

    Functionally identical to get_display_name but semantically distinct:
    - get_display_name → for UI rendering
    - get_system_id    → for database identity
    """
    return get_display_name(full_name, role)


# ═══════════════════════════════════════════════════════════════════════════
# API RESPONSE ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════

def enrich_record_with_display_name(record: dict, name_field: str = "name",
                                      role_field: str = "role") -> dict:
    """
    Add `full_name` and `display_name` fields to an API response dict.

    Uses `original_name` if available (preferred), otherwise strips prefixes
    from the `name_field`.

    Args:
        record:     Dictionary (e.g., a row from the DB)
        name_field: Key containing the (possibly prefixed) name
        role_field: Key containing the role

    Returns:
        The same dict, mutated with `full_name` and `display_name` keys added.

    Example output:
        {
            "name": "T_Kartik",       # existing DB key (unchanged)
            "full_name": "Kartik",    # clean human name
            "display_name": "TM_Kartik",  # dynamic prefix based on current role
            ...
        }
    """
    if not record or not isinstance(record, dict):
        return record

    # Prefer original_name if available; fall back to stripping prefix from name
    raw_name = record.get(name_field, "") or ""
    original = record.get("original_name") or strip_all_prefixes(raw_name)

    role = record.get(role_field, "employee") or "employee"

    record["full_name"] = original
    record["display_name"] = get_display_name(original, role) if original else ""

    return record


def enrich_list_with_display_names(records: list, name_field: str = "name",
                                     role_field: str = "role") -> list:
    """
    Batch version of enrich_record_with_display_name for list results.
    """
    if not records:
        return records
    for record in records:
        enrich_record_with_display_name(record, name_field, role_field)
    return records
