-- ============================================================================
-- Migration 020: Device Hardware Specifications
-- ============================================================================
-- Adds processor, ram, and storage columns to the devices table so that
-- asset detail pages can display hardware specifications.
-- Safe: Uses INFORMATION_SCHEMA checks — fully idempotent.
-- ============================================================================

USE hrms;

-- 1. Processor (e.g. "Intel Core i7-13700H", "Apple M2 Pro")
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'processor'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN processor VARCHAR(150) NULL AFTER location',
    'SELECT ''Column processor already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. RAM (e.g. "16 GB", "32 GB DDR5")
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'ram'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN ram VARCHAR(50) NULL AFTER processor',
    'SELECT ''Column ram already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. Storage (e.g. "512 GB SSD", "1 TB NVMe")
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'devices'
      AND COLUMN_NAME = 'storage'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE devices ADD COLUMN storage VARCHAR(100) NULL AFTER ram',
    'SELECT ''Column storage already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Migration 020 applied successfully.' AS status;
