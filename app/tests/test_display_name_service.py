"""
Unit Tests for Centralized Display Name Service
─────────────────────────────────────────────────
Tests all core functions that prevent name prefix corruption.

Usage:
    python -m pytest app/tests/test_display_name_service.py -v
    
    # Or run directly:
    python app/tests/test_display_name_service.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.utils.display_name_service import (
    strip_all_prefixes,
    get_clean_name,
    get_display_name,
    get_role_prefix,
    get_system_id,
    enrich_record_with_display_name,
    ROLE_PREFIX_MAP,
)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: strip_all_prefixes
# ═══════════════════════════════════════════════════════════════════════════

def test_strip_single_prefix():
    """Standard single-prefix stripping."""
    assert strip_all_prefixes("T_Kartik") == "Kartik"
    assert strip_all_prefixes("M_Tejas") == "Tejas"
    assert strip_all_prefixes("H_Riya") == "Riya"
    assert strip_all_prefixes("A_Santosh Jadhav") == "Santosh Jadhav"
    assert strip_all_prefixes("HR_Priya") == "Priya"
    assert strip_all_prefixes("TM_Omkar") == "Omkar"
    assert strip_all_prefixes("ADMIN_Shruti") == "Shruti"


def test_strip_double_prefix():
    """THE BUG: double-prefixed names must be fully cleaned."""
    assert strip_all_prefixes("A_A_Santosh Jadhav") == "Santosh Jadhav"
    assert strip_all_prefixes("M_M_Tejas") == "Tejas"
    assert strip_all_prefixes("T_T_Kartik") == "Kartik"
    assert strip_all_prefixes("H_H_Riya") == "Riya"


def test_strip_mixed_double_prefix():
    """Cross-role double prefixes (e.g., role changed from T_ to A_)."""
    assert strip_all_prefixes("A_T_Kartik") == "Kartik"
    assert strip_all_prefixes("M_T_Raj") == "Raj"
    assert strip_all_prefixes("T_M_Tejas") == "Tejas"
    assert strip_all_prefixes("H_A_Admin") == "Admin"


def test_strip_triple_prefix():
    """Triple stacked prefixes (edge case from multiple role changes)."""
    assert strip_all_prefixes("A_A_A_Santosh") == "Santosh"
    assert strip_all_prefixes("T_M_A_Name") == "Name"


def test_strip_no_prefix():
    """Clean names should pass through unchanged."""
    assert strip_all_prefixes("Santosh Jadhav") == "Santosh Jadhav"
    assert strip_all_prefixes("Kartik") == "Kartik"
    assert strip_all_prefixes("") == ""
    assert strip_all_prefixes(None) == ""


def test_strip_whitespace():
    """Leading/trailing whitespace should be handled."""
    assert strip_all_prefixes("  T_Kartik  ") == "Kartik"
    assert strip_all_prefixes("  A_A_Santosh  ") == "Santosh"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: get_clean_name (alias)
# ═══════════════════════════════════════════════════════════════════════════

def test_get_clean_name():
    """get_clean_name is an alias for strip_all_prefixes."""
    assert get_clean_name("A_A_Santosh Jadhav") == "Santosh Jadhav"
    assert get_clean_name("T_Kartik") == "Kartik"
    assert get_clean_name("Santosh") == "Santosh"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: get_role_prefix
# ═══════════════════════════════════════════════════════════════════════════

def test_get_role_prefix():
    """Verify standardized role → prefix mapping."""
    assert get_role_prefix("admin") == "A"
    assert get_role_prefix("hr") == "HR"
    assert get_role_prefix("manager") == "M"
    assert get_role_prefix("employee") == "TM"
    assert get_role_prefix("team_member") == "TM"
    assert get_role_prefix("unknown_role") == "TM"  # Default
    assert get_role_prefix("") == "TM"               # Empty
    assert get_role_prefix(None) == "TM"              # None


# ═══════════════════════════════════════════════════════════════════════════
# TEST: get_display_name
# ═══════════════════════════════════════════════════════════════════════════

def test_get_display_name():
    """Dynamic display name generation for each role."""
    assert get_display_name("Santosh Jadhav", "admin") == "A_Santosh Jadhav"
    assert get_display_name("Kartik", "employee") == "TM_Kartik"
    assert get_display_name("Riya", "hr") == "HR_Riya"
    assert get_display_name("Tejas", "manager") == "M_Tejas"
    assert get_display_name("Omkar", "team_member") == "TM_Omkar"


def test_get_display_name_strips_existing_prefix():
    """If a prefixed name is passed, it should strip first then re-prefix."""
    assert get_display_name("T_Kartik", "admin") == "A_Kartik"
    assert get_display_name("A_A_Santosh", "employee") == "TM_Santosh"
    assert get_display_name("M_Tejas", "hr") == "HR_Tejas"


def test_get_display_name_empty():
    """Empty/None names should return empty string."""
    assert get_display_name("", "admin") == ""
    assert get_display_name(None, "admin") == ""


# ═══════════════════════════════════════════════════════════════════════════
# TEST: get_system_id
# ═══════════════════════════════════════════════════════════════════════════

def test_get_system_id():
    """System ID should match display name format."""
    assert get_system_id("Kartik", "employee") == "TM_Kartik"
    assert get_system_id("Tejas", "manager") == "M_Tejas"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: enrich_record_with_display_name
# ═══════════════════════════════════════════════════════════════════════════

def test_enrich_record_basic():
    """Enrich a DB record with full_name and display_name."""
    record = {"name": "T_Kartik", "role": "employee", "original_name": "Kartik"}
    enriched = enrich_record_with_display_name(record)
    
    assert enriched["full_name"] == "Kartik"
    assert enriched["display_name"] == "TM_Kartik"
    assert enriched["name"] == "T_Kartik"  # Original DB key preserved


def test_enrich_record_uses_original_name():
    """Should prefer original_name over stripping prefix from name."""
    record = {"name": "T_Kartik", "role": "admin", "original_name": "Kartik Dahale"}
    enriched = enrich_record_with_display_name(record)
    
    assert enriched["full_name"] == "Kartik Dahale"
    assert enriched["display_name"] == "A_Kartik Dahale"


def test_enrich_record_without_original_name():
    """Falls back to stripping prefix if original_name is missing."""
    record = {"name": "A_A_Santosh Jadhav", "role": "admin"}
    enriched = enrich_record_with_display_name(record)
    
    assert enriched["full_name"] == "Santosh Jadhav"
    assert enriched["display_name"] == "A_Santosh Jadhav"


def test_enrich_record_none_input():
    """None/empty records should be handled gracefully."""
    assert enrich_record_with_display_name(None) is None
    assert enrich_record_with_display_name({}) == {}


def test_enrich_record_custom_fields():
    """Support for custom field name mappings (e.g., employee_name)."""
    record = {"employee_name": "M_Tejas", "role": "manager", "original_name": "Tejas"}
    enriched = enrich_record_with_display_name(record, name_field="employee_name")
    
    assert enriched["full_name"] == "Tejas"
    assert enriched["display_name"] == "M_Tejas"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Role change scenarios (regression tests for the original bug)
# ═══════════════════════════════════════════════════════════════════════════

def test_role_change_employee_to_admin():
    """Simulate: T_Kartik changes to admin → should produce A_Kartik, never A_T_Kartik."""
    old_name = "T_Kartik"
    clean = strip_all_prefixes(old_name)
    new_name = get_display_name(clean, "admin")
    
    assert clean == "Kartik"
    assert new_name == "A_Kartik"


def test_role_change_admin_to_manager():
    """Simulate: A_Santosh changes to manager → should produce M_Santosh, never M_A_Santosh."""
    old_name = "A_Santosh"
    clean = strip_all_prefixes(old_name)
    new_name = get_display_name(clean, "manager")
    
    assert clean == "Santosh"
    assert new_name == "M_Santosh"


def test_role_change_corrupted_double_prefix():
    """Simulate: A_A_Santosh (already corrupted) → should still produce correct result."""
    old_name = "A_A_Santosh Jadhav"
    clean = strip_all_prefixes(old_name)
    new_name = get_display_name(clean, "employee")
    
    assert clean == "Santosh Jadhav"
    assert new_name == "TM_Santosh Jadhav"


def test_multiple_role_changes():
    """Simulate 3 consecutive role changes — name should never accumulate prefixes."""
    name = "Santosh Jadhav"
    
    # Step 1: Created as employee
    system_name = get_display_name(name, "employee")
    assert system_name == "TM_Santosh Jadhav"
    
    # Step 2: Promoted to manager
    clean = strip_all_prefixes(system_name)
    system_name = get_display_name(clean, "manager")
    assert system_name == "M_Santosh Jadhav"
    assert clean == "Santosh Jadhav"
    
    # Step 3: Promoted to admin
    clean = strip_all_prefixes(system_name)
    system_name = get_display_name(clean, "admin")
    assert system_name == "A_Santosh Jadhav"
    assert clean == "Santosh Jadhav"
    
    # Step 4: Demoted back to employee
    clean = strip_all_prefixes(system_name)
    system_name = get_display_name(clean, "employee")
    assert system_name == "TM_Santosh Jadhav"
    assert clean == "Santosh Jadhav"


# ═══════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_functions = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    
    passed = 0
    failed = 0
    
    for test_fn in test_functions:
        try:
            test_fn()
            print(f"  ✅ {test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {test_fn.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'═' * 55}")
    print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'═' * 55}")
    
    sys.exit(1 if failed > 0 else 0)
