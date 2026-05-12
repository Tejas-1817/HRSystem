-- Create DB
USE hrms;

-- -- 🔥 Remove all old users (important)
-- DROP USER IF EXISTS 'tejas'@'%';
-- DROP USER IF EXISTS 'tejas'@'localhost';

-- -- 🔥 Create user for all devices
-- CREATE USER 'tejas'@'%' IDENTIFIED BY 'password';

-- -- Give full access
-- -- ALTER user 'tejas'@'%' IDENTIFIED by 'password123';
-- GRANT ALL PRIVILEGES ON hrms.* TO 'tejas'@'%';
-- FLUSH PRIVILEGES;



-- 🔥 Create employee table safely (with date_of_birth & date_of_joining)
CREATE TABLE IF NOT EXISTS employee (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    original_name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    salary DECIMAL(10,2),
    date_of_birth DATE,
    date_of_joining DATE,
    photo VARCHAR(255),
    pdf_file VARCHAR(255),
    docx_file VARCHAR(255),
    status ENUM('working', 'bench', 'over_allocated') DEFAULT 'bench',
    allow_over_allocation BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_doj (date_of_joining),
    INDEX idx_emp_status (status)
);

-- 🔥 Clean up old timesheet table if it exists
DROP TABLE IF EXISTS timesheet;

-- 🔥 Create timesheets table matching your new Office.py API
CREATE TABLE IF NOT EXISTS timesheets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100),
    project VARCHAR(100),
    task VARCHAR(100),
    description TEXT,
    hours INT,
    start_date DATE,
    status ENUM('draft', 'submitted', 'approved', 'rejected') DEFAULT 'draft',
    manager_comments TEXT,
    manager_name VARCHAR(100),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP NULL,
    INDEX idx_ts_status (status),
    INDEX idx_ts_employee (employee_name)
);

-- 🔥 Create projects table (enhanced with manager, customer info & dates)
CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) UNIQUE NOT NULL,
    project_type ENUM('fixed', 'tm') DEFAULT 'fixed',
    status VARCHAR(50) DEFAULT 'ongoing',
    manager_name VARCHAR(100),
    customer_name VARCHAR(100),
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_proj_id (project_id)
);

-- 🔥 Create project_assignments table to track team members
CREATE TABLE IF NOT EXISTS project_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    employee_name VARCHAR(100) NOT NULL,
    is_billable BOOLEAN DEFAULT TRUE,
    billable_percentage INT DEFAULT 100,
    assigned_by VARCHAR(100),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE KEY unique_assignment (project_id, employee_name),
    INDEX idx_pa_billable (is_billable)
);

-- 🔥 Create notifications table for system alerts
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) DEFAULT 'general',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notif_user (employee_name)
);

-- 🔥 Create leaves table for employee leave applications (supports full-day & half-day)
CREATE TABLE IF NOT EXISTS leaves (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    leave_type VARCHAR(50) NOT NULL,
    leave_type_category ENUM('full_day', 'half_day') NOT NULL DEFAULT 'full_day',
    half_day_period ENUM('first_half', 'second_half') NULL,
    leave_duration DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_leave_emp_date (employee_name, start_date),
    INDEX idx_leave_status (status)
);

-- 🔥 Create leave_balance table to track per-employee leave balances
-- total_leaves and used_leaves are DECIMAL to support half-day (0.5) deductions
CREATE TABLE IF NOT EXISTS leave_balance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    leave_type VARCHAR(50) NOT NULL,
    total_leaves DECIMAL(6,2) NOT NULL DEFAULT 0.00,
    used_leaves DECIMAL(6,2) NOT NULL DEFAULT 0.00,
    UNIQUE KEY unique_emp_leave (employee_name, leave_type)
);

-- 🔥 Create users table for authentication & RBAC
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    original_name VARCHAR(100),
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'employee',
    employee_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    password_change_required BOOLEAN DEFAULT TRUE,
    reset_token VARCHAR(255) DEFAULT NULL,
    reset_token_expiry DATETIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- 🔥 Attendance table (legacy/deprecated): kept for backward compatibility.
-- Attendance is now derived from timesheet aggregates in GET /attendance.
CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'present',
    clock_in TIME,
    clock_out TIME,
    break_minutes INT DEFAULT 0,
    total_worked_hours DECIMAL(5,2) DEFAULT 0.00,
    overtime_hours DECIMAL(5,2) DEFAULT 0.00,
    underwork_hours DECIMAL(5,2) DEFAULT 0.00,
    work_status VARCHAR(20) DEFAULT 'incomplete',
    remarks TEXT,
    UNIQUE KEY unique_daily_attendance (employee_name, date)
);

-- 🔥 Daily work config table (legacy/deprecated with clock-in/out flow)
-- Kept for soft migration compatibility. Not used in timesheet-derived attendance.
CREATE TABLE IF NOT EXISTS daily_work_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    standard_hours DECIMAL(5,2) DEFAULT 8.00,
    half_day_threshold DECIMAL(5,2) DEFAULT 4.00,
    default_break_minutes INT DEFAULT 60,
    late_login_threshold TIME DEFAULT '09:30:00',
    early_logout_threshold TIME DEFAULT '17:30:00',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 🔥 Create payslips table
CREATE TABLE IF NOT EXISTS payslips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    month VARCHAR(20) NOT NULL,
    year INT NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 🔥 Create employee_documents table (enhanced with status tracking, verification & access control)
CREATE TABLE IF NOT EXISTS employee_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    is_confidential BOOLEAN DEFAULT TRUE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP NULL,
    rejection_reason TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_emp_doc (employee_name, doc_type),
    INDEX idx_doc_status (status)
);

-- 🔥 Create holidays table for organization-wide holiday list
CREATE TABLE IF NOT EXISTS holidays (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    date DATE NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'public',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_holiday_date (date)
);

-- 🔥 Create policies table for Company Policy Management
CREATE TABLE IF NOT EXISTS policies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(100) NOT NULL, -- Core HR, Legal/Compliance, etc.
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    INDEX idx_policy_category (category)
);

-- 🔥 Create audit_logs table for tracking security-sensitive events
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_user (user_id)
);

-- 🔥 Create bank_details table (HR-restricted, employee-owned)
CREATE TABLE IF NOT EXISTS bank_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL UNIQUE,
    account_holder_name VARCHAR(150) NOT NULL,
    bank_name VARCHAR(150) NOT NULL,
    account_number VARCHAR(30) NOT NULL,
    ifsc_code VARCHAR(20) NOT NULL,
    branch_name VARCHAR(150) NOT NULL,
    status ENUM('pending', 'completed', 'verified') NOT NULL DEFAULT 'completed',
    verified_by VARCHAR(100) DEFAULT NULL,
    verified_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_bank_emp (employee_name),
    INDEX idx_bank_status (status)
);

-- 🔥 Create leave_config table for configurable default leave quotas
CREATE TABLE IF NOT EXISTS leave_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    leave_type VARCHAR(50) NOT NULL UNIQUE,
    default_total INT NOT NULL DEFAULT 0,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 🔥 Create helpdesk_tickets table for the Help Desk / Ticket Management module
CREATE TABLE IF NOT EXISTS helpdesk_tickets (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    ticket_ref    VARCHAR(20) UNIQUE NOT NULL,          -- Human-readable HD-0001
    title         VARCHAR(255) NOT NULL,
    description   TEXT NOT NULL,
    category      ENUM('it_issue','hr_issue','payroll','leave','others') NOT NULL,
    priority      ENUM('low','medium','high','urgent') NOT NULL DEFAULT 'medium',
    status        ENUM('open','in_progress','resolved','closed') NOT NULL DEFAULT 'open',
    employee_name VARCHAR(100) NOT NULL,                -- Who raised the ticket
    assigned_to   VARCHAR(100) NULL,                   -- Resolver employee_name
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at   TIMESTAMP NULL,
    INDEX idx_hd_emp    (employee_name),
    INDEX idx_hd_status (status),
    INDEX idx_hd_prio   (priority),
    INDEX idx_hd_cat    (category),
    INDEX idx_hd_assign (assigned_to)
);

-- 🔥 Create helpdesk_ticket_history table — immutable audit trail for ticket changes
CREATE TABLE IF NOT EXISTS helpdesk_ticket_history (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id  INT NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    field      VARCHAR(50) NOT NULL,                   -- 'status' | 'assigned_to' | 'priority'
    old_value  VARCHAR(255) NULL,
    new_value  VARCHAR(255) NULL,
    note       TEXT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES helpdesk_tickets(id) ON DELETE CASCADE,
    INDEX idx_hdh_ticket (ticket_id)
);

-- 🔥 Create reimbursements table for Expense / Reimbursement Management module
CREATE TABLE IF NOT EXISTS reimbursements (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    ref              VARCHAR(20) UNIQUE NOT NULL,           -- Human-readable: EXP-0001
    employee_name    VARCHAR(100) NOT NULL,
    title            VARCHAR(255) NOT NULL,
    description      TEXT NULL,
    amount           DECIMAL(10,2) NOT NULL,
    currency         VARCHAR(10) NOT NULL DEFAULT 'INR',
    expense_date     DATE NOT NULL,
    category         ENUM('travel','food','accommodation','office_supplies','others') NOT NULL,
    receipt_file     VARCHAR(500) NULL,                     -- Path to uploaded receipt
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

-- 🔥 Create reimbursement_history table — immutable audit trail for expense changes
CREATE TABLE IF NOT EXISTS reimbursement_history (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    reimbursement_id  INT NOT NULL,
    changed_by        VARCHAR(100) NOT NULL,
    field             VARCHAR(50) NOT NULL,       -- 'status' | 'approved_by' | 'payment_status'
    old_value         VARCHAR(255) NULL,
    new_value         VARCHAR(255) NULL,
    note              TEXT NULL,
    changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE CASCADE,
    INDEX idx_rh_reimb (reimbursement_id)
);
