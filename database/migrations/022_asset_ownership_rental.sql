-- ============================================================================
-- Migration 022: Asset Ownership Type & Rental Vendor Details
-- ============================================================================
-- Adds ownership_type (Purchased / Rented) to devices, plus vendor and
-- rental-period fields used when an asset is rented rather than purchased.
-- Safe: Uses INFORMATION_SCHEMA checks — fully idempotent.
-- ============================================================================

USE hrms;

-- 1. ownership_type: Purchased (default) or Rented
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'ownership_type'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN ownership_type ENUM(''Purchased'', ''Rented'') NOT NULL DEFAULT ''Purchased'' AFTER location',
    'SELECT ''Column ownership_type already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. vendor_name: rental vendor / leasing company name
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'vendor_name'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN vendor_name VARCHAR(150) NULL AFTER ownership_type',
    'SELECT ''Column vendor_name already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. vendor_contact: phone / email of the vendor point of contact
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'vendor_contact'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN vendor_contact VARCHAR(150) NULL AFTER vendor_name',
    'SELECT ''Column vendor_contact already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. rental_start_date
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'rental_start_date'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN rental_start_date DATE NULL AFTER vendor_contact',
    'SELECT ''Column rental_start_date already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. rental_end_date
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'rental_end_date'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN rental_end_date DATE NULL AFTER rental_start_date',
    'SELECT ''Column rental_end_date already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 6. rental_cost: periodic rental amount
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'rental_cost'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN rental_cost DECIMAL(12,2) NULL AFTER rental_end_date',
    'SELECT ''Column rental_cost already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 7. rental_cost_frequency: how often rental_cost is billed
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'rental_cost_frequency'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN rental_cost_frequency ENUM(''Monthly'', ''Quarterly'', ''Yearly'', ''One-time'') NULL AFTER rental_cost',
    'SELECT ''Column rental_cost_frequency already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 8. Index for filtering by ownership type (e.g. "show all rented assets")
SET @idx = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND INDEX_NAME = 'idx_device_ownership_type'
);
SET @sql = IF(@idx = 0,
    'ALTER TABLE devices ADD INDEX idx_device_ownership_type (ownership_type)',
    'SELECT ''Index idx_device_ownership_type already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Migration 022 applied successfully.' AS status;
