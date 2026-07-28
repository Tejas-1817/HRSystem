"""
Migration 027: Offboarding feature schema and accounts role
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
            # Check if accounts is already in the ENUM
            cursor.execute("""
                SELECT COLUMN_TYPE 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'users' 
                  AND COLUMN_NAME = 'role'
            """)
            result = cursor.fetchone()
            
            if not result or 'accounts' not in result['COLUMN_TYPE']:
                logger.info("Adding accounts to users.role ENUM...")
                cursor.execute("""
                    ALTER TABLE users MODIFY COLUMN role
                    ENUM('admin','hr','manager','employee','team_member','onboarding_candidate','superadmin','accounts')
                    NOT NULL DEFAULT 'employee'
                """)
            else:
                logger.info("accounts role already exists in users.role ENUM.")

            logger.info("Creating offboarding tables...")
            sql_path = os.path.join(os.path.dirname(__file__), '027_offboarding.sql')
            with open(sql_path, 'r') as f:
                sql = f.read()
                
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    cursor.execute(statement)

            logger.info("Migration 027 complete.")
            return True
    except Exception as e:
        logger.error(f"Migration 027 failed: {e}")
        return False

if __name__ == '__main__':
    run_migration()
