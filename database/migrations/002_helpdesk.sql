-- =============================================================================
-- Migration 002: Help Desk (Ticket Management) Module
-- Description : Creates helpdesk_tickets and helpdesk_ticket_history tables.
-- Safe        : Uses CREATE TABLE IF NOT EXISTS — idempotent.
-- =============================================================================

USE starterdata;

-- ---------------------------------------------------------------------------
-- Table 1: helpdesk_tickets
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS helpdesk_tickets (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    ticket_ref    VARCHAR(20) UNIQUE NOT NULL,
    title         VARCHAR(255) NOT NULL,
    description   TEXT NOT NULL,
    category      ENUM('it_issue','hr_issue','payroll','leave','others') NOT NULL,
    priority      ENUM('low','medium','high','urgent') NOT NULL DEFAULT 'medium',
    status        ENUM('open','in_progress','resolved','closed') NOT NULL DEFAULT 'open',
    employee_name VARCHAR(100) NOT NULL,
    assigned_to   VARCHAR(100) NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at   TIMESTAMP NULL,
    INDEX idx_hd_emp    (employee_name),
    INDEX idx_hd_status (status),
    INDEX idx_hd_prio   (priority),
    INDEX idx_hd_cat    (category),
    INDEX idx_hd_assign (assigned_to)
);

-- ---------------------------------------------------------------------------
-- Table 2: helpdesk_ticket_history (immutable audit trail)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS helpdesk_ticket_history (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id  INT NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    field      VARCHAR(50) NOT NULL,
    old_value  VARCHAR(255) NULL,
    new_value  VARCHAR(255) NULL,
    note       TEXT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES helpdesk_tickets(id) ON DELETE CASCADE,
    INDEX idx_hdh_ticket (ticket_id)
);

SELECT 'Migration 002 applied successfully.' AS status;
