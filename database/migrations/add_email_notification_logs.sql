-- =============================================================================
-- Migration: Add email_notification_logs table
-- Purpose:   Enterprise audit trail for every email notification attempt
--            triggered by the HRMS leave workflow.
-- Run once:  mysql -u <user> -p starterdata < add_email_notification_logs.sql
-- =============================================================================

USE starterdata;

CREATE TABLE IF NOT EXISTS email_notification_logs (
    id                INT AUTO_INCREMENT PRIMARY KEY,

    -- What kind of notification was sent
    notification_type VARCHAR(50)  NOT NULL,        -- 'leave_application' | 'leave_approved' | 'leave_rejected'

    -- Who received it
    recipient_email   VARCHAR(150) NOT NULL,
    recipient_name    VARCHAR(100),

    -- Foreign key context (nullable — emails can be sent for other events too)
    leave_id          INT          DEFAULT NULL,

    -- Delivery status (populated after async thread completes)
    notification_sent BOOLEAN      NOT NULL DEFAULT FALSE,
    sent_at           TIMESTAMP    NULL DEFAULT NULL,
    error_message     TEXT         DEFAULT NULL,

    -- Audit timestamps
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for dashboard queries and compliance audits
    INDEX idx_enl_leave (leave_id),
    INDEX idx_enl_type  (notification_type),
    INDEX idx_enl_sent  (notification_sent),
    INDEX idx_enl_recipient (recipient_email)
);
