-- Migration 034: Timesheet Access Control Permission Setup & Seed

-- 1. Insert/Update Permission Catalog Entries (View and Manage)
INSERT INTO permissions (module, permission_key, label, description, route_reference)
VALUES 
('timesheets', 'timesheets.view', 'View Timesheets', 'View and track timesheets and work logs', 'GET /timesheets/'),
('timesheets', 'timesheets.manage', 'Manage Timesheets', 'Review, approve, and reject timesheet entries', 'PATCH /timesheets/<id>/review')
ON DUPLICATE KEY UPDATE label = VALUES(label), description = VALUES(description), route_reference = VALUES(route_reference);

-- 2. Seed Default Role Grants for timesheets.view (Superadmin, Admin, HR, Manager)
INSERT INTO role_permissions (role, permission_id, is_granted)
SELECT r.role, p.id,
       CASE WHEN r.role IN ('superadmin', 'admin', 'hr', 'manager') THEN TRUE ELSE FALSE END
FROM (
    SELECT 'superadmin' AS role
    UNION SELECT 'admin'
    UNION SELECT 'hr'
    UNION SELECT 'manager'
    UNION SELECT 'employee'
    UNION SELECT 'team_member'
    UNION SELECT 'onboarding_candidate'
    UNION SELECT 'system_admin'
) r
CROSS JOIN permissions p
WHERE p.permission_key = 'timesheets.view'
ON DUPLICATE KEY UPDATE role = VALUES(role);

-- 3. Seed Default Role Grants for timesheets.manage (Superadmin, Admin, Manager)
INSERT INTO role_permissions (role, permission_id, is_granted)
SELECT r.role, p.id,
       CASE WHEN r.role IN ('superadmin', 'admin', 'manager') THEN TRUE ELSE FALSE END
FROM (
    SELECT 'superadmin' AS role
    UNION SELECT 'admin'
    UNION SELECT 'hr'
    UNION SELECT 'manager'
    UNION SELECT 'employee'
    UNION SELECT 'team_member'
    UNION SELECT 'onboarding_candidate'
    UNION SELECT 'system_admin'
) r
CROSS JOIN permissions p
WHERE p.permission_key = 'timesheets.manage'
ON DUPLICATE KEY UPDATE role = VALUES(role);
