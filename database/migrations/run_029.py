"""
Migration 029: Timesheet manager assignment, employee role sync, and 2026 holiday timetable
"""

import sys
import os
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction, execute_query

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    try:
        with Transaction() as cursor:
            # 1. Check & Add manager_name column to timesheets table
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'timesheets' 
                  AND COLUMN_NAME = 'manager_name'
            """)
            col_exists = cursor.fetchone()
            if not col_exists or col_exists['count'] == 0:
                logger.info("Adding manager_name column to timesheets table...")
                cursor.execute("ALTER TABLE timesheets ADD COLUMN manager_name VARCHAR(100) DEFAULT NULL AFTER start_date")
            else:
                logger.info("manager_name column already exists on timesheets table.")

            # 2. Ensure role column on employee table is VARCHAR(50) to support all system roles
            logger.info("Ensuring employee.role column is VARCHAR(50)...")
            cursor.execute("ALTER TABLE employee MODIFY COLUMN role VARCHAR(50) DEFAULT 'employee'")

            # 3. Sync employee table roles from users table
            logger.info("Syncing employee roles with users table...")
            cursor.execute("""
                UPDATE employee e
                JOIN users u ON e.name = u.employee_name
                SET e.role = u.role
                WHERE u.role IS NOT NULL
            """)

            # 4. Clean & re-seed 2026 holiday timetable
            logger.info("Updating 2026 organization holiday timetable...")
            cursor.execute("DELETE FROM holidays WHERE YEAR(date) = 2026")
            
            holidays = [
                ('Republic Day', '2026-01-26', 'public', 'National Holiday - Republic Day'),
                ('May Day & Maharashtra Day', '2026-05-01', 'public', 'Labour Day and Maharashtra Formation Day'),
                ('Bakrid', '2026-05-28', 'public', 'Eid ul-Adha'),
                ('Independence Day', '2026-08-15', 'public', 'National Holiday - Independence Day'),
                ('Ganesh Chaturthi', '2026-09-14', 'public', 'Ganesh Utsav celebration'),
                ('Gandhi Jayanti', '2026-10-02', 'public', 'National Holiday - Mahatma Gandhi Birthday'),
                ('Diwali', '2026-11-09', 'public', 'Festival of Lights - Deepavali'),
                ('Christmas', '2026-12-25', 'public', 'Christmas Day celebration'),
                ('New Years', '2026-01-01', 'optional', 'New Year Day'),
                ('Makara Sankranthi', '2026-01-15', 'optional', 'Harvest Festival - Pongal / Sankranthi'),
                ('Holi', '2026-03-03', 'optional', 'Festival of Colors'),
                ('Ugadi/Gudi Padwa', '2026-03-19', 'optional', 'New Year Festival - Ugadi / Gudi Padwa'),
                ('Good Friday', '2026-04-03', 'optional', 'Good Friday Christian observance'),
                ('Dasara', '2026-10-20', 'optional', 'Vijayadashami / Dussehra celebration')
            ]
            
            cursor.executemany("""
                INSERT INTO holidays (name, date, type, description)
                VALUES (%s, %s, %s, %s)
            """, holidays)

            logger.info("Migration 028 complete.")
            return True
    except Exception as e:
        logger.error(f"Migration 028 failed: {e}")
        return False

if __name__ == '__main__':
    run_migration()
