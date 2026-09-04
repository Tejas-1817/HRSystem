-- Migration 031: Seed and ensure all permissions exist for superadmin in role_permissions
INSERT INTO role_permissions (role, permission_id, is_granted)
SELECT 'superadmin', p.id, TRUE
FROM permissions p
ON DUPLICATE KEY UPDATE is_granted = VALUES(is_granted);
