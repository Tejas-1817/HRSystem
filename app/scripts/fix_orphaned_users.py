import sys
import os
from werkzeug.security import generate_password_hash

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.models.database import Transaction, get_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_TEMP_PASSWORD = "Welcome@123"

def fix_orphaned_users():
    """
    Identifies employees who do not have a corresponding record in the users table
    and creates login credentials for them.
    """
    logger.info("Starting orphaned user repair check...")
    
    with Transaction() as cursor:
        # Find employees without user accounts
        cursor.execute('''
            SELECT e.name, e.original_name, e.email 
            FROM employee e 
            LEFT JOIN users u ON e.name = u.employee_name 
            WHERE u.id IS NULL
        ''')
        orphans = cursor.fetchall()
        
        if not orphans:
            logger.info("✅ No orphaned employees found. Sync is healthy.")
            return

        logger.info(f"🔍 Found {len(orphans)} orphaned employees. Starting repair...")
        
        hashed_password = generate_password_hash(DEFAULT_TEMP_PASSWORD)
        
        for o in orphans:
            emp_name = o['name']
            orig_name = o['original_name']
            email = o['email']
            
            # Note: We use email as the default username. 
            # If email is missing (shouldn't happen with new logic, but legacy might have it), 
            # fallback to emp_name.
            username = email if email else emp_name
            
            logger.info(f"  Repairing: {emp_name} -> Creating user: {username}")
            
            try:
                cursor.execute("""
                    INSERT INTO users (username, original_name, password, role, employee_name, password_change_required)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """, (username, orig_name, hashed_password, "employee", emp_name))
            except Exception as e:
                logger.error(f"  ❌ Failed to repair {emp_name}: {e}")
                raise # Rollback the whole batch if one fails for safety

    logger.info("✅ All orphaned users have been successfully repaired!")

if __name__ == "__main__":
    fix_orphaned_users()
