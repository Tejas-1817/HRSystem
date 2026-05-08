-- Migration 004: Secure Role Management
-- Adds role column to employee and creates role history table

USE starterdata;

-- 1. Add role column to employee table
ALTER TABLE employee 
ADD COLUMN role ENUM('admin', 'hr', 'manager', 'employee') DEFAULT 'employee' AFTER phone;

-- 2. Sync roles from users table to employee table
UPDATE employee e
JOIN users u ON e.name = u.employee_name
SET e.role = u.role;

-- 3. Create role_history table for immutable audit trail
CREATE TABLE IF NOT EXISTS role_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    old_role VARCHAR(50),
    new_role VARCHAR(50),
    changed_by_user_id INT,
    notes TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_rh_employee (employee_name),
    INDEX idx_rh_date (changed_at)
);

-- 4. Log initial migration as a security event
INSERT INTO audit_logs (user_id, event_type, description)
VALUES (1, 'database_migration', 'Migration 004: Role management and history tracking enabled.');
