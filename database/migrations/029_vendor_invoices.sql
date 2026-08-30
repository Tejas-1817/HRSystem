-- Migration: Create vendor_invoices table
-- This table was referenced by rental_service.py, device_service.py, and rental_invoice_routes.py
-- but never had a CREATE TABLE migration.

CREATE TABLE IF NOT EXISTS vendor_invoices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vendor_name VARCHAR(255) NOT NULL,
    invoice_number VARCHAR(100) NOT NULL UNIQUE,
    status ENUM('Pending', 'Paid', 'Overdue', 'Cancelled') DEFAULT 'Pending',
    uploaded_file_path VARCHAR(255) NULL,
    uploaded_file_name VARCHAR(255) NULL,
    uploaded_file_type VARCHAR(50) NULL,
    uploaded_file_size INT NULL,
    uploaded_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_vendor_name (vendor_name),
    INDEX idx_invoice_status (status)
);
