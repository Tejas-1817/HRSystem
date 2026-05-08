-- Table: devices
CREATE TABLE IF NOT EXISTS devices (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    device_type    VARCHAR(50) NOT NULL DEFAULT 'Laptop',
    brand          VARCHAR(100) NOT NULL,
    model          VARCHAR(100) NOT NULL,
    serial_number  VARCHAR(100) UNIQUE NOT NULL,
    status         ENUM('Available', 'Assigned', 'Under Repair', 'Retired') NOT NULL DEFAULT 'Available',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_device_status (status),
    INDEX idx_device_serial (serial_number)
);

-- Table: device_assignments
CREATE TABLE IF NOT EXISTS device_assignments (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    device_id       INT NOT NULL,
    employee_name  VARCHAR(100) NOT NULL,
    assigned_date  DATE NOT NULL,
    returned_date  DATE NULL,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    INDEX idx_da_employee (employee_name),
    INDEX idx_da_device   (device_id)
);

-- Table: device_images
CREATE TABLE IF NOT EXISTS device_images (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    device_id       INT NOT NULL,
    image_url      VARCHAR(255) NOT NULL,
    uploaded_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    INDEX idx_di_device (device_id)
);

-- Update helpdesk_tickets table
ALTER TABLE helpdesk_tickets ADD COLUMN device_id INT NULL;
ALTER TABLE helpdesk_tickets ADD COLUMN issue_type ENUM('Hardware', 'Software', 'Network') NULL;
ALTER TABLE helpdesk_tickets ADD CONSTRAINT fk_hd_device FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL;
