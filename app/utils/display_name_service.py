"""
Centralized Display Name Service
─────────────────────────────────
Single source of truth for identity management across the entire HRMS.

This module enforces the clean enterprise architecture rule:
  ✅ Database stores CLEAN names  (e.g., "Santosh Jadhav")
  ✅ Display names are identical to stored names

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

# All known legacy prefixes that may appear in older corrupted names
_ALL_KNOWN_PREFIXES = ["ADMIN_", "HR_", "TM_", "A_", "H_", "M_", "T_"]

# Compiled regex: matches one or MORE consecutive known prefixes at start.
_PREFIX_PATTERN = re.compile(
    r"^(?:" + "|".join(re.escape(p) for p in _ALL_KNOWN_PREFIXES) + r")+",
    re.IGNORECASE,
)


def strip_all_prefixes(name: str) -> str:
    """
    Remove ALL known legacy role prefixes from a name.
    """
    if not name:
        return ""
    return _PREFIX_PATTERN.sub("", name.strip())


def get_clean_name(possibly_prefixed_name: str) -> str:
    """
    Alias for strip_all_prefixes.
    """
    return strip_all_prefixes(possibly_prefixed_name)


def get_display_name(full_name: str, role: str = None) -> str:
    """
    Generate a display name. 
    In the modern architecture, this just returns the clean name.
    The role parameter is kept for backward API compatibility.
    """
    clean = strip_all_prefixes(full_name)
    if not clean:
        return ""
    return clean


def get_system_id(full_name: str, role: str = None) -> str:
    """
    Generate a system identifier (used as the DB key in employee.name).
    In the modern architecture, this is just the clean name.
    """
    return get_display_name(full_name, role)


def enrich_record_with_display_name(record: dict, name_field: str = "name",
                                      role_field: str = "role") -> dict:
    """
    Add `full_name` and `display_name` fields to an API response dict.
    Both will contain the clean name.
    """
    if not record or not isinstance(record, dict):
        return record

    raw_name = record.get(name_field, "") or ""
    clean = strip_all_prefixes(raw_name)

    record["full_name"] = clean
    record["display_name"] = clean

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
