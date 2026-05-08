USE starterdata;

INSERT IGNORE INTO employee (name, email, phone, id, salary, date_of_birth, date_of_joining) VALUES
('M_Tejas', 'tejas@gmail.com', 8362954547, '19950514', 65000.00, '1995-05-14', '2020-06-01'),
-- ('H_Riya', 'riya@example.com', 9365847545, '19901123', 72000.00, '1990-11-23', '2018-03-15'),
('T_Raj', 'raj@gmail.com', 7385694562, '19880217', 58000.00, '1988-02-17', '2019-01-10'),
-- ('T_Sneha', 'sneha@example.com', 789985636, '20000809', 50000.00, '2000-04-10', '2023-07-01'),
('H_Saurabh', 'saurabh@gmail.com', 8885695257, '19931230', 61000.00, '1993-12-30', '2021-09-20');
-- ('M_Priyanka', 'priyanka@example.com', 9999548565, '19850712', 84000.00, '1985-07-12', '2015-04-01'),
-- ('T_Aisha', 'aisha@example.com', 8788995547, '19970325', 56000.00, '1997-03-25', '2022-11-15'),
-- ('T_Aditya', 'aditya@example.com', 8256976345, '19920617', 69000.00, '1992-04-15', '2020-01-06'),
-- ('T_Meera', 'meera@example.com', 8695471423, '19890905', 77000.00, '1989-09-05', '2017-08-21'),
-- ("T_Omkar", "omkar@example.com", 8796563214, 1, 60000, '1996-01-20', '2022-02-14'),
-- ("T_Arnav", "arnav@example.com", 8796563214, 9, 330000, '1994-06-08', '2019-06-01'),
-- ("T_Santosh", "santosh@example.com", 6556563214, 10, 550000, '1991-08-15', '2016-10-03'),
-- ("T_Snehal", "snehal@example.com", 9376563214, 11, 570000, '1993-04-25', '2021-04-12'),
-- ("T_Manasi", "manasi@example.com", 9376563896, 12, 580000, '1995-10-12', '2020-08-01'),
-- ("T_Shreyash", "shreyash@example.com", 7856563896, 13, 600000, '1990-04-06', '2018-12-01'),
-- ("T_Sanket", "sanket@example.com", 9572563896, 17, 700000, '1992-11-30', '2017-05-15'),
-- ("T_Shubham", "shubham@example.com", 9882563896, 27, 800000, '1994-03-18', '2019-09-09'),
-- ("T_Manoj", "manoj@example.com", 8382563896, 28, 400000, '1988-07-04', '2023-01-02'),
-- ("T_Mayur", "mayur@gmail.com", 8282563896, 21, 400000, '1991-12-25', '2024-03-01'),
-- ("T_Kartik", "kartik@gmail.com", 8282563123, 22, 200000, '2000-04-06', '2025-10-01'),
-- ("T_Avira", "avira@gmail.com", 7772563123, 23, 300000, '1998-05-22', '2026-01-15'),
-- ("T_rakesh", "rakesh@gmail.com", 7772563123, 30, 300000, '1996-08-30', '2026-03-01');

INSERT IGNORE INTO projects (id, project_id, name, status, manager_name, customer_name, contact_person, phone, email, start_date, end_date) VALUES
(1, 'PROJ-2026-001', 'Employee Records', 'ongoing', 'M_Tejas', 'Acme Corp', 'John Doe', '1234567890', 'john@acme.com', '2026-01-01', '2026-12-31'),
(2, 'PROJ-2026-002', 'Payroll System', 'ongoing', 'M_Priyanka', 'Globex', 'Jane Smith', '0987654321', 'jane@globex.com', '2026-02-15', '2026-11-30'),
(3, 'PROJ-2026-003', 'Leave Management', 'completed', 'M_Tejas', 'Initech', 'Peter Gibbons', '5551234567', 'peter@initech.com', '2025-06-01', '2025-12-15');

-- 🔥 Seed Initial Project Assignments
INSERT IGNORE INTO project_assignments (project_id, employee_name, assigned_by) VALUES
(1, 'T_Kartik', 'M_Tejas'),
(2, 'T_Sneha', 'M_Priyanka'),
(3, 'T_Aditya', 'M_Tejas'),
(1, 'T_Raj', 'M_Tejas'),
(2, 'T_Aisha', 'M_Priyanka');

INSERT IGNORE INTO leaves (id, employee_name, leave_type, start_date, end_date, reason, status) VALUES
(1, 'M_Tejas', 'sick', '2026-04-05', '2026-04-06', 'Fever and cold', 'approved'),
(2, 'H_Riya', 'casual', '2026-04-10', '2026-04-11', 'Personal work', 'approved'),
(3, 'T_Kartik', 'earned', '2026-04-15', '2026-04-18', 'Family vacation', 'pending'),
(4, 'T_Sneha', 'sick', '2026-04-07', '2026-04-08', 'Doctor appointment', 'approved'),
(5, 'T_Aditya', 'casual', '2026-04-20', '2026-04-22', 'Friend wedding', 'pending'),
(6, 'T_Omkar', 'earned', '2026-04-25', '2026-04-30', 'Hometown visit', 'rejected'),
(7, 'T_Raj', 'sick', '2026-03-30', '2026-04-04', 'Recovery', 'approved'),
(8, 'T_Aisha', 'casual', '2026-04-01', '2026-04-03', 'Family event', 'approved'),
(9, 'T_Meera', 'sick', '2026-04-02', '2026-04-02', 'Sudden illness', 'approved');

INSERT IGNORE INTO leave_balance (employee_name, leave_type, total_leaves, used_leaves) VALUES
('M_Tejas', 'sick', 12, 2),
('M_Tejas', 'casual', 10, 0),
('M_Tejas', 'earned', 15, 0),
('H_Riya', 'sick', 12, 0),
('H_Riya', 'casual', 10, 2),
('H_Riya', 'earned', 15, 0),
('T_Kartik', 'sick', 12, 0),
('T_Kartik', 'casual', 10, 0),
('T_Kartik', 'earned', 15, 4),
('T_Sneha', 'sick', 12, 2),
('T_Sneha', 'casual', 10, 0),
('T_Sneha', 'earned', 15, 0),
('T_Aditya', 'sick', 12, 0),
('T_Aditya', 'casual', 10, 3),
('T_Aditya', 'earned', 15, 0),
('T_Omkar', 'sick', 12, 0),
('T_Omkar', 'casual', 10, 0),
('T_Omkar', 'earned', 15, 0),
('T_Raj', 'sick', 12, 0),
('T_Raj', 'casual', 10, 0),
('T_Raj', 'earned', 15, 0),
('M_Priyanka', 'sick', 12, 0),
('M_Priyanka', 'casual', 10, 0),
('M_Priyanka', 'earned', 15, 0);

-- 🔥 Seed users for RBAC (plain text passwords for dev — use /auth/register in production for hashed passwords)
INSERT IGNORE INTO users (username, password, role, employee_name, password_change_required) VALUES
('tejas@gmail.com', 'scrypt:32768:8:1$n3bveCVwFWHRi8GI$1ec9559dfee7ce749d878a29f5ff43452702d43e2e2cad9ffc2310f35960dbd7730be91921b23fec5df0a8299bca579ff8c1fae4ac397029bf34bce1fc502109', 'manager', 'M_Tejas', TRUE),
('priyanka@gmail.com', 'scrypt:32768:8:1$n3bveCVwFWHRi8GI$1ec9559dfee7ce749d878a29f5ff43452702d43e2e2cad9ffc2310f35960dbd7730be91921b23fec5df0a8299bca579ff8c1fae4ac397029bf34bce1fc502109', 'manager', 'M_Priyanka', TRUE),
('riya@gmail.com', 'scrypt:32768:8:1$WwpdJ1Bbza6nHrdP$e06177224864057476f05d94e44b24dbac3b06596ba40277f1f7fee925e2ef416e88ba9c82d9b3122bc7bc663a5d8277a5555011412c3b5c09f4930026eb77fe', 'hr', 'H_Riya', TRUE),
('saurabh@gmail.com', 'scrypt:32768:8:1$WwpdJ1Bbza6nHrdP$e06177224864057476f05d94e44b24dbac3b06596ba40277f1f7fee925e2ef416e88ba9c82d9b3122bc7bc663a5d8277a5555011412c3b5c09f4930026eb77fe', 'hr', 'H_Saurabh', TRUE),
('kartik@gmail.com', 'scrypt:32768:8:1$8XZrPvIBnpC3nuom$7c2af0069397e7471608b6b1fe0537f0fe271214c6b5b202171de7b5bad1ddb9ccfc208f584dc0c87973dc5a5dd793c8f4e7f6158b628f1b00acd7ec7480a90c', 'employee', 'T_Kartik', TRUE),
('sneha@gmail.com', 'scrypt:32768:8:1$THLOyrLwEe6gl7uE$a4b7b7fade6dd0070d9e5d3a2cdb7bab120627029943da99a2160aebc06ab49ba48666a64ee5bdd90bc3bd146982dcd4240cb6904d5d4f3ff3c7c969ac9bddbd', 'employee', 'T_Sneha', TRUE),
('aditya@gmail.com', 'scrypt:32768:8:1$nnjy7MvglCaGAIFk$f41726578e7880fcbd3fa84d0fbb7b4c4f2ec1a210c61c6a6f752e177b43ad230432a1707f602fc82b5aad1058859fd58bd1fabe0e825b9d515e504dcd5b4f4c', 'employee', 'T_Aditya', TRUE),
('omkar@gmail.com', 'scrypt:32768:8:1$ncEhdhSc6yHKl4Mv$8ab7aaec316d70421654fab42ea9534cde350a1bcf197c1244228b6f915b6c3f592698ee7b26ad24098925c1c0ecbae608050495c763b559684d4932aee3cd00', 'employee', 'T_Omkar', TRUE),
('raj@gmail.com', 'scrypt:32768:8:1$eXjvLKJW0cOKuiMC$e490b2c364e4645649ba4cec063ae6f28f91172b395341b4a7f8ca360e51ea129f9d621dd71d57f5c38263cd31fe85ddf9870b7386910a01a23a522fc9cecb73', 'employee', 'T_Raj', TRUE),
('aisha@gmail.com', 'scrypt:32768:8:1$frUKP2nyRXDysGCw$105f400e788767eee20b80a0df0e9dd0fe029448016da712be490f2be08b131fcc955961ecf0549d7a98fc6793176119fe5609a852c46cc2c3375554e390ff36', 'employee', 'T_Aisha', TRUE);

-- 🔥 Attendance and daily_work_config are legacy/deprecated in this release.
-- Attendance is derived from timesheet entries via GET /attendance.

-- 🔥 Seed Timesheets (project-level task tracking)
INSERT IGNORE INTO timesheets (employee_name, project, task, description, hours, start_date, status, manager_comments, manager_name) VALUES
('T_Kartik', 'Employee Records', 'Database Design', 'Designed employee table schema', 8, '2026-04-01', 'approved', 'Great work on the normalization.', 'M_Tejas'),
('T_Sneha', 'Payroll System', 'Payslip Module', 'Built payslip generation feature', 6, '2026-04-01', 'pending', NULL, NULL),
('T_Aditya', 'Leave Management', 'Leave Balance', 'Implemented leave balance tracking', 4, '2026-04-01', 'rejected', 'Please clarify the carry-forward logic.', 'M_Tejas'),
('T_Kartik', 'Employee Records', 'API Development', 'Created CRUD endpoints', 10, '2026-04-02', 'pending', NULL, NULL),
('T_Raj', 'Payroll System', 'Tax Calculation', 'Added tax deduction logic', 8, '2026-04-01', 'pending', NULL, NULL);

-- 🔥 Seed Payslips
INSERT IGNORE INTO payslips (employee_name, month, year, file_path) VALUES
('T_Kartik', 'March', 2026, 'uploads/kartik_payslip_march.pdf'),
('T_Sneha', 'March', 2026, 'uploads/sneha_payslip_march.pdf');

-- 🔥 Seed Holidays (public, company, optional for 2026)
INSERT IGNORE INTO holidays (name, date, type, description) VALUES
('New Year''s Day',        '2026-01-01', 'public',   'New Year celebration'),
('Republic Day',           '2026-01-26', 'public',   'Indian Republic Day'),
('Holi',                   '2026-03-17', 'public',   'Festival of Colors'),
('Good Friday',            '2026-04-03', 'public',   'Christian observance'),
('Eid al-Fitr',            '2026-04-10', 'public',   'End of Ramadan'),
('May Day',                '2026-05-01', 'public',   'International Workers Day'),
('Independence Day',       '2026-08-15', 'public',   'Indian Independence Day'),
('Ganesh Chaturthi',       '2026-08-27', 'public',   'Lord Ganesha festival'),
('Gandhi Jayanti',         '2026-10-02', 'public',   'Mahatma Gandhi birthday'),
('Dussehra',               '2026-10-12', 'public',   'Victory of good over evil'),
('Diwali',                 '2026-11-05', 'public',   'Festival of Lights'),
('Christmas',              '2026-12-25', 'public',   'Christmas Day'),
('Company Foundation Day', '2026-06-15', 'company',  'Anniversary of company founding'),
('Annual Day',             '2026-09-20', 'company',  'Company annual gathering'),
('Birthday Leave',         '2026-01-01', 'optional', 'Employees may take their birthday off'),
('Voting Day',             '2026-04-20', 'optional', 'Election day — optional leave');

-- 🔥 Seed Employee Documents (with access control: is_confidential = TRUE for all sensitive docs)
INSERT IGNORE INTO employee_documents (employee_name, doc_type, file_path, status, is_confidential, verified_by, verified_at) VALUES
('T_Kartik', 'pan_card',        'uploads/kartik_pan.pdf',        'verified',  TRUE, 'H_Riya', '2025-10-05 10:00:00'),
('T_Kartik', 'aadhar_card',     'uploads/kartik_aadhar.pdf',     'verified',  TRUE, 'H_Riya', '2025-10-05 10:05:00'),
('T_Kartik', 'tenth_cert',      'uploads/kartik_10th.pdf',       'verified',  TRUE, 'H_Riya', '2025-10-05 10:10:00'),
('T_Kartik', 'twelfth_cert',    'uploads/kartik_12th.pdf',       'uploaded',  TRUE, NULL, NULL),
('T_Kartik', 'graduation_cert', 'uploads/kartik_grad.pdf',       'uploaded',  TRUE, NULL, NULL),
('T_Sneha',  'pan_card',        'uploads/sneha_pan.pdf',         'verified',  TRUE, 'H_Riya', '2023-07-10 09:00:00'),
('T_Sneha',  'aadhar_card',     'uploads/sneha_aadhar.pdf',      'verified',  TRUE, 'H_Riya', '2023-07-10 09:05:00'),
('T_Sneha',  'tenth_cert',      'uploads/sneha_10th.pdf',        'verified',  TRUE, 'H_Riya', '2023-07-10 09:10:00'),
('T_Sneha',  'twelfth_cert',    'uploads/sneha_12th.pdf',        'verified',  TRUE, 'H_Riya', '2023-07-10 09:15:00'),
('T_Sneha',  'graduation_cert', 'uploads/sneha_grad.pdf',        'verified',  TRUE, 'H_Riya', '2023-07-10 09:20:00'),
('T_Aditya', 'pan_card',        'uploads/aditya_pan.pdf',        'uploaded',  TRUE, NULL, NULL),
('T_Aditya', 'aadhar_card',     'uploads/aditya_aadhar.pdf',     'uploaded',  TRUE, NULL, NULL),
('T_Raj',    'pan_card',        'uploads/raj_pan.pdf',           'verified',  TRUE, 'H_Saurabh', '2019-02-01 11:00:00'),
('T_Raj',    'aadhar_card',     NULL,                            'pending',   TRUE, NULL, NULL),
('T_Raj',    'tenth_cert',      'uploads/raj_10th_blurry.pdf',   'rejected',  TRUE, 'H_Riya', '2019-02-02 14:00:00');

-- Set rejection reason for Raj's 10th cert
UPDATE employee_documents SET rejection_reason='Document is blurry and unreadable. Please re-upload a clear scan.' WHERE employee_name='T_Raj' AND doc_type='tenth_cert';

--  Seed Company Policies
INSERT IGNORE INTO policies (category, title, content, updated_by) VALUES
('Core HR', 'Leave Policy', 'Employees are entitled to 12 Sick leaves, 10 Casual leaves, and 15 Earned leaves per year. Unused earned leaves can be carried forward up to 45 days.', 'H_Riya'),
('Core HR', 'Attendance & Working Hours', 'Standard working hours are 9:00 AM to 6:00 PM with 1-hour break. Late login threshold is 9:30 AM. Minimum 8 hours required for a full day.', 'H_Riya'),
('Core HR', 'Payroll & Salary', 'Salaries are processed on the 1st of every month. Deductions include PF, PT, and TDS. Bonuses are performance-based.', 'H_Riya'),
('IT', 'Software/Hardware', 'Employees must use company devices (laptops, desktops, hardware) only for official purposes. Installation of unauthorized software is strictly prohibited. Employees must not share login credentials or system access. Devices must be secured with passwords and antivirus software. Any loss or damage must be reported immediately to IT/HR.', 'H_Riya');

--  Seed Notifications for testing the new system
INSERT IGNORE INTO notifications (employee_name, title, message) VALUES
('M_Priyanka', 'New Project Assignment', 'You have been assigned to the project Employee Records by M_Tejas.'),
('T_Kartik', 'New Project Assignment', 'You have been assigned to the project Employee Records by M_Tejas.'),
('T_Sneha', 'New Project Assignment', 'You have been assigned to the project Payroll System by M_Priyanka.');

--  Extra Project Assignment to test cross-manager visibility (Priyanka assigned to Tejas's project)
INSERT IGNORE INTO project_assignments (project_id, employee_name, assigned_by) VALUES
(1, 'M_Priyanka', 'M_Tejas');

-- 🔥 Seed Leave Configuration (default quotas for auto-allocation)
INSERT IGNORE INTO leave_config (leave_type, default_total, description) VALUES
('sick',   12,  'Medical / health related leave'),
('casual', 10,  'Personal / casual leave'),
('earned', 15,  'Earned / privilege leave (carry-forward eligible)');
