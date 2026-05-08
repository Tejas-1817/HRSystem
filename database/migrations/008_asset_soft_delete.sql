-- ============================================================================
-- Migration 008: Asset Soft Delete
-- ============================================================================
-- Adds soft-delete columns to the devices table for audit-safe asset removal.
-- ============================================================================

ALTER TABLE devices
    ADD COLUMN is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN deleted_at  TIMESTAMP NULL,
    ADD COLUMN deleted_by  VARCHAR(100) NULL;

ALTER TABLE devices ADD INDEX idx_device_deleted (is_deleted);
