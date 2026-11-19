-- ============================================================================
-- Migration 035: Return to Vendor Enhancement
-- ============================================================================
-- Extends devices.status to support 'Returned to Vendor'.
-- Adds vendor return tracking columns (vendor_return_date, vendor_return_reason, vendor_return_reference).
-- Extends asset_stock_log.action ENUM to support 'returned_to_vendor'.
-- Safe & idempotent.
-- ============================================================================

USE hrms;

-- 1. Modify devices.status ENUM to include 'Returned to Vendor'
ALTER TABLE devices 
    MODIFY COLUMN status ENUM('Available', 'Assigned', 'Under Repair', 'Retired', 'Returned to Vendor') NOT NULL DEFAULT 'Available';

-- 2. Add vendor_return_date column to devices
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'vendor_return_date'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN vendor_return_date DATE NULL AFTER next_due_date',
    'SELECT "Column vendor_return_date already exists."'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. Add vendor_return_reason column to devices
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'vendor_return_reason'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN vendor_return_reason TEXT NULL AFTER vendor_return_date',
    'SELECT "Column vendor_return_reason already exists."'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. Add vendor_return_reference column to devices
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'vendor_return_reference'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN vendor_return_reference VARCHAR(100) NULL AFTER vendor_return_reason',
    'SELECT "Column vendor_return_reference already exists."'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. Modify asset_stock_log.action ENUM to include 'returned_to_vendor'
ALTER TABLE asset_stock_log 
    MODIFY COLUMN action ENUM('added','assigned','returned','repair_in','repair_out','retired','deleted','status_change','returned_to_vendor') NOT NULL;

SELECT 'Migration 035 applied successfully.' AS status;
