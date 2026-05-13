-- ============================================================================
-- Migration 010: Device Inventory & Stock Management
-- ============================================================================
-- Adds asset_catalog for SKU-level tracking, asset_stock_log for immutable
-- stock-change audit trail, and extends devices with purchase metadata.
-- All statements are idempotent (IF NOT EXISTS / dynamic column checks).
-- ============================================================================

USE hrms;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. asset_catalog: SKU-level metadata for grouping and purchase tracking
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS asset_catalog (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    category            VARCHAR(50) NOT NULL,
    brand               VARCHAR(100) NOT NULL,
    model               VARCHAR(100) NOT NULL,
    specifications      TEXT NULL,
    unit_cost           DECIMAL(12,2) NULL,
    vendor              VARCHAR(150) NULL,
    low_stock_threshold INT NOT NULL DEFAULT 3,
    notes               TEXT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_catalog_sku (brand, model),
    INDEX idx_catalog_category (category)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Extend devices table with purchase metadata and catalog linkage
-- ─────────────────────────────────────────────────────────────────────────────

-- catalog_id: link to asset_catalog
SET @col = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND COLUMN_NAME = 'catalog_id');
SET @sql = IF(@col = 0,
    'ALTER TABLE devices ADD COLUMN catalog_id INT NULL AFTER updated_at',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- purchase_date
SET @col = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND COLUMN_NAME = 'purchase_date');
SET @sql = IF(@col = 0,
    'ALTER TABLE devices ADD COLUMN purchase_date DATE NULL AFTER catalog_id',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- warranty_expiry
SET @col = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND COLUMN_NAME = 'warranty_expiry');
SET @sql = IF(@col = 0,
    'ALTER TABLE devices ADD COLUMN warranty_expiry DATE NULL AFTER purchase_date',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- condition_notes
SET @col = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND COLUMN_NAME = 'condition_notes');
SET @sql = IF(@col = 0,
    'ALTER TABLE devices ADD COLUMN condition_notes TEXT NULL AFTER warranty_expiry',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- location
SET @col = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND COLUMN_NAME = 'location');
SET @sql = IF(@col = 0,
    'ALTER TABLE devices ADD COLUMN location VARCHAR(100) NULL DEFAULT ''HQ'' AFTER condition_notes',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Foreign key (skip if already exists)
SET @fk = (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND CONSTRAINT_NAME = 'fk_device_catalog');
SET @sql = IF(@fk = 0,
    'ALTER TABLE devices ADD CONSTRAINT fk_device_catalog FOREIGN KEY (catalog_id) REFERENCES asset_catalog(id) ON DELETE SET NULL',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Auto-populate asset_catalog from existing devices (backfill)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT IGNORE INTO asset_catalog (category, brand, model)
SELECT DISTINCT device_type, brand, model
FROM devices
WHERE is_deleted = FALSE;

-- Link existing devices to their catalog entries
UPDATE devices d
JOIN asset_catalog ac ON d.brand = ac.brand AND d.model = ac.model
SET d.catalog_id = ac.id
WHERE d.catalog_id IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. asset_stock_log: immutable audit trail for stock changes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS asset_stock_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    device_id    INT NULL,
    catalog_id   INT NULL,
    action       ENUM('added','assigned','returned','repair_in','repair_out','retired','deleted','status_change') NOT NULL,
    old_status   VARCHAR(50) NULL,
    new_status   VARCHAR(50) NULL,
    performed_by VARCHAR(100) NOT NULL,
    notes        TEXT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asl_device   (device_id),
    INDEX idx_asl_catalog  (catalog_id),
    INDEX idx_asl_action   (action),
    INDEX idx_asl_date     (created_at)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Index for device_type filtering (if not present)
-- ─────────────────────────────────────────────────────────────────────────────
SET @idx = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = 'hrms' AND TABLE_NAME = 'devices' AND INDEX_NAME = 'idx_device_type');
SET @sql = IF(@idx = 0,
    'ALTER TABLE devices ADD INDEX idx_device_type (device_type)',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Audit log
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO audit_logs (user_id, event_type, description)
VALUES (1, 'database_migration', 'Migration 010: Device Inventory & Stock Management — asset_catalog, asset_stock_log, and device purchase metadata added.');
