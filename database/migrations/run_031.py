"""
Migration 031: Seed and Grant All Dynamic Permissions to Super Admin Role
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
            logger.info("Executing 031_superadmin_permissions.sql...")
            sql_path = os.path.join(os.path.dirname(__file__), '031_superadmin_permissions.sql')
            with open(sql_path, 'r') as f:
                sql = f.read()

            for statement in sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)

            logger.info("Super Admin permissions seeded successfully.")

        refresh_permissions_cache()
        logger.info("Migration 031 complete.")
        return True
    except Exception as e:
        logger.error(f"Migration 031 failed: {e}")
        return False


if __name__ == '__main__':
    run_migration()
