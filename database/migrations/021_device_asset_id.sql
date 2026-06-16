-- ============================================================================
-- Migration 021: Device Asset ID
-- ============================================================================
-- Adds a custom asset_id column to the devices table.
-- Safe: Uses INFORMATION_SCHEMA checks — fully idempotent.
-- ============================================================================

USE hrms;

-- Custom Asset ID (e.g. "LT-2026-VASANTH")
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'asset_id'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN asset_id VARCHAR(100) UNIQUE NULL AFTER serial_number',
    'SELECT ''Column asset_id already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Migration 021 applied successfully.' AS status;
