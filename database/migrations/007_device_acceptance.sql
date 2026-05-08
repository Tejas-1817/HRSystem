-- ============================================================================
-- Migration 007: Device Assignment Acceptance Workflow
-- ============================================================================
-- Adds acceptance tracking to device_assignments and creates an immutable
-- device_agreements table for compliance/audit records.
-- ============================================================================

-- 1. Extend device_assignments with acceptance tracking columns
ALTER TABLE device_assignments
    ADD COLUMN acceptance_status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',
    ADD COLUMN accepted_at       TIMESTAMP NULL,
    ADD COLUMN signature_url     VARCHAR(500) NULL,
    ADD COLUMN rejection_reason  TEXT NULL;

-- 2. Create device_agreements table — immutable signed agreement records
CREATE TABLE IF NOT EXISTS device_agreements (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id       INT NOT NULL,
    employee_name       VARCHAR(100) NOT NULL,
    device_id           INT NOT NULL,
    agreement_text      TEXT NOT NULL,
    agreement_version   VARCHAR(20) NOT NULL DEFAULT '1.0',
    signature_url       VARCHAR(500) NOT NULL,
    accepted_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address          VARCHAR(45) NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES device_assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    INDEX idx_dagr_emp      (employee_name),
    INDEX idx_dagr_assign   (assignment_id),
    INDEX idx_dagr_device   (device_id)
);

-- 3. Add index on acceptance_status for filtering queries
ALTER TABLE device_assignments ADD INDEX idx_da_acceptance (acceptance_status);
