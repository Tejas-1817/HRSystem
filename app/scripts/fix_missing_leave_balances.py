import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.models.database import Transaction, execute_query
from app.services.leave_service import allocate_default_leaves
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_missing_leaves():
    """
    Identifies employees who do not have any records in the leave_balance table
    and allocates default quotas for them.
    """
    logger.info("Starting leave balance repair check...")
    
    # 1. Find employees without leave balances
    query = """
        SELECT e.name 
        FROM employee e 
        LEFT JOIN (
            SELECT employee_name, count(*) as count 
            FROM leave_balance 
            GROUP BY employee_name
        ) lb ON e.name = lb.employee_name 
        WHERE lb.count IS NULL OR lb.count = 0
    """
    missing = execute_query(query)
    
    if not missing:
        logger.info("✅ No employees missing leave balances found.")
        return

    logger.info(f"🔍 Found {len(missing)} employees missing leave balances. Starting repair...")
    
    with Transaction() as cursor:
        for m in missing:
            emp_name = m['name']
            logger.info(f"  Allocating leaves for: {emp_name}")
            try:
                allocate_default_leaves(emp_name, cursor)
            except Exception as e:
                logger.error(f"  ❌ Failed to allocate for {emp_name}: {e}")
                raise # Transaction will rollback

    logger.info("✅ All missing leave balances have been successfully repaired!")

if __name__ == "__main__":
    fix_missing_leaves()
