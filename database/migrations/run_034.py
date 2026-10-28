"""
Migration 034: Timesheet Access Control Permission Setup & Seed
"""

import sys
import os
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction
from app.api.middleware.auth import refresh_permissions_cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def run_migration():
    try:
        with Transaction() as cursor:
            logger.info("Executing 034_timesheet_access_permission.sql...")
            sql_path = os.path.join(os.path.dirname(__file__), '034_timesheet_access_permission.sql')
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()

            statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
            for stmt in statements:
                clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith('--')]
                clean_stmt = '\n'.join(clean_lines).strip()
                if clean_stmt:
                    cursor.execute(clean_stmt)

            logger.info("Timesheet access permission seeded successfully.")

        refresh_permissions_cache()
        logger.info("Migration 034 complete.")
        return True
    except Exception as e:
        logger.error(f"Migration 034 failed: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = run_migration()
    if not success:
        sys.exit(1)
