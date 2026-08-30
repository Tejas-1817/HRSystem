"""
Migration 030: Multi-Approver Leave Signoff Workflow (HR + All Assigned Project Managers)
"""

import sys
import os
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def run_migration():
    try:
        with Transaction() as cursor:
            # Check if table already exists
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'leave_signoffs'
            """)
            result = cursor.fetchone()
            if result and result['cnt'] > 0:
                logger.info("leave_signoffs already exists.")
            else:
                logger.info("Creating leave_signoffs table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leave_signoffs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        leave_id INT NOT NULL,
                        approver_role VARCHAR(50) NOT NULL,
                        approver_name VARCHAR(100) NULL,
                        project_name VARCHAR(100) NULL,
                        status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                        action_by VARCHAR(100) NULL,
                        action_at TIMESTAMP NULL,
                        comments TEXT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (leave_id) REFERENCES leaves(id) ON DELETE CASCADE,
                        INDEX idx_ls_leave (leave_id),
                        INDEX idx_ls_approver (approver_name, approver_role),
                        INDEX idx_ls_status (status)
                    )
                """)
                logger.info("leave_signoffs table created successfully.")

            # Backfill existing pending leaves if they don't have signoffs
            cursor.execute("""
                SELECT l.id, l.employee_name, l.requester_role
                FROM leaves l
                LEFT JOIN leave_signoffs ls ON l.id = ls.leave_id
                WHERE l.status = 'pending' AND ls.id IS NULL
            """)
            pending_leaves = cursor.fetchall() or []
            logger.info("Found %d pending leaves to backfill signoffs.", len(pending_leaves))

            for l in pending_leaves:
                leave_id = l['id']
                emp_name = l['employee_name']
                req_role = l.get('requester_role') or 'employee'

                if req_role == 'employee':
                    # 1. Insert HR signoff
                    cursor.execute("""
                        INSERT INTO leave_signoffs (leave_id, approver_role, approver_name, project_name, status)
                        VALUES (%s, 'hr', NULL, NULL, 'pending')
                    """, (leave_id,))

                    # 2. Find active project managers
                    cursor.execute("""
                        SELECT DISTINCT p.manager_name, p.name AS project_name
                        FROM project_assignments pa
                        JOIN projects p ON pa.project_id = p.id
                        WHERE pa.employee_name = %s
                          AND p.status NOT IN ('completed', 'closed', 'cancelled')
                          AND p.manager_name IS NOT NULL AND p.manager_name != ''
                    """, (emp_name,))
                    mgrs = cursor.fetchall() or []
                    for m in mgrs:
                        cursor.execute("""
                            INSERT INTO leave_signoffs (leave_id, approver_role, approver_name, project_name, status)
                            VALUES (%s, 'manager', %s, %s, 'pending')
                        """, (leave_id, m['manager_name'], m['project_name']))
                else:
                    # Non-employee: Admin signoff
                    cursor.execute("""
                        INSERT INTO leave_signoffs (leave_id, approver_role, approver_name, project_name, status)
                        VALUES (%s, 'admin', NULL, NULL, 'pending')
                    """, (leave_id,))

            logger.info("Migration 030 completed successfully.")
            return True
    except Exception as e:
        logger.error("Migration 030 failed: %s", e)
        return False


if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
