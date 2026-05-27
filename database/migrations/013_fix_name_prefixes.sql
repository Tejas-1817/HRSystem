-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 013: Fix Name Prefix Corruption
-- ═══════════════════════════════════════════════════════════════════════════
-- 
-- Purpose:
--   1. Populate missing `original_name` values by stripping prefixes
--   2. Fix double-prefixed original_name entries (e.g., A_A_Santosh → Santosh)
--   3. Ensure data integrity across all linked tables
--
-- Safety: This migration only updates `original_name` fields (the clean name column).
--         It does NOT modify `employee.name` (the system FK key) to avoid breaking joins.
--
-- Prerequisites: Run database backup before executing.
-- ═══════════════════════════════════════════════════════════════════════════

USE hrms;

-- ─────────────────────────────────────────────────────────────────────────
-- Step 1: Fix employee.original_name where it's NULL
-- Derive clean name by stripping the known prefix from employee.name
-- ─────────────────────────────────────────────────────────────────────────

UPDATE employee
SET original_name = CASE
    WHEN name REGEXP '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)' THEN
        REGEXP_REPLACE(name, '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)+', '')
    ELSE name
END
WHERE original_name IS NULL OR original_name = '';

-- ─────────────────────────────────────────────────────────────────────────
-- Step 2: Fix double-prefixed original_name values
-- e.g., A_A_Santosh → Santosh, M_M_Tejas → Tejas
-- ─────────────────────────────────────────────────────────────────────────

UPDATE employee
SET original_name = REGEXP_REPLACE(original_name, '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)+', '')
WHERE original_name REGEXP '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)';

-- ─────────────────────────────────────────────────────────────────────────
-- Step 3: Fix users.original_name where it's NULL or corrupted
-- ─────────────────────────────────────────────────────────────────────────

UPDATE users
SET original_name = CASE
    WHEN original_name IS NULL OR original_name = '' THEN
        REGEXP_REPLACE(employee_name, '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)+', '')
    WHEN original_name REGEXP '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)' THEN
        REGEXP_REPLACE(original_name, '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)+', '')
    ELSE original_name
END
WHERE original_name IS NULL 
   OR original_name = ''
   OR original_name REGEXP '^(ADMIN_|HR_|TM_|A_|H_|M_|T_)';

-- ─────────────────────────────────────────────────────────────────────────
-- Step 4: Fix double-prefixed employee.name values (the actual corruption bug)
-- e.g., A_A_Santosh → A_Santosh (keep single correct prefix)
-- 
-- Strategy: Extract the clean name, then re-apply a single prefix from the
-- user's current role. This is done via the Python runner for safety.
-- ─────────────────────────────────────────────────────────────────────────

-- (Handled by run_013.py for complex cases requiring cascade rename)

-- ─────────────────────────────────────────────────────────────────────────
-- Verification Queries (Run after migration to confirm)
-- ─────────────────────────────────────────────────────────────────────────

-- Check for any remaining double-prefixed names:
-- SELECT name, original_name FROM employee WHERE name REGEXP '^[A-Z]+_[A-Z]+_';
-- SELECT employee_name, original_name FROM users WHERE employee_name REGEXP '^[A-Z]+_[A-Z]+_';

-- Check for NULL original_names:
-- SELECT id, name FROM employee WHERE original_name IS NULL;
-- SELECT id, employee_name FROM users WHERE original_name IS NULL;
