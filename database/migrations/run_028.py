"""
Migration 028: Automatic Leave Credit System — employee_leave_credit_log table
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
                  AND TABLE_NAME = 'employee_leave_credit_log'
            """)
            result = cursor.fetchone()
            if result and result['cnt'] > 0:
                logger.info("employee_leave_credit_log already exists — skipping creation.")
            else:
                logger.info("Creating employee_leave_credit_log table...")
                cursor.execute("""
                    CREATE TABLE employee_leave_credit_log (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        employee_name VARCHAR(100) NOT NULL,
                        quarter_number INT NOT NULL,
                        quarter_start DATE NOT NULL,
                        quarter_end DATE NOT NULL,
                        planned_leaves_credited DECIMAL(4,2) NOT NULL DEFAULT 3.00,
                        unplanned_leaves_credited DECIMAL(4,2) NOT NULL DEFAULT 1.00,
                        optional_leaves_credited DECIMAL(4,2) NOT NULL DEFAULT 0.00,
                        credited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        credited_by VARCHAR(50) DEFAULT 'system',
                        status ENUM('SUCCESS','FAILED') NOT NULL DEFAULT 'SUCCESS',
                        error_message TEXT NULL,
                        UNIQUE KEY uniq_emp_quarter (employee_name, quarter_number),
                        INDEX idx_elc_employee (employee_name)
                    )
                """)
                logger.info("employee_leave_credit_log created.")

            # Verify the unique constraint exists
            cursor.execute("""
                SELECT CONSTRAINT_NAME
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'employee_leave_credit_log'
                  AND CONSTRAINT_TYPE = 'UNIQUE'
            """)
            constraints = cursor.fetchall()
            if constraints:
                logger.info(f"Unique constraints present: {[c['CONSTRAINT_NAME'] for c in constraints]}")
            else:
                logger.warning("No unique constraints found — migration may not be correct!")

            logger.info("Migration 028 complete.")
            return True
    except Exception as e:
        logger.error(f"Migration 028 failed: {e}")
        return False


if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
