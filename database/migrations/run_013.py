"""
Migration Runner 013: Fix Name Prefix Corruption
─────────────────────────────────────────────────
Safely detects and repairs corrupted (double-prefixed) employee names
across all linked database tables.

Usage:
    # Dry-run (detection only, no modifications):
    python database/migrations/run_013.py --dry-run

    # Execute migration:
    python database/migrations/run_013.py

    # Execute with full backup report:
    python database/migrations/run_013.py --verbose
"""

import sys
import os
import re
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.models.database import Transaction, execute_query, execute_single
from app.utils.display_name_service import strip_all_prefixes, ROLE_PREFIX_MAP

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Pattern to detect double-prefixed names (e.g., A_A_Santosh, M_T_Kartik)
DOUBLE_PREFIX_PATTERN = re.compile(
    r'^(ADMIN_|HR_|TM_|A_|H_|M_|T_){2,}',
    re.IGNORECASE
)

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


def scan_corrupted_names(cursor):
    """
    Scan all tables for names with double (or more) role prefixes.
    Returns a dict: { old_name: { 'tables': [(table, col), ...], 'clean_name': str } }
    """
    corrupted = {}
    
    for table, col in NAME_COLUMNS:
        try:
            cursor.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL")
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning(f"  ⚠️  Skipping {table}.{col}: {e}")
            continue

        for row in rows:
            name = row[col] if isinstance(row, dict) else row[0]
            if name and DOUBLE_PREFIX_PATTERN.match(name):
                if name not in corrupted:
                    clean = strip_all_prefixes(name)
                    corrupted[name] = {
                        'clean_name': clean,
                        'tables': [],
                    }
                corrupted[name]['tables'].append((table, col))

    return corrupted


def scan_missing_original_names(cursor):
    """Scan for employee/users records missing original_name."""
    missing = []
    
    cursor.execute("SELECT id, name, original_name FROM employee WHERE original_name IS NULL OR original_name = ''")
    for row in cursor.fetchall():
        missing.append({
            'table': 'employee',
            'id': row['id'],
            'name': row['name'],
            'derived_original': strip_all_prefixes(row['name'])
        })

    cursor.execute("SELECT id, employee_name, original_name FROM users WHERE original_name IS NULL OR original_name = ''")
    for row in cursor.fetchall():
        missing.append({
            'table': 'users',
            'id': row['id'],
            'name': row['employee_name'],
            'derived_original': strip_all_prefixes(row['employee_name'])
        })

    return missing


def fix_double_prefixed_names(cursor, corrupted, dry_run=False):
    """
    Fix double-prefixed names by:
    1. Deriving the correct single-prefixed name from the employee's current role
    2. Cascading the rename across all linked tables
    """
    fixed_count = 0

    for old_name, info in corrupted.items():
        clean_name = info['clean_name']
        
        # Look up the user's current role to generate the correct single prefix
        cursor.execute(
            "SELECT role FROM users WHERE employee_name = %s LIMIT 1",
            (old_name,)
        )
        user_row = cursor.fetchone()
        
        if user_row:
            role = user_row['role'] if isinstance(user_row, dict) else user_row[0]
        else:
            # Guess role from the prefix if user record not found
            role = 'employee'
            for r, p in ROLE_PREFIX_MAP.items():
                if old_name.upper().startswith(p + '_'):
                    role = r
                    break

        # Generate correct single-prefixed name
        prefix = ROLE_PREFIX_MAP.get(role, 'TM')
        correct_name = f"{prefix}_{clean_name}"
        
        if correct_name == old_name:
            logger.info(f"  ✅ {old_name} — already correct, skipping")
            continue

        logger.info(f"  {'[DRY-RUN] ' if dry_run else ''}🔧 {old_name} → {correct_name} (role: {role})")

        if not dry_run:
            # Cascade rename across all tables
            for table, col in info['tables']:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {col} = %s WHERE {col} = %s",
                        (correct_name, old_name)
                    )
                    affected = cursor.rowcount
                    if affected > 0:
                        logger.info(f"    Updated {affected} row(s) in {table}.{col}")
                except Exception as e:
                    logger.error(f"    ❌ Failed to update {table}.{col}: {e}")

        fixed_count += 1

    return fixed_count


def fix_missing_original_names(cursor, missing, dry_run=False):
    """Populate NULL original_name fields by deriving from the prefixed name."""
    fixed_count = 0

    for record in missing:
        derived = record['derived_original']
        table = record['table']
        record_id = record['id']

        logger.info(
            f"  {'[DRY-RUN] ' if dry_run else ''}"
            f"📝 {table} ID {record_id}: original_name = '{derived}' "
            f"(from '{record['name']}')"
        )

        if not dry_run:
            cursor.execute(
                f"UPDATE {table} SET original_name = %s WHERE id = %s",
                (derived, record_id)
            )

        fixed_count += 1

    return fixed_count


def run_migration(dry_run=False, verbose=False):
    """Main migration entry point."""
    mode = "DRY-RUN" if dry_run else "LIVE"
    logger.info(f"═══════════════════════════════════════════════════")
    logger.info(f"  Migration 013: Fix Name Prefix Corruption [{mode}]")
    logger.info(f"═══════════════════════════════════════════════════")

    with Transaction() as cursor:
        # ── Phase 1: Scan for corrupted names ─────────────────────────
        logger.info("\n📊 Phase 1: Scanning for double-prefixed names...")
        corrupted = scan_corrupted_names(cursor)

        if corrupted:
            logger.info(f"  Found {len(corrupted)} corrupted name(s):")
            for name, info in corrupted.items():
                tables_str = ', '.join(f"{t}.{c}" for t, c in info['tables'])
                logger.info(f"    ❌ '{name}' → clean: '{info['clean_name']}' (in: {tables_str})")
        else:
            logger.info("  ✅ No double-prefixed names found.")

        # ── Phase 2: Scan for missing original_names ─────────────────
        logger.info("\n📊 Phase 2: Scanning for missing original_name values...")
        missing = scan_missing_original_names(cursor)

        if missing:
            logger.info(f"  Found {len(missing)} record(s) with missing original_name.")
        else:
            logger.info("  ✅ All records have original_name populated.")

        # ── Phase 3: Fix corrupted names ─────────────────────────────
        if corrupted:
            logger.info(f"\n🔧 Phase 3: Fixing double-prefixed names...")
            fixed_names = fix_double_prefixed_names(cursor, corrupted, dry_run)
            logger.info(f"  {'Would fix' if dry_run else 'Fixed'} {fixed_names} corrupted name(s).")
        else:
            fixed_names = 0

        # ── Phase 4: Fix missing original_names ──────────────────────
        if missing:
            logger.info(f"\n📝 Phase 4: Populating missing original_name values...")
            fixed_missing = fix_missing_original_names(cursor, missing, dry_run)
            logger.info(f"  {'Would fix' if dry_run else 'Fixed'} {fixed_missing} missing original_name(s).")
        else:
            fixed_missing = 0

        # ── Phase 5: Run SQL migration for remaining cleanup ─────────
        if not dry_run:
            logger.info("\n🗄️  Phase 5: Running SQL cleanup (original_name normalization)...")
            sql_path = os.path.join(os.path.dirname(__file__), '013_fix_name_prefixes.sql')
            if os.path.exists(sql_path):
                with open(sql_path, 'r') as f:
                    sql_content = f.read()

                # Execute each statement separately (skip comments and empty lines)
                for statement in sql_content.split(';'):
                    stmt = statement.strip()
                    if stmt and not stmt.startswith('--') and not stmt.startswith('USE '):
                        try:
                            cursor.execute(stmt)
                            logger.info(f"    ✅ Executed SQL statement ({cursor.rowcount} rows affected)")
                        except Exception as e:
                            logger.warning(f"    ⚠️  SQL statement skipped: {e}")
            else:
                logger.warning(f"  SQL file not found: {sql_path}")

        # ── Summary ──────────────────────────────────────────────────
        logger.info("\n" + "═" * 55)
        logger.info(f"  Migration 013 Summary [{mode}]")
        logger.info(f"  Double-prefixed names {'detected' if dry_run else 'fixed'}: {fixed_names}")
        logger.info(f"  Missing original_names {'detected' if dry_run else 'fixed'}: {fixed_missing}")
        logger.info("═" * 55)

        if dry_run:
            logger.info("\n💡 This was a DRY-RUN. No data was modified.")
            logger.info("   To apply changes, run: python database/migrations/run_013.py")
            # Rollback to prevent any accidental commits
            raise Exception("DRY-RUN: Rolling back transaction (no data modified)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration 013: Fix Name Prefix Corruption")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report only, don't modify data")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        run_migration(dry_run=args.dry_run, verbose=args.verbose)
    except Exception as e:
        if "DRY-RUN" in str(e):
            pass  # Expected for dry-run
        else:
            logger.error(f"Migration failed: {e}")
            sys.exit(1)
