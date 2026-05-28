-- ═══════════════════════════════════════════════════════════════════════
-- Migration 016: Team Member Professional Information Fields
-- ═══════════════════════════════════════════════════════════════════════
-- Adds enterprise-grade HR fields to the employee table:
--   - designation, department, gender, address, employment_type
--   - Auto-generated team_member_code (TM-YYYY-NNNN)
--   - Audit tracking: created_by, updated_by, updated_at
--
-- Also creates dynamic management tables:
--   - departments (HR/Admin managed)
--   - designations (HR/Admin managed)
--
-- Safe to run multiple times (uses IF NOT EXISTS / IF EXISTS guards).
-- ═══════════════════════════════════════════════════════════════════════

USE hrms;

-- ─── 1. Add new columns to employee table ────────────────────────────

-- Designation (e.g., Software Engineer, HR Executive)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS designation VARCHAR(100) NULL;

-- Department (e.g., Engineering, HR, Finance)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS department VARCHAR(100) NULL;

-- Gender (Male, Female, Other, Prefer Not to Say)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS gender VARCHAR(30) NULL;

-- Address (Full postal address)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS address TEXT NULL;

-- Employment Type (Full Time, Intern, Contract Based, Part Time, Freelancer, Temporary)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS employment_type VARCHAR(50) NULL;

-- Auto-generated unique Team Member Code (TM-2026-0001)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS team_member_code VARCHAR(20) NULL;

-- Audit: who created this team member
ALTER TABLE employee ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) NULL;

-- Audit: who last updated this team member
ALTER TABLE employee ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100) NULL;

-- Audit: last update timestamp (if not already present)
ALTER TABLE employee ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;


-- ─── 2. Add indexes for frequently queried new fields ────────────────

-- Index on department for filtering/grouping queries
CREATE INDEX IF NOT EXISTS idx_emp_department ON employee(department);

-- Index on employment_type for filtering queries
CREATE INDEX IF NOT EXISTS idx_emp_employment_type ON employee(employment_type);

-- Unique index on team_member_code for lookup
CREATE UNIQUE INDEX IF NOT EXISTS idx_emp_team_member_code ON employee(team_member_code);

-- Index on gender for analytics queries
CREATE INDEX IF NOT EXISTS idx_emp_gender ON employee(gender);


-- ─── 3. Create departments management table ──────────────────────────

CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_dept_active (is_active)
);


-- ─── 4. Create designations management table ─────────────────────────

CREATE TABLE IF NOT EXISTS designations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    department_id INT NULL,
    description VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
    INDEX idx_desig_active (is_active),
    INDEX idx_desig_dept (department_id)
);


-- ─── 5. Seed default departments ─────────────────────────────────────

INSERT IGNORE INTO departments (name, description, created_by) VALUES
('Engineering',          'Software development and technical operations',  'system'),
('HR',                   'Human Resources and people management',          'system'),
('Finance',              'Financial operations and accounting',            'system'),
('Recruitment',          'Talent acquisition and hiring',                  'system'),
('Operations',           'Business operations and logistics',              'system'),
('Marketing',            'Marketing and brand management',                 'system'),
('Sales',                'Sales and business development',                 'system'),
('Legal',                'Legal and compliance',                           'system'),
('IT',                   'IT infrastructure and support',                  'system'),
('Administration',       'General administration and office management',   'system'),
('Product',              'Product management and strategy',                'system'),
('Design',               'UI/UX and graphic design',                       'system'),
('Quality Assurance',    'Testing and quality control',                    'system'),
('Customer Support',     'Customer service and support',                   'system'),
('Research & Development', 'R&D and innovation',                           'system');


-- ─── 6. Seed default designations ────────────────────────────────────

INSERT IGNORE INTO designations (name, description, created_by) VALUES
('Software Engineer',        'Develops and maintains software applications',         'system'),
('Senior Software Engineer', 'Senior-level software development role',               'system'),
('HR Executive',             'Handles human resource operations',                    'system'),
('HR Manager',               'Manages the HR department and policies',               'system'),
('Project Manager',          'Oversees project planning and delivery',               'system'),
('Recruiter',                'Handles talent acquisition and hiring',                'system'),
('Senior Developer',         'Senior software development role',                     'system'),
('Team Lead',                'Leads a team of developers or specialists',            'system'),
('QA Engineer',              'Quality assurance and testing',                        'system'),
('DevOps Engineer',          'Infrastructure and deployment automation',             'system'),
('Business Analyst',         'Analyzes business processes and requirements',         'system'),
('Product Manager',          'Manages product strategy and roadmap',                 'system'),
('Technical Lead',           'Technical leadership and architecture',                'system'),
('Data Analyst',             'Data analysis and insights',                           'system'),
('UI/UX Designer',           'User interface and experience design',                 'system'),
('System Administrator',     'System and infrastructure management',                 'system'),
('Intern',                   'Internship/training position',                         'system'),
('Trainee',                  'Entry-level training position',                        'system');
