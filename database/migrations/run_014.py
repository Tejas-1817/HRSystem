import os
import sys

# Add the HRSystem root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import execute_query, Transaction
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Runs the 014 migration to create the timesheet_edit_history table."""
    migration_file = os.path.join(os.path.dirname(__file__), '014_timesheet_edit_history.sql')
    
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    # Split by statements
    statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
    
    logger.info("Executing Migration 014: timesheet_edit_history...")
    try:
        with Transaction() as conn:
            with conn.cursor() as cursor:
                for stmt in statements:
                    if not stmt.startswith('--'):
                        logger.info(f"Executing: {stmt[:50]}...")
                        cursor.execute(stmt)
        logger.info("✅ Migration 014 completed successfully.")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
