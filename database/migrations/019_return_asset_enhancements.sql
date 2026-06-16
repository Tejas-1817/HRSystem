-- ============================================================================
-- Migration 019: Return Asset Workflow Enhancements
-- ============================================================================
-- Extends device_assignments with return tracking columns and audit_logs
-- with request metadata for enterprise-grade compliance.
-- Safe: Uses IF NOT EXISTS / column-existence checks — idempotent.
-- ============================================================================

USE hrms;

-- ---------------------------------------------------------------------------
-- 1. Extend device_assignments with return tracking
-- ---------------------------------------------------------------------------

-- Who processed the return (HR/Admin employee_name)
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'device_assignments'
      AND COLUMN_NAME = 'returned_by'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE device_assignments ADD COLUMN returned_by VARCHAR(100) NULL AFTER returned_date',
    'SELECT ''Column returned_by already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Reason for return (e.g. "End of employment", "Device upgrade")
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'device_assignments'
      AND COLUMN_NAME = 'return_reason'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE device_assignments ADD COLUMN return_reason TEXT NULL AFTER returned_by',
    'SELECT ''Column return_reason already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- 2. Extend audit_logs with request metadata
-- ---------------------------------------------------------------------------

-- IP address of the requester
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'audit_logs'
      AND COLUMN_NAME = 'ip_address'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE audit_logs ADD COLUMN ip_address VARCHAR(45) NULL AFTER description',
    'SELECT ''Column ip_address already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- User agent string
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'audit_logs'
      AND COLUMN_NAME = 'user_agent'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE audit_logs ADD COLUMN user_agent TEXT NULL AFTER ip_address',
    'SELECT ''Column user_agent already exists'' AS status'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Migration 019 applied successfully.' AS status;
