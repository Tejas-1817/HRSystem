"""
Migration 029: Superadmin Permissions Sync
Populate/ensure all permissions are granted to the superadmin role.
"""

import sys
import os
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction, execute_query
from app.api.middleware.auth import refresh_permissions_cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    try:
        with Transaction() as cursor:
            # 1. Fetch all permissions from the permissions table
            cursor.execute("SELECT id, permission_key FROM permissions")
            permissions = cursor.fetchall()
            logger.info("Found %d permissions to sync for superadmin.", len(permissions))

            # 2. Insert or update role_permissions for superadmin
            count = 0
            for perm in permissions:
                perm_id = perm['id']
                cursor.execute("""
                    INSERT INTO role_permissions (role, permission_id, is_granted)
                    VALUES ('superadmin', %s, TRUE)
                    ON DUPLICATE KEY UPDATE is_granted = TRUE
                """, (perm_id,))
                count += 1

            logger.info("Successfully synced %d permissions for role 'superadmin'.", count)
            return True
    except Exception as e:
        logger.error("Migration 029 failed: %s", e, exc_info=True)
        return False

if __name__ == '__main__':
    success = run_migration()
    if success:
        refresh_permissions_cache()
        print("Migration 029 completed successfully.")
    else:
        print("Migration 029 failed.")
        sys.exit(1)
