-- Migration 030: Multi-Approver Leave Signoff Workflow (HR + All Assigned Project Managers)

USE hrms;

CREATE TABLE IF NOT EXISTS leave_signoffs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    leave_id INT NOT NULL,
    approver_role VARCHAR(50) NOT NULL,
    approver_name VARCHAR(100) NULL,
    project_name VARCHAR(100) NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    action_by VARCHAR(100) NULL,
    action_at TIMESTAMP NULL,
    comments TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (leave_id) REFERENCES leaves(id) ON DELETE CASCADE,
    INDEX idx_ls_leave (leave_id),
    INDEX idx_ls_approver (approver_name, approver_role),
    INDEX idx_ls_status (status)
);
