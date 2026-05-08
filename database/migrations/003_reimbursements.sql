-- =============================================================================
-- Migration 003: Reimbursement (Expense Management) Module
-- Description : Creates reimbursements and reimbursement_history tables.
-- Safe        : Uses CREATE TABLE IF NOT EXISTS — idempotent.
-- =============================================================================

USE starterdata;

-- ---------------------------------------------------------------------------
-- Table 1: reimbursements
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reimbursements (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    ref              VARCHAR(20) UNIQUE NOT NULL,
    employee_name    VARCHAR(100) NOT NULL,
    title            VARCHAR(255) NOT NULL,
    description      TEXT NULL,
    amount           DECIMAL(10,2) NOT NULL,
    currency         VARCHAR(10) NOT NULL DEFAULT 'INR',
    expense_date     DATE NOT NULL,
    category         ENUM('travel','food','accommodation','office_supplies','others') NOT NULL,
    receipt_file     VARCHAR(500) NULL,
    status           ENUM('pending','approved','rejected','paid') NOT NULL DEFAULT 'pending',
    approved_by      VARCHAR(100) NULL,
    approved_at      TIMESTAMP NULL,
    rejection_reason TEXT NULL,
    payment_status   ENUM('pending','processed') NOT NULL DEFAULT 'pending',
    payment_date     DATE NULL,
    project_id       INT NULL,
    billable         TINYINT(1) NOT NULL DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_reimb_emp    (employee_name),
    INDEX idx_reimb_status (status),
    INDEX idx_reimb_cat    (category),
    INDEX idx_reimb_proj   (project_id)
);

-- ---------------------------------------------------------------------------
-- Table 2: reimbursement_history (immutable audit trail)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reimbursement_history (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    reimbursement_id  INT NOT NULL,
    changed_by        VARCHAR(100) NOT NULL,
    field             VARCHAR(50) NOT NULL,
    old_value         VARCHAR(255) NULL,
    new_value         VARCHAR(255) NULL,
    note              TEXT NULL,
    changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE CASCADE,
    INDEX idx_rh_reimb (reimbursement_id)
);

SELECT 'Migration 003 applied successfully.' AS status;
