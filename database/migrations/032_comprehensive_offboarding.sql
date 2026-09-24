-- ============================================================================
-- Migration 032: Comprehensive Corporate Employee Offboarding & System Admin Role
-- ============================================================================

USE hrms;

-- 1. Extend employee table with employment_status and personal contact fields
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'employee' AND COLUMN_NAME = 'employment_status'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE employee ADD COLUMN employment_status ENUM(''ACTIVE'', ''NOTICE_PERIOD'', ''OFFBOARDED'') DEFAULT ''ACTIVE'' AFTER status',
    'SELECT ''Column employment_status already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'employee' AND COLUMN_NAME = 'personal_email'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE employee ADD COLUMN personal_email VARCHAR(150) NULL AFTER email',
    'SELECT ''Column personal_email already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'employee' AND COLUMN_NAME = 'personal_phone'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE employee ADD COLUMN personal_phone VARCHAR(20) NULL AFTER phone',
    'SELECT ''Column personal_phone already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Enhance offboarding_request table
ALTER TABLE offboarding_request MODIFY COLUMN status VARCHAR(50) DEFAULT 'EXIT_REQUESTED';

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'resignation_date'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN resignation_date DATE NULL AFTER employee_name',
    'SELECT ''Column resignation_date already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'proposed_last_working_day'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN proposed_last_working_day DATE NULL AFTER resignation_date',
    'SELECT ''Column proposed_last_working_day already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'personal_email'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN personal_email VARCHAR(150) NULL AFTER proposed_last_working_day',
    'SELECT ''Column personal_email already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'personal_phone'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN personal_phone VARCHAR(20) NULL AFTER personal_email',
    'SELECT ''Column personal_phone already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'department'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN department VARCHAR(100) NULL AFTER personal_phone',
    'SELECT ''Column department already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'designation'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN designation VARCHAR(100) NULL AFTER department',
    'SELECT ''Column designation already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'resignation_doc_path'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN resignation_doc_path VARCHAR(255) NULL AFTER reason_notes',
    'SELECT ''Column resignation_doc_path already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'rejection_reason'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN rejection_reason TEXT NULL AFTER resignation_doc_path',
    'SELECT ''Column rejection_reason already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'manager_id'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN manager_id INT NULL AFTER rejection_reason',
    'SELECT ''Column manager_id already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'manager_name'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN manager_name VARCHAR(100) NULL AFTER manager_id',
    'SELECT ''Column manager_name already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'manager_approved_at'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN manager_approved_at TIMESTAMP NULL AFTER manager_name',
    'SELECT ''Column manager_approved_at already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'it_cleared_by'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN it_cleared_by VARCHAR(100) NULL AFTER manager_approved_at',
    'SELECT ''Column it_cleared_by already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'it_cleared_at'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN it_cleared_at TIMESTAMP NULL AFTER it_cleared_by',
    'SELECT ''Column it_cleared_at already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'hr_cleared_by'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN hr_cleared_by VARCHAR(100) NULL AFTER it_cleared_at',
    'SELECT ''Column hr_cleared_by already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_request' AND COLUMN_NAME = 'hr_cleared_at'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_request ADD COLUMN hr_cleared_at TIMESTAMP NULL AFTER hr_cleared_by',
    'SELECT ''Column hr_cleared_at already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- 3. Create offboarding_consent table
CREATE TABLE IF NOT EXISTS offboarding_consent (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    employee_id INT NOT NULL,
    resignation_confirmed BOOLEAN DEFAULT FALSE,
    last_working_day_confirmed BOOLEAN DEFAULT FALSE,
    asset_return_acknowledged BOOLEAN DEFAULT FALSE,
    confidential_info_acknowledged BOOLEAN DEFAULT FALSE,
    data_handling_acknowledged BOOLEAN DEFAULT FALSE,
    access_termination_acknowledged BOOLEAN DEFAULT FALSE,
    final_clearance_acknowledged BOOLEAN DEFAULT FALSE,
    consent_version VARCHAR(20) DEFAULT 'v1.0',
    status ENUM('EMPLOYEE_CONSENT_PENDING', 'CONSENT_COMPLETED') DEFAULT 'EMPLOYEE_CONSENT_PENDING',
    signature_text VARCHAR(150) NULL,
    ip_address VARCHAR(45) NULL,
    submitted_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE RESTRICT,
    UNIQUE KEY uniq_offb_consent (offboarding_id)
);

-- 4. Create offboarding_knowledge_transfer table
CREATE TABLE IF NOT EXISTS offboarding_knowledge_transfer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    employee_id INT NOT NULL,
    replacement_employee_id INT NULL,
    replacement_employee_name VARCHAR(100) NULL,
    pending_responsibilities TEXT NULL,
    documents_transferred TEXT NULL,
    remarks TEXT NULL,
    status ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED') DEFAULT 'PENDING',
    completed_date DATE NULL,
    updated_by VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE RESTRICT,
    UNIQUE KEY uniq_offb_kt (offboarding_id)
);

-- 5. Create offboarding_it_access table
CREATE TABLE IF NOT EXISTS offboarding_it_access (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    employee_id INT NOT NULL,
    system_name VARCHAR(100) NOT NULL,
    access_status ENUM('ACTIVE', 'SCHEDULED', 'PENDING_REVOCATION', 'REVOKED') DEFAULT 'ACTIVE',
    scheduled_deactivation_date DATE NULL,
    revoked_at TIMESTAMP NULL,
    revoked_by VARCHAR(100) NULL,
    notes TEXT NULL,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE RESTRICT,
    UNIQUE KEY uniq_offb_sys (offboarding_id, system_name)
);

-- 6. Create offboarding_it_actions table (checklist on deactivation)
CREATE TABLE IF NOT EXISTS offboarding_it_actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    corporate_account_disabled BOOLEAN DEFAULT FALSE,
    corporate_email_disabled BOOLEAN DEFAULT FALSE,
    application_access_revoked BOOLEAN DEFAULT FALSE,
    vpn_access_revoked BOOLEAN DEFAULT FALSE,
    github_access_revoked BOOLEAN DEFAULT FALSE,
    groups_removed BOOLEAN DEFAULT FALSE,
    sessions_revoked BOOLEAN DEFAULT FALSE,
    licenses_removed BOOLEAN DEFAULT FALSE,
    deactivated_by VARCHAR(100) NULL,
    deactivated_at TIMESTAMP NULL,
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE CASCADE,
    UNIQUE KEY uniq_offb_it_actions (offboarding_id)
);

-- 7. Create exit_portal_otp table
CREATE TABLE IF NOT EXISTS exit_portal_otp (
    id INT AUTO_INCREMENT PRIMARY KEY,
    personal_email VARCHAR(150) NOT NULL,
    employee_id INT NOT NULL,
    otp_code VARCHAR(10) NOT NULL,
    expires_at DATETIME NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_exit_email (personal_email),
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE CASCADE
);

-- 8. Enhance offboarding_audit_log table
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_audit_log' AND COLUMN_NAME = 'role'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_audit_log ADD COLUMN role VARCHAR(50) NULL AFTER performed_by_name',
    'SELECT ''Column role already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'offboarding_audit_log' AND COLUMN_NAME = 'previous_status'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE offboarding_audit_log ADD COLUMN previous_status VARCHAR(50) NULL AFTER action',
    'SELECT ''Column previous_status already exists'' AS status'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 9. Add SYSTEM_ADMIN to users.role ENUM and configure permissions
ALTER TABLE users MODIFY COLUMN role
ENUM('admin','hr','manager','employee','team_member','onboarding_candidate','superadmin','accounts','system_admin')
NOT NULL DEFAULT 'employee';

-- Insert SYSTEM_ADMIN permissions
INSERT IGNORE INTO permissions (module, permission_key, label, description, route_reference) VALUES
('offboarding', 'offboarding.view', 'View Offboarding', 'View offboarding cases and tasks', '/offboarding'),
('offboarding', 'offboarding.it_tasks', 'Manage IT Offboarding', 'Manage IT access and account deactivations', '/offboarding/it'),
('system_access', 'system_access.view', 'View System Access', 'View employee system access statuses', '/system-admin/system-access'),
('system_access', 'system_access.manage', 'Manage System Access', 'Revoke and manage system access', '/system-admin/system-access'),
('user_accounts', 'user_accounts.view', 'View User Accounts', 'View corporate user accounts', '/system-admin/user-accounts'),
('user_accounts', 'user_accounts.manage', 'Manage User Accounts', 'Enable or disable user accounts', '/system-admin/user-accounts'),
('audit_logs', 'audit_logs.view', 'View Audit Logs', 'View security and system audit logs', '/system-admin/audit-logs');

-- Grant offboarding & system administration permissions to system_admin role
INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'system_admin', id FROM permissions WHERE permission_key IN (
    'offboarding.view', 'offboarding.it_tasks', 'system_access.view', 'system_access.manage',
    'user_accounts.view', 'user_accounts.manage', 'audit_logs.view'
);

-- Grant all standard team member permissions to system_admin
INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'system_admin', permission_id 
FROM role_permissions 
WHERE role IN ('employee', 'team_member');

-- Grant software & device asset management permissions to system_admin
INSERT INTO role_permissions (role, permission_id, is_granted)
SELECT 'system_admin', id, 1 
FROM permissions 
WHERE module IN ('devices', 'software')
ON DUPLICATE KEY UPDATE is_granted = 1;

-- Grant offboarding.view to employee, manager, hr, admin, superadmin
INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'employee', id FROM permissions WHERE permission_key = 'offboarding.view';

INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'team_member', id FROM permissions WHERE permission_key = 'offboarding.view';

INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'manager', id FROM permissions WHERE permission_key = 'offboarding.view';

INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'hr', id FROM permissions WHERE permission_key IN ('offboarding.view');

INSERT IGNORE INTO role_permissions (role, permission_id)
SELECT 'admin', id FROM permissions WHERE permission_key IN ('offboarding.view', 'offboarding.it_tasks', 'system_access.view', 'user_accounts.view', 'audit_logs.view');

SELECT 'Migration 032 executed successfully' AS result;
