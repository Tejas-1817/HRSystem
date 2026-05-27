-- 014_timesheet_edit_history.sql
-- Create timesheet edit history table to track modifications made by Team Members

USE hrms;

CREATE TABLE IF NOT EXISTS timesheet_edit_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timesheet_id INT NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    old_project VARCHAR(100),
    new_project VARCHAR(100),
    old_task VARCHAR(100),
    new_task VARCHAR(100),
    old_hours DECIMAL(5,2),
    new_hours DECIMAL(5,2),
    old_description TEXT,
    new_description TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (timesheet_id) REFERENCES timesheets(id) ON DELETE CASCADE,
    INDEX idx_teh_timesheet (timesheet_id)
);
