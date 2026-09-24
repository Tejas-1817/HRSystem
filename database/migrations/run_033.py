"""
Migration 033: Corporate Resignation Form Enhancements
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
            logger.info("Running migration 033 SQL...")
            sql_path = os.path.join(os.path.dirname(__file__), '033_resignation_form_enhancements.sql')
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()

            statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
            for stmt in statements:
                clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith('--')]
                clean_stmt = '\n'.join(clean_lines).strip()
                if clean_stmt:
                    cursor.execute(clean_stmt)

            logger.info("Migration 033 completed successfully.")
            return True
    except Exception as e:
        logger.error(f"Migration 033 failed: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = run_migration()
    if not success:
        sys.exit(1)
