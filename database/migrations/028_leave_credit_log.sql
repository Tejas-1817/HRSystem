-- Migration 028: Automatic Leave Credit System schema
CREATE TABLE IF NOT EXISTS employee_leave_credit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    quarter_number INT NOT NULL,
    quarter_start DATE NOT NULL,
    quarter_end DATE NOT NULL,
    planned_leaves_credited DECIMAL(4,2) NOT NULL DEFAULT 3.00,
    unplanned_leaves_credited DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    optional_leaves_credited DECIMAL(4,2) NOT NULL DEFAULT 0.00,
    credited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    credited_by VARCHAR(50) DEFAULT 'system',
    status ENUM('SUCCESS','FAILED') NOT NULL DEFAULT 'SUCCESS',
    error_message TEXT NULL,
    UNIQUE KEY uniq_emp_quarter (employee_name, quarter_number),
    INDEX idx_elc_employee (employee_name)
);
