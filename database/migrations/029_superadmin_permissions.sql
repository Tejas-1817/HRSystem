-- Migration 029: Grant all permissions to Super Admin
-- Populates role_permissions for superadmin across all existing permissions

INSERT INTO role_permissions (role, permission_id, is_granted)
SELECT 'superadmin', id, TRUE
FROM permissions
ON DUPLICATE KEY UPDATE is_granted = TRUE;
