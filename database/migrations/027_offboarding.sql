CREATE TABLE IF NOT EXISTS offboarding_request (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    employee_name VARCHAR(100) NOT NULL,
    initiated_by INT NOT NULL,
    initiated_by_name VARCHAR(100) NOT NULL,
    reason VARCHAR(100) NOT NULL,
    reason_notes TEXT NULL,
    last_working_day DATE NOT NULL,
    status ENUM('INITIATED','IN_PROGRESS','COMPLETED','CANCELLED') DEFAULT 'INITIATED',
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE RESTRICT,
    FOREIGN KEY (initiated_by) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_offb_employee (employee_id),
    INDEX idx_offb_status (status)
);

CREATE TABLE IF NOT EXISTS offboarding_checklist_item (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    item_type ENUM('ASSETS_RETURNED','EMAIL_ACCESS_REMOVED','SYSTEM_ACCESS_REMOVED','MS_TEAMS_ACCESS_REMOVED') NOT NULL,
    is_auto_tracked BOOLEAN DEFAULT FALSE,
    status ENUM('PENDING','DONE','NOT_APPLICABLE') DEFAULT 'PENDING',
    notes TEXT NULL,
    marked_by INT NULL,
    marked_by_name VARCHAR(100) NULL,
    marked_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE RESTRICT,
    FOREIGN KEY (marked_by) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE KEY uniq_offb_item (offboarding_id, item_type),
    INDEX idx_oci_offboarding (offboarding_id)
);

CREATE TABLE IF NOT EXISTS offboarding_approval (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    approver_role ENUM('hr','manager','accounts') NOT NULL,
    approver_id INT NULL,
    approver_name VARCHAR(100) NULL,
    status ENUM('PENDING','APPROVED','REJECTED') DEFAULT 'PENDING',
    comments TEXT NULL,
    acted_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE RESTRICT,
    FOREIGN KEY (approver_id) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE KEY uniq_offb_approval (offboarding_id, approver_role),
    INDEX idx_oa_offboarding (offboarding_id)
);

CREATE TABLE IF NOT EXISTS offboarding_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offboarding_id INT NOT NULL,
    action VARCHAR(100) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    performed_by INT NULL,
    performed_by_name VARCHAR(100) NULL,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT NULL,
    FOREIGN KEY (offboarding_id) REFERENCES offboarding_request(id) ON DELETE RESTRICT,
    FOREIGN KEY (performed_by) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_oal_offboarding (offboarding_id)
);
