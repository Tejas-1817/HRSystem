"""
Migration 032: Comprehensive Corporate Employee Offboarding & System Admin Role
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
            # 1. Check if system_admin is in users.role ENUM
            cursor.execute("""
                SELECT COLUMN_TYPE 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'users' 
                  AND COLUMN_NAME = 'role'
            """)
            result = cursor.fetchone()
            
            if not result or 'system_admin' not in result['COLUMN_TYPE']:
                logger.info("Adding system_admin to users.role ENUM...")
                cursor.execute("""
                    ALTER TABLE users MODIFY COLUMN role
                    ENUM('admin','hr','manager','employee','team_member','onboarding_candidate','superadmin','accounts','system_admin')
                    NOT NULL DEFAULT 'employee'
                """)
            else:
                logger.info("system_admin role already exists in users.role ENUM.")

            # 2. Run 032_comprehensive_offboarding.sql statements
            logger.info("Running migration 032 SQL...")
            sql_path = os.path.join(os.path.dirname(__file__), '032_comprehensive_offboarding.sql')
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()

            # Execute statements
            statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
            for stmt in statements:
                # filter pure comment lines
                clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith('--')]
                clean_stmt = '\n'.join(clean_lines).strip()
                if clean_stmt:
                    cursor.execute(clean_stmt)

            logger.info("Migration 032 completed successfully.")
            return True
    except Exception as e:
        logger.error(f"Migration 032 failed: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = run_migration()
    if not success:
        sys.exit(1)
