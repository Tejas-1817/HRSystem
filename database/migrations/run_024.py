"""
Migration 024: Add superadmin role
"""

import sys
import os
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction, execute_query, execute_single

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    try:
        with Transaction() as cursor:
            # Check if superadmin is already in the ENUM
            cursor.execute("""
                SELECT COLUMN_TYPE 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'users' 
                  AND COLUMN_NAME = 'role'
            """)
            result = cursor.fetchone()
            
            if result and 'superadmin' in result['COLUMN_TYPE']:
                logger.info("superadmin role already exists in users.role ENUM. Skipping.")
                return True

            logger.info("Adding superadmin to users.role ENUM...")
            
            sql_path = os.path.join(os.path.dirname(__file__), '024_superadmin_role.sql')
            with open(sql_path, 'r') as f:
                sql = f.read()
                
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)

            logger.info("Migration 024 complete.")
            return True
    except Exception as e:
        logger.error(f"Migration 024 failed: {e}")
        return False

if __name__ == '__main__':
    run_migration()
