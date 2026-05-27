import sys
import os
import re
import argparse
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction, execute_query, execute_single
from app.utils.display_name_service import strip_all_prefixes

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# All tables and columns that store employee names as string FKs
NAME_COLUMNS = [
    ("employee", "name"),
    ("users", "employee_name"),
    ("timesheets", "employee_name"),
    ("timesheets", "manager_name"),
    ("projects", "manager_name"),
    ("project_assignments", "employee_name"),
    ("project_assignments", "assigned_by"),
    ("leaves", "employee_name"),
    ("leave_balance", "employee_name"),
    ("attendance", "employee_name"),
    ("notifications", "employee_name"),
    ("payslips", "employee_name"),
    ("employee_documents", "employee_name"),
    ("employee_documents", "verified_by"),
    ("bank_details", "employee_name"),
    ("helpdesk_tickets", "employee_name"),
    ("helpdesk_tickets", "assigned_to"),
    ("reimbursements", "employee_name"),
    ("policies", "updated_by"),
]

def scan_prefixed_names(cursor):
    """
    Scan all tables for names that have any prefix.
    Returns a dict mapping old_name to a dictionary of clean_name and tables.
    """
    prefixed = {}
    
    for table, col in NAME_COLUMNS:
        try:
            cursor.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL")
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning(f"  ⚠️  Skipping {table}.{col}: {e}")
            continue

        for row in rows:
            name = row[col] if isinstance(row, dict) else row[0]
            if name:
                clean = strip_all_prefixes(name)
                # If stripping prefixes changed the name, it was prefixed
                if clean != name:
                    if name not in prefixed:
                        prefixed[name] = {
                            'clean_name': clean,
                            'tables': [],
                        }
                    prefixed[name]['tables'].append((table, col))

    return prefixed

def check_clean_name_availability(clean_name, cursor, mapping):
    """
    Ensure the clean_name is globally unique to avoid PK/FK conflicts.
    Since we are mapping old prefixed names to clean names, we must not map two different users to the same clean name.
    """
    # Is it already in the mapping targets?
    existing_targets = [info['new_target'] for info in mapping.values() if 'new_target' in info]
    
    # Is it already in the DB as a clean name?
    cursor.execute("SELECT employee_name FROM users WHERE employee_name = %s", (clean_name,))
    in_db = cursor.fetchone() is not None

    if clean_name not in existing_targets and not in_db:
        return clean_name
        
    i = 1
    while True:
        candidate = f"{clean_name}_{i}"
        if candidate not in existing_targets:
            cursor.execute("SELECT employee_name FROM users WHERE employee_name = %s", (candidate,))
            if cursor.fetchone() is None:
                return candidate
        i += 1


def generate_migration_mapping(cursor, prefixed_names):
    """
    Generate target names avoiding collisions.
    """
    mapping = {}
    for old_name, info in prefixed_names.items():
        clean_name = info['clean_name']
        target = check_clean_name_availability(clean_name, cursor, mapping)
        mapping[old_name] = {
            'tables': info['tables'],
            'new_target': target
        }
    return mapping


def execute_renames(cursor, mapping, dry_run=False):
    """
    Cascade rename across all linked tables.
    """
    fixed_count = 0

    for old_name, info in mapping.items():
        target_name = info['new_target']
        logger.info(f"  {'[DRY-RUN] ' if dry_run else ''}🔧 {old_name} → {target_name}")

        if not dry_run:
            # First, update tables that are NOT the primary key definition tables.
            # We must handle FK constraints carefully. If ON UPDATE CASCADE is set, updating `users` or `employee` might automatically update the others.
            # However, because MySQL FKs might be partially set or missing, we update explicitly.
            # We temporarily disable foreign key checks to allow arbitrary update order.
            cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
            
            for table, col in info['tables']:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {col} = %s WHERE {col} = %s",
                        (target_name, old_name)
                    )
                    affected = cursor.rowcount
                    if affected > 0:
                        logger.info(f"    Updated {affected} row(s) in {table}.{col}")
                except Exception as e:
                    logger.error(f"    ❌ Failed to update {table}.{col}: {e}")
            
            cursor.execute("SET FOREIGN_KEY_CHECKS=1;")

        fixed_count += 1

    return fixed_count


def run_migration(dry_run=False):
    mode = "DRY-RUN" if dry_run else "LIVE"
    logger.info(f"═══════════════════════════════════════════════════")
    logger.info(f"  Migration 015: Clean Architecture [{mode}]")
    logger.info(f"═══════════════════════════════════════════════════")

    with Transaction() as cursor:
        logger.info("\n📊 Phase 1: Scanning for prefixed names...")
        prefixed = scan_prefixed_names(cursor)

        if not prefixed:
            logger.info("  ✅ No prefixed names found.")
        else:
            logger.info(f"  Found {len(prefixed)} prefixed name(s).")
            mapping = generate_migration_mapping(cursor, prefixed)
            
            logger.info(f"\n🔧 Phase 2: Generating and applying rewrite mapping...")
            fixed_names = execute_renames(cursor, mapping, dry_run)
            logger.info(f"  {'Would fix' if dry_run else 'Fixed'} {fixed_names} prefixed name(s).")
            
        if not dry_run:
            logger.info("\n🗄️  Phase 3: Running SQL cleanup (dropping original_name columns)...")
            sql_path = os.path.join(os.path.dirname(__file__), '015_clean_identity_architecture.sql')
            if os.path.exists(sql_path):
                with open(sql_path, 'r') as f:
                    sql_content = f.read()

                for statement in sql_content.split(';'):
                    stmt = statement.strip()
                    if stmt and not stmt.startswith('--') and not stmt.startswith('USE '):
                        try:
                            # Handle DROP COLUMN IF EXISTS safely if using older MySQL
                            if 'DROP COLUMN IF EXISTS' in stmt:
                                # We'll just catch the error if column doesn't exist
                                stmt = stmt.replace('IF EXISTS', '')
                                
                            cursor.execute(stmt)
                            logger.info(f"    ✅ Executed SQL statement")
                        except Exception as e:
                            if 'check that column/key exists' not in str(e):
                                logger.warning(f"    ⚠️  SQL statement skipped: {e}")
            else:
                logger.warning(f"  SQL file not found: {sql_path}")

        if dry_run:
            logger.info("\n💡 This was a DRY-RUN. No data was modified.")
            raise Exception("DRY-RUN: Rolling back transaction")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration 015: Clean Architecture")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report only")
    args = parser.parse_args()
    
    try:
        run_migration(dry_run=args.dry_run)
    except Exception as e:
        if "DRY-RUN" in str(e):
            pass
        else:
            logger.error(f"Migration failed: {e}")
            sys.exit(1)
