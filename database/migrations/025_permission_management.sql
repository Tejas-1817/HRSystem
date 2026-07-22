CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    permission_key VARCHAR(150) UNIQUE NOT NULL,   -- e.g. 'devices.create'
    module VARCHAR(100) NOT NULL,                   -- e.g. 'devices' — for grouping in the UI
    label VARCHAR(255) NOT NULL,                     -- human-readable, e.g. "Add a new device"
    description TEXT NULL,
    route_reference VARCHAR(255) NULL,               -- e.g. 'POST /devices/' — traceability back to code
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_perm_module (module)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role VARCHAR(50) NOT NULL,                       -- 'hr', 'manager', 'employee', 'accounts', 'admin', etc. (never 'superadmin' — see §6)
    permission_id INT NOT NULL,
    is_granted BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by INT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE KEY uniq_role_permission (role, permission_id),
    INDEX idx_rp_role (role)
);

CREATE TABLE IF NOT EXISTS role_permission_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role VARCHAR(50) NOT NULL,
    permission_id INT NOT NULL,
    old_value BOOLEAN NULL,
    new_value BOOLEAN NOT NULL,
    changed_by INT NOT NULL,
    changed_by_name VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_rpal_role (role),
    INDEX idx_rpal_permission (permission_id)
);
