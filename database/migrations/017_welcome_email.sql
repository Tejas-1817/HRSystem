-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 017: Welcome Email Feature Table & Seeding
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pending_welcome_emails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE CASCADE,
    UNIQUE KEY unique_employee_pending (employee_id)
);

-- Seed pending_welcome_emails with current employees except those whose 
-- joining date is before April 30th, 2026.
INSERT IGNORE INTO pending_welcome_emails (employee_id)
SELECT id FROM employee
WHERE date_of_joining >= '2026-04-30' OR date_of_joining IS NULL;
