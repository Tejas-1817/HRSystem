-- ============================================================================
-- Migration 033: Corporate Resignation Form Enhancements
-- ============================================================================

USE hrms;

-- 1. Add exit_type and other_exit_type to offboarding_request
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'exit_type'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN exit_type VARCHAR(50) DEFAULT ''Voluntary Resignation'' AFTER proposed_last_working_day',
    'SELECT ''Column exit_type already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'other_exit_type'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN other_exit_type VARCHAR(255) NULL AFTER exit_type',
    'SELECT ''Column other_exit_type already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Add other_reason to offboarding_request
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'other_reason'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN other_reason VARCHAR(255) NULL AFTER reason',
    'SELECT ''Column other_reason already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Add handover fields to offboarding_request
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'handover_required'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN handover_required VARCHAR(10) DEFAULT ''Yes'' AFTER reason_notes',
    'SELECT ''Column handover_required already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'handover_to'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN handover_to VARCHAR(100) NULL AFTER handover_required',
    'SELECT ''Column handover_to already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'handover_projects'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN handover_projects TEXT NULL AFTER handover_to',
    'SELECT ''Column handover_projects already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'handover_notes'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN handover_notes TEXT NULL AFTER handover_projects',
    'SELECT ''Column handover_notes already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. Add personal contact enhancements to offboarding_request
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'alternate_phone'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN alternate_phone VARCHAR(30) NULL AFTER personal_phone',
    'SELECT ''Column alternate_phone already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'preferred_communication'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN preferred_communication VARCHAR(30) DEFAULT ''Personal Email'' AFTER alternate_phone',
    'SELECT ''Column preferred_communication already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'post_employment_contact_consent'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN post_employment_contact_consent VARCHAR(10) DEFAULT ''Yes'' AFTER preferred_communication',
    'SELECT ''Column post_employment_contact_consent already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5. Add supporting document and declaration confirmation to offboarding_request
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'supporting_doc_path'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN supporting_doc_path VARCHAR(255) NULL AFTER resignation_doc_path',
    'SELECT ''Column supporting_doc_path already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'declarations_confirmed'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN declarations_confirmed BOOLEAN DEFAULT TRUE AFTER supporting_doc_path',
    'SELECT ''Column declarations_confirmed already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'Migration 033 executed successfully' AS result;
