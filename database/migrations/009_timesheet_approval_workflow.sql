-- Migration 009: Role-Based Timesheet Approval Workflow
-- Adds approval audit columns to timesheets and creates timesheet_approval_history table.
-- Safe to re-run: all statements are idempotent (IF NOT EXISTS / IGNORE).

USE starterdata;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Extend timesheets ENUM to include 'pending' (some seed rows already use it)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE timesheets
  MODIFY COLUMN status ENUM('draft','submitted','pending','approved','rejected') DEFAULT 'draft';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Add approval-audit columns to timesheets (idempotent via IGNORE)
-- ─────────────────────────────────────────────────────────────────────────────

-- owner_role: cached role of the timesheet submitter at time of creation
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = 'starterdata' AND TABLE_NAME = 'timesheets' AND COLUMN_NAME = 'owner_role');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE timesheets ADD COLUMN owner_role VARCHAR(50) NULL AFTER employee_name',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- approved_by: employee_name of the person who approved/rejected
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = 'starterdata' AND TABLE_NAME = 'timesheets' AND COLUMN_NAME = 'approved_by');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE timesheets ADD COLUMN approved_by VARCHAR(100) NULL AFTER manager_name',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- approver_role: role of the approver at time of action
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = 'starterdata' AND TABLE_NAME = 'timesheets' AND COLUMN_NAME = 'approver_role');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE timesheets ADD COLUMN approver_role VARCHAR(50) NULL AFTER approved_by',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- approved_at: timestamp of approval/rejection action
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = 'starterdata' AND TABLE_NAME = 'timesheets' AND COLUMN_NAME = 'approved_at');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE timesheets ADD COLUMN approved_at TIMESTAMP NULL AFTER approver_role',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- rejection_reason: detailed reason when rejected
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = 'starterdata' AND TABLE_NAME = 'timesheets' AND COLUMN_NAME = 'rejection_reason');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE timesheets ADD COLUMN rejection_reason TEXT NULL AFTER approved_at',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Backfill owner_role from users table for existing rows
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE timesheets t
JOIN users u ON t.employee_name = u.employee_name
SET t.owner_role = u.role
WHERE t.owner_role IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Backfill approved_by / approved_at for already-approved entries
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE timesheets
SET approved_by   = manager_name,
    approved_at   = reviewed_at
WHERE status = 'approved'
  AND manager_name IS NOT NULL
  AND approved_by IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Create timesheet_approval_history — immutable audit trail
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS timesheet_approval_history (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    timesheet_id   INT NOT NULL,
    action         ENUM('approved','rejected','submitted','resubmitted') NOT NULL,
    performed_by   VARCHAR(100) NOT NULL,
    performer_role VARCHAR(50)  NOT NULL,
    comments       TEXT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (timesheet_id) REFERENCES timesheets(id) ON DELETE CASCADE,
    INDEX idx_tah_ts        (timesheet_id),
    INDEX idx_tah_performer (performed_by)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Add index for owner_role queries (if not already present)
-- ─────────────────────────────────────────────────────────────────────────────
SET @idx_exists = (SELECT COUNT(*) FROM information_schema.STATISTICS
                   WHERE TABLE_SCHEMA = 'starterdata' AND TABLE_NAME = 'timesheets' AND INDEX_NAME = 'idx_ts_owner_role');
SET @sql = IF(@idx_exists = 0,
    'ALTER TABLE timesheets ADD INDEX idx_ts_owner_role (owner_role)',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Audit log
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO audit_logs (user_id, event_type, description)
VALUES (1, 'database_migration', 'Migration 009: Role-based timesheet approval workflow — approval audit columns and history table created.');
