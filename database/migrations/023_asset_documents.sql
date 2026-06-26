-- ============================================================================
-- Migration 023: Asset Documents
-- ============================================================================
-- Adds device_documents table to store Invoice, Warranty, and other
-- attachments linked to a device.
-- ============================================================================

CREATE TABLE IF NOT EXISTS device_documents (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    device_id      INT NOT NULL,
    document_type  ENUM('Invoice', 'Warranty', 'Purchase Document', 'User Manual', 'Other Attachments') NOT NULL,
    file_url       VARCHAR(255) NOT NULL,
    uploaded_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    INDEX idx_dd_device (device_id)
);
