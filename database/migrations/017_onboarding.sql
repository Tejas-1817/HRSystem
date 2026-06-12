-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 017: Onboarding Module + Users Table Additive Columns
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Phase 1 — Users Table Additive Changes (data migration in run_017.py):
--   - Add email (VARCHAR 255 UNIQUE), migrate from username
--   - Add password_hash (VARCHAR 255), migrate from password
--   - Add employee_id (FK to employee.id), migrate from employee_name
--   - Convert role VARCHAR(50) → ENUM with 'onboarding_candidate'
--   - Legacy columns (username, password, employee_name,
--     password_change_required, reset_token, reset_token_expiry)
--     are PRESERVED for auth system backward compatibility.
--
-- Phase 2 — Onboarding Module (5 new tables):
--   - onboarding_joinee       — Core joinee record, UUID-based, status workflow
--   - onboarding_declaration  — Full background info (personal, address,
--                               ID proof, 3 education, 6 employment, declaration)
--   - onboarding_references   — Professional references (min 3, up to 6)
--   - onboarding_documents    — Document upload with verification workflow
--   - onboarding_audit_log    — Immutable audit trail
--
-- Safety: All CREATE TABLEs use IF NOT EXISTS.
--         All foreign keys use ON DELETE RESTRICT (never CASCADE for audit safety).
-- ═══════════════════════════════════════════════════════════════════════════

USE hrms;

-- ═══════════════════════════════════════════════════════════════════════════
-- PHASE 1: USERS TABLE — ADDITIVE CHANGES ONLY
-- Note: Data migration (UPDATE) between ADD COLUMN and MODIFY is
-- handled by run_017.py. The ALTER statements below are idempotent with
-- IF [NOT] EXISTS guards.
--
-- IMPORTANT: Legacy columns (username, password, employee_name,
-- password_change_required, reset_token, reset_token_expiry) are
-- PRESERVED — the auth system still reads from them. A future migration
-- can drop them once all code references are migrated to the new columns.
-- ═══════════════════════════════════════════════════════════════════════════

-- 1a. Add email column (nullable first; data copied + NOT NULL set in Python)
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255) NULL;

-- 1b. Add password_hash column (nullable first)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) NULL;

-- 1c. Add employee_id FK column
ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id INT NULL;

-- 1d. Convert role VARCHAR(50) → ENUM (data sanitized in Python first)
-- ALTER TABLE users MODIFY COLUMN role
--     ENUM('admin','hr','manager','employee','team_member','onboarding_candidate')
--     NOT NULL DEFAULT 'employee';

-- 1e. Add FK to employee (handled in Python after data migration)


-- ═══════════════════════════════════════════════════════════════════════════
-- PHASE 2: ONBOARDING MODULE TABLES
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────
-- 2a. onboarding_joinee — Core joinee record
-- ─────────────────────────────────────────────────────────────────────────
-- person_id: Stable UUID shared with external hiring app (generated at creation)
-- active_login_email: Whichever email is currently used for login (personal or company)
-- user_id: Filled once the onboarding flow completes and a login is created
-- All FKs → users(id) with ON DELETE RESTRICT
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_joinee (
    id INT AUTO_INCREMENT PRIMARY KEY,
    person_id VARCHAR(36) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    personal_email VARCHAR(255) UNIQUE NOT NULL,
    company_email VARCHAR(255) UNIQUE NULL,
    temp_password_changed BOOLEAN DEFAULT FALSE,
    active_login_email VARCHAR(255) NOT NULL,
    onboarding_status ENUM('PENDING', 'DOCUMENTS_SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED', 'VERIFIED') DEFAULT 'PENDING',
    assigned_role VARCHAR(100) NULL,
    assigned_department VARCHAR(100) NULL,
    joining_date DATE NULL,
    created_by_user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    user_id INT UNIQUE NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_oj_person_id (person_id),
    INDEX idx_oj_status (onboarding_status),
    INDEX idx_oj_created_by (created_by_user_id)
);

-- ─────────────────────────────────────────────────────────────────────────
-- 2b. onboarding_declaration — Full background information form
-- Contains: personal info, current + permanent address, ID proofs,
--           education (3 entries), employment (6 entries), Yes/No checks,
--           onsite/visa details (JSON), letter of authorization, HR review
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_declaration (
    id INT AUTO_INCREMENT PRIMARY KEY,
    joinee_id INT NOT NULL,

    -- PERSONAL INFORMATION
    full_name VARCHAR(255),
    contact_no VARCHAR(20),
    email_id VARCHAR(255),
    father_name VARCHAR(255),
    gender ENUM('Male', 'Female', 'Other'),
    actual_dob DATE,
    certificate_dob DATE,

    -- CURRENT ADDRESS
    current_address TEXT,
    current_landmark VARCHAR(255),
    current_landline VARCHAR(20),
    current_mobile VARCHAR(20),
    current_period_of_stay VARCHAR(100),
    current_nature_of_residence VARCHAR(100),

    -- PERMANENT ADDRESS
    permanent_address TEXT,
    permanent_landmark VARCHAR(255),
    permanent_landline VARCHAR(20),
    permanent_mobile VARCHAR(20),
    permanent_period_of_stay VARCHAR(100),
    permanent_nature_of_residence VARCHAR(100),

    -- ADDRESS & ID PROOF
    pan_number VARCHAR(20),
    aadhar_number VARCHAR(20),
    passport_name VARCHAR(255),
    passport_issue_date DATE NULL,
    passport_expiry_date DATE NULL,
    passport_place_of_issue VARCHAR(255),
    other_id_details TEXT,

    -- ACADEMIC DETAILS — Institution 1
    edu1_qualification VARCHAR(255),
    edu1_specialization VARCHAR(255),
    edu1_college_name VARCHAR(255),
    edu1_address TEXT,
    edu1_university VARCHAR(255),
    edu1_period VARCHAR(100),
    edu1_program ENUM('Full Time', 'Part Time'),

    -- Institution 2
    edu2_qualification VARCHAR(255),
    edu2_specialization VARCHAR(255),
    edu2_college_name VARCHAR(255),
    edu2_address TEXT,
    edu2_university VARCHAR(255),
    edu2_period VARCHAR(100),
    edu2_program ENUM('Full Time', 'Part Time'),

    -- Institution 3
    edu3_qualification VARCHAR(255),
    edu3_specialization VARCHAR(255),
    edu3_college_name VARCHAR(255),
    edu3_address TEXT,
    edu3_university VARCHAR(255),
    edu3_period VARCHAR(100),
    edu3_program ENUM('Full Time', 'Part Time'),

    -- EMPLOYMENT DETAILS — Employment 1 (Latest)
    emp1_company_name VARCHAR(255),
    emp1_employee_id VARCHAR(100),
    emp1_address TEXT,
    emp1_doj DATE NULL,
    emp1_lwd DATE NULL,
    emp1_city VARCHAR(100),
    emp1_designation VARCHAR(255),
    emp1_state VARCHAR(100),
    emp1_remuneration VARCHAR(100),
    emp1_contact1 VARCHAR(20),
    emp1_reported_to VARCHAR(255),
    emp1_contact2 VARCHAR(20),
    emp1_reported_person_designation VARCHAR(255),
    emp1_reason_for_leaving TEXT,

    -- Employment 2
    emp2_company_name VARCHAR(255),
    emp2_employee_id VARCHAR(100),
    emp2_address TEXT,
    emp2_doj DATE NULL,
    emp2_lwd DATE NULL,
    emp2_city VARCHAR(100),
    emp2_designation VARCHAR(255),
    emp2_state VARCHAR(100),
    emp2_remuneration VARCHAR(100),
    emp2_contact1 VARCHAR(20),
    emp2_reported_to VARCHAR(255),
    emp2_contact2 VARCHAR(20),
    emp2_reported_person_designation VARCHAR(255),
    emp2_reason_for_leaving TEXT,

    -- Employment 3
    emp3_company_name VARCHAR(255),
    emp3_employee_id VARCHAR(100),
    emp3_address TEXT,
    emp3_doj DATE NULL,
    emp3_lwd DATE NULL,
    emp3_city VARCHAR(100),
    emp3_designation VARCHAR(255),
    emp3_state VARCHAR(100),
    emp3_remuneration VARCHAR(100),
    emp3_contact1 VARCHAR(20),
    emp3_reported_to VARCHAR(255),
    emp3_contact2 VARCHAR(20),
    emp3_reported_person_designation VARCHAR(255),
    emp3_reason_for_leaving TEXT,

    -- Employment 4
    emp4_company_name VARCHAR(255),
    emp4_employee_id VARCHAR(100),
    emp4_address TEXT,
    emp4_doj DATE NULL,
    emp4_lwd DATE NULL,
    emp4_city VARCHAR(100),
    emp4_designation VARCHAR(255),
    emp4_state VARCHAR(100),
    emp4_remuneration VARCHAR(100),
    emp4_contact1 VARCHAR(20),
    emp4_reported_to VARCHAR(255),
    emp4_contact2 VARCHAR(20),
    emp4_reported_person_designation VARCHAR(255),
    emp4_reason_for_leaving TEXT,

    -- Employment 5
    emp5_company_name VARCHAR(255),
    emp5_employee_id VARCHAR(100),
    emp5_address TEXT,
    emp5_doj DATE NULL,
    emp5_lwd DATE NULL,
    emp5_city VARCHAR(100),
    emp5_designation VARCHAR(255),
    emp5_state VARCHAR(100),
    emp5_remuneration VARCHAR(100),
    emp5_contact1 VARCHAR(20),
    emp5_reported_to VARCHAR(255),
    emp5_contact2 VARCHAR(20),
    emp5_reported_person_designation VARCHAR(255),
    emp5_reason_for_leaving TEXT,

    -- Employment 6
    emp6_company_name VARCHAR(255),
    emp6_employee_id VARCHAR(100),
    emp6_address TEXT,
    emp6_doj DATE NULL,
    emp6_lwd DATE NULL,
    emp6_city VARCHAR(100),
    emp6_designation VARCHAR(255),
    emp6_state VARCHAR(100),
    emp6_remuneration VARCHAR(100),
    emp6_contact1 VARCHAR(20),
    emp6_reported_to VARCHAR(255),
    emp6_contact2 VARCHAR(20),
    emp6_reported_person_designation VARCHAR(255),
    emp6_reason_for_leaving TEXT,

    -- OTHER DETAILS (Yes/No questions)
    has_service_bond ENUM('Yes', 'No'),
    has_service_bond_details TEXT,
    has_criminal_record ENUM('Yes', 'No'),
    has_criminal_record_details TEXT,
    knows_company_employee ENUM('Yes', 'No'),
    knows_company_employee_details TEXT,

    -- ONSITE DETAILS (international travel / visa)
    -- JSON array: [{country, visa_type, duration_of_stay, purpose}, ...] (up to 7)
    onsite_details JSON NULL,

    -- LETTER OF AUTHORIZATION
    declaration_full_name VARCHAR(255),
    declaration_date DATE NULL,
    declaration_place VARCHAR(255),
    declaration_agreed BOOLEAN DEFAULT FALSE,

    -- ADMIN / WORKFLOW FIELDS
    submitted_at TIMESTAMP NULL,
    hr_notes TEXT NULL,
    hr_reviewed_by INT NULL,
    hr_reviewed_at TIMESTAMP NULL,
    status ENUM('DRAFT', 'SUBMITTED', 'APPROVED', 'CHANGES_REQUESTED') DEFAULT 'DRAFT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (joinee_id) REFERENCES onboarding_joinee(id) ON DELETE RESTRICT,
    FOREIGN KEY (hr_reviewed_by) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_od_joinee (joinee_id),
    INDEX idx_od_status (status),
    INDEX idx_od_submitted (submitted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 ROW_FORMAT=DYNAMIC;

-- ─────────────────────────────────────────────────────────────────────────
-- 2c. onboarding_references — Professional references (min 3, max 6)
-- Each reference links to both the declaration (for the form context) and
-- the joinee (for easy lookup). sort_order defines display order (1-6).
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_references (
    id INT AUTO_INCREMENT PRIMARY KEY,
    declaration_id INT NOT NULL,
    joinee_id INT NOT NULL,
    ref_name VARCHAR(255),
    ref_designation VARCHAR(255),
    ref_phone VARCHAR(20),
    ref_email VARCHAR(255),
    ref_company_name VARCHAR(255),
    candidate_designation VARCHAR(255),
    sort_order TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (declaration_id) REFERENCES onboarding_declaration(id) ON DELETE RESTRICT,
    FOREIGN KEY (joinee_id) REFERENCES onboarding_joinee(id) ON DELETE RESTRICT,
    INDEX idx_or_declaration (declaration_id),
    INDEX idx_or_joinee (joinee_id)
);

-- ─────────────────────────────────────────────────────────────────────────
-- 2d. onboarding_documents — Document upload & verification
-- Tracks each uploaded document with its verification workflow.
-- verified_by links to users(id) of the HR/admin who reviewed it.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    joinee_id INT NOT NULL,
    document_type ENUM('AADHAR', 'PAN', 'PASSPORT_COPY', 'ACADEMIC_CERTIFICATE', 'OFFER_LETTER', 'RELIEVING_LETTER', 'PAY_SLIP', 'APPRAISAL_LETTER', 'DRIVING_LICENSE_VOTER_ID', 'PHOTO', 'OTHER') NOT NULL,
    document_label VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_original_name VARCHAR(255) NOT NULL,
    file_size_bytes INT,
    mime_type VARCHAR(100),
    verification_status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
    rejection_reason TEXT NULL,
    verified_by INT NULL,
    verified_at TIMESTAMP NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (joinee_id) REFERENCES onboarding_joinee(id) ON DELETE RESTRICT,
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_odoc_joinee (joinee_id),
    INDEX idx_odoc_status (verification_status),
    INDEX idx_odoc_type (document_type)
);

-- ─────────────────────────────────────────────────────────────────────────
-- 2e. onboarding_audit_log — Immutable audit trail
-- Records every meaningful action on a joinee record:
--   'STATUS_CHANGED', 'DOCUMENT_VERIFIED', 'LOGIN_MIGRATED', etc.
-- old_value / new_value store JSON or plain-text snapshots.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    joinee_id INT NOT NULL,
    action VARCHAR(100) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    performed_by INT NULL,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT NULL,
    FOREIGN KEY (joinee_id) REFERENCES onboarding_joinee(id) ON DELETE RESTRICT,
    FOREIGN KEY (performed_by) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_oal_joinee (joinee_id),
    INDEX idx_oal_action (action),
    INDEX idx_oal_performed_at (performed_at)
);
