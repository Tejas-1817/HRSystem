-- Migration 028: Timesheet manager assignment, employee role sync, and 2026 holiday timetable

-- 1. Ensure manager_name column exists on timesheets table
ALTER TABLE timesheets 
ADD COLUMN IF NOT EXISTS manager_name VARCHAR(100) DEFAULT NULL AFTER start_date;

-- 2. Ensure role column on employee table supports all system roles
ALTER TABLE employee 
MODIFY COLUMN role VARCHAR(50) DEFAULT 'employee';

-- 3. Sync employee table roles from users table
UPDATE employee e
JOIN users u ON e.name = u.employee_name
SET e.role = u.role
WHERE u.role IS NOT NULL;

-- 4. Clean and re-seed 2026 organization holidays (8 Public, 6 Optional)
DELETE FROM holidays WHERE YEAR(date) = 2026;

INSERT INTO holidays (name, date, type, description) VALUES
('Republic Day', '2026-01-26', 'public', 'National Holiday - Republic Day'),
('May Day & Maharashtra Day', '2026-05-01', 'public', 'Labour Day and Maharashtra Formation Day'),
('Bakrid', '2026-05-28', 'public', 'Eid ul-Adha'),
('Independence Day', '2026-08-15', 'public', 'National Holiday - Independence Day'),
('Ganesh Chaturthi', '2026-09-14', 'public', 'Ganesh Utsav celebration'),
('Gandhi Jayanti', '2026-10-02', 'public', 'National Holiday - Mahatma Gandhi Birthday'),
('Diwali', '2026-11-09', 'public', 'Festival of Lights - Deepavali'),
('Christmas', '2026-12-25', 'public', 'Christmas Day celebration'),
('New Years', '2026-01-01', 'optional', 'New Year Day'),
('Makara Sankranthi', '2026-01-15', 'optional', 'Harvest Festival - Pongal / Sankranthi'),
('Holi', '2026-03-03', 'optional', 'Festival of Colors'),
('Ugadi/Gudi Padwa', '2026-03-19', 'optional', 'New Year Festival - Ugadi / Gudi Padwa'),
('Good Friday', '2026-04-03', 'optional', 'Good Friday Christian observance'),
('Dasara', '2026-10-20', 'optional', 'Vijayadashami / Dussehra celebration');
