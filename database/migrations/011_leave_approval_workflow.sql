-- =============================================================================
-- Migration 011: Role-Based Leave Approval Workflow
-- =============================================================================
-- Adds audit columns to `leaves` and creates a new `leave_approval_history`
-- table for a full immutable audit trail of every approval decision.
-- Idempotent: uses ALTER IGNORE / IF NOT EXISTS so re-running is safe.
-- =============================================================================

USE starterdata;

-- ── Step 1: Add audit & hierarchy columns to `leaves` ──────────────────────

ALTER TABLE leaves
  ADD COLUMN approved_by      VARCHAR(100) NULL       COMMENT 'employee_name of whoever approved/rejected',
  ADD COLUMN approver_role    VARCHAR(50)  NULL       COMMENT 'role snapshot of the approver at decision time',
  ADD COLUMN approved_at      TIMESTAMP    NULL       COMMENT 'timestamp of the approval/rejection decision',
  ADD COLUMN rejection_reason TEXT         NULL       COMMENT 'reason provided when rejecting a leave',
  ADD COLUMN requester_role   VARCHAR(50)  NULL       COMMENT 'role of the applicant at apply time (snapshot)';

-- ── Step 2: Index on approved_by for manager dashboard queries ──────────────

CREATE INDEX idx_leave_approved_by ON leaves (approved_by);

-- ── Step 3: Create leave_approval_history — immutable audit trail ───────────

CREATE TABLE IF NOT EXISTS leave_approval_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    leave_id    INT          NOT NULL,
    action      ENUM('submitted', 'approved', 'rejected', 'cancelled') NOT NULL,
    actor       VARCHAR(100) NOT NULL   COMMENT 'employee_name of whoever performed the action',
    actor_role  VARCHAR(50)  NOT NULL   COMMENT 'role snapshot of the actor at action time',
    reason      TEXT         NULL       COMMENT 'optional note — required on rejection',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (leave_id) REFERENCES leaves(id) ON DELETE CASCADE,
    INDEX idx_lah_leave    (leave_id),
    INDEX idx_lah_actor    (actor),
    INDEX idx_lah_created  (created_at)
) COMMENT='Immutable audit trail for every leave approval action';
