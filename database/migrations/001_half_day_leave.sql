-- =============================================================================
-- Migration 001: Half-Day Leave Support
-- Description : Extends `leaves` with half-day metadata and converts
--               `leave_balance.used_leaves` to DECIMAL so 0.5-day deductions
--               are stored accurately.
-- Safe        : Uses ADD COLUMN IF NOT EXISTS and MODIFY so it is idempotent.
-- =============================================================================

USE starterdata;

-- ---------------------------------------------------------------------------
-- Step 1: Add half-day columns to `leaves`
-- ---------------------------------------------------------------------------

-- leave_type_category: 'full_day' (default) or 'half_day'
ALTER TABLE leaves
  ADD COLUMN IF NOT EXISTS leave_type_category
    ENUM('full_day', 'half_day') NOT NULL DEFAULT 'full_day'
    AFTER leave_type;

-- half_day_period: NULL for full-day; 'first_half' or 'second_half' for half-day
ALTER TABLE leaves
  ADD COLUMN IF NOT EXISTS half_day_period
    ENUM('first_half', 'second_half') NULL
    AFTER leave_type_category;

-- leave_duration: server-calculated; 1.00 for full-day, 0.50 for half-day
ALTER TABLE leaves
  ADD COLUMN IF NOT EXISTS leave_duration
    DECIMAL(4,2) NOT NULL DEFAULT 1.00
    AFTER half_day_period;

-- ---------------------------------------------------------------------------
-- Step 2: Convert leave_balance.used_leaves from INT to DECIMAL(6,2)
--         All existing integers are preserved (12 → 12.00, 0 → 0.00)
-- ---------------------------------------------------------------------------

ALTER TABLE leave_balance
  MODIFY COLUMN used_leaves DECIMAL(6,2) NOT NULL DEFAULT 0.00;

-- Also widen total_leaves for consistency (allows fractional totals in future)
ALTER TABLE leave_balance
  MODIFY COLUMN total_leaves DECIMAL(6,2) NOT NULL DEFAULT 0.00;

-- ---------------------------------------------------------------------------
-- Step 3: Back-fill existing leave records
--         All old records had no category column → force full_day / 1.00
-- ---------------------------------------------------------------------------

UPDATE leaves
SET
  leave_type_category = 'full_day',
  leave_duration      = 1.00
WHERE leave_type_category IS NULL
   OR leave_duration IS NULL;

-- Done.
SELECT 'Migration 001 applied successfully.' AS status;
