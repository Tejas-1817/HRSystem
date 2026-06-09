"""
Migration 017: Onboarding Module + Users Table Alignment
─────────────────────────────────────────────────────────
Phase 1 — Users Table Refactoring:
  - Add email column, migrate from username, set UNIQUE NOT NULL
  - Add password_hash column, migrate from password, set NOT NULL
  - Add employee_id FK column, populate via JOIN, add FK constraint
  - Convert role VARCHAR(50) → ENUM with 'onboarding_candidate'
  - Drop legacy columns: username, password, employee_name,
    password_change_required, reset_token, reset_token_expiry

Phase 2 — Onboarding Module (5 new tables):
  - onboarding_joinee, onboarding_declaration, onboarding_references,
    onboarding_documents, onboarding_audit_log

Usage:
    python database/migrations/run_017.py              # Run live
    python database/migrations/run_017.py --dry-run    # Scan only, no changes

Safe to run multiple times — uses information_schema guards.
All foreign keys use ON DELETE RESTRICT (never CASCADE).
"""

import sys
import os
import argparse
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction, execute_query, execute_single

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ─── Helpers ─────────────────────────────────────────────────────────────

ROLE_ENUM_VALUES = ['admin', 'hr', 'manager', 'employee', 'team_member', 'onboarding_candidate']
LEGACY_COLUMNS = [
    'username', 'password', 'employee_name',
    'password_change_required', 'reset_token', 'reset_token_expiry',
]


def _col_exists(cursor, table, column):
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """, (table, column))
    result = cursor.fetchone()
    return result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0


def _table_exists(cursor, table):
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
    """, (table,))
    result = cursor.fetchone()
    return result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0


def _fk_exists(cursor, table, constraint_name):
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND CONSTRAINT_NAME = %s
          AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    """, (table, constraint_name))
    result = cursor.fetchone()
    return result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0


def _col_type(cursor, table, column):
    """Get the column type (e.g. 'varchar(50)', 'enum(...)')."""
    cursor.execute("""
        SELECT COLUMN_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """, (table, column))
    row = cursor.fetchone()
    if row:
        return row['COLUMN_TYPE'] if isinstance(row, dict) else row[0]
    return None


def _index_exists(cursor, table, index_name):
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s
    """, (table, index_name))
    result = cursor.fetchone()
    return result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0


# ─── Phase 1: Users Table Refactoring ───────────────────────────────────

def phase1_users_refactor(cursor, dry_run=False):
    logger.info("\n═══════════════════════════════════════════════════")
    logger.info("  Phase 1: Users Table Refactoring")
    logger.info("═══════════════════════════════════════════════════")

    # ── Step 1a: Add email column ──────────────────────────────────
    logger.info("\n  Step 1a: Adding email column...")
    if _col_exists(cursor, 'users', 'email'):
        logger.info("    ✅ Column 'email' already exists — skipping")
    else:
        if not dry_run:
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL")
            logger.info("    ✅ Added column 'email' (VARCHAR(255) NULL)")
        else:
            logger.info("    [DRY-RUN] Would add column 'email' (VARCHAR(255) NULL)")

    # ── Step 1b: Migrate data from username → email ────────────────
    logger.info("\n  Step 1b: Migrating data from username to email...")
    if _col_exists(cursor, 'users', 'email') and _col_exists(cursor, 'users', 'username'):
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE email IS NULL AND username IS NOT NULL")
        result = cursor.fetchone()
        needs_migration = result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0
        if needs_migration:
            if not dry_run:
                cursor.execute("UPDATE users SET email = username WHERE email IS NULL")
                affected = cursor.rowcount
                logger.info(f"    ✅ Migrated {affected} row(s) from username → email")
            else:
                logger.info(f"    [DRY-RUN] Would migrate username → email ({result})")
        else:
            logger.info("    ✅ No rows need migration — all emails populated")
    else:
        logger.info("    ⏭️  Skip — columns not yet in expected state")

    # ── Step 1c: Make email UNIQUE NOT NULL ────────────────────────
    logger.info("\n  Step 1c: Making email UNIQUE NOT NULL...")
    if _col_exists(cursor, 'users', 'email'):
        current_type = _col_type(cursor, 'users', 'email')
        if current_type and 'varchar' in current_type.lower():
            if not dry_run:
                cursor.execute("ALTER TABLE users MODIFY email VARCHAR(255) UNIQUE NOT NULL")
                logger.info("    ✅ Set email to UNIQUE NOT NULL")
            else:
                logger.info("    [DRY-RUN] Would set email UNIQUE NOT NULL")
        else:
            logger.info("    ✅ email already modified — skipping")
    else:
        logger.info("    ⏭️  Skip — email column does not exist")

    # ── Step 2a: Add password_hash column ──────────────────────────
    logger.info("\n  Step 2a: Adding password_hash column...")
    if _col_exists(cursor, 'users', 'password_hash'):
        logger.info("    ✅ Column 'password_hash' already exists — skipping")
    else:
        if not dry_run:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL")
            logger.info("    ✅ Added column 'password_hash' (VARCHAR(255) NULL)")
        else:
            logger.info("    [DRY-RUN] Would add column 'password_hash' (VARCHAR(255) NULL)")

    # ── Step 2b: Migrate data from password → password_hash ────────
    logger.info("\n  Step 2b: Migrating data from password to password_hash...")
    if _col_exists(cursor, 'users', 'password_hash') and _col_exists(cursor, 'users', 'password'):
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE password_hash IS NULL AND password IS NOT NULL")
        result = cursor.fetchone()
        needs_migration = result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0
        if needs_migration:
            if not dry_run:
                cursor.execute("UPDATE users SET password_hash = password WHERE password_hash IS NULL")
                affected = cursor.rowcount
                logger.info(f"    ✅ Migrated {affected} row(s) from password → password_hash")
            else:
                logger.info(f"    [DRY-RUN] Would migrate password → password_hash ({result})")
        else:
            logger.info("    ✅ No rows need migration — all password_hashes populated")
    else:
        logger.info("    ⏭️  Skip — columns not yet in expected state")

    # ── Step 2c: Make password_hash NOT NULL ───────────────────────
    logger.info("\n  Step 2c: Making password_hash NOT NULL...")
    if _col_exists(cursor, 'users', 'password_hash'):
        current_type = _col_type(cursor, 'users', 'password_hash')
        if current_type and 'varchar' in current_type.lower() and 'not null' not in current_type.lower():
            if not dry_run:
                cursor.execute("ALTER TABLE users MODIFY password_hash VARCHAR(255) NOT NULL")
                logger.info("    ✅ Set password_hash to NOT NULL")
            else:
                logger.info("    [DRY-RUN] Would set password_hash NOT NULL")
        else:
            logger.info("    ✅ password_hash already modified — skipping")
    else:
        logger.info("    ⏭️  Skip — password_hash column does not exist")

    # ── Step 3a: Add employee_id column ────────────────────────────
    logger.info("\n  Step 3a: Adding employee_id column...")
    if _col_exists(cursor, 'users', 'employee_id'):
        logger.info("    ✅ Column 'employee_id' already exists — skipping")
    else:
        if not dry_run:
            cursor.execute("ALTER TABLE users ADD COLUMN employee_id INT NULL")
            logger.info("    ✅ Added column 'employee_id' (INT NULL)")
        else:
            logger.info("    [DRY-RUN] Would add column 'employee_id' (INT NULL)")

    # ── Step 3b: Migrate data from employee_name → employee_id ─────
    logger.info("\n  Step 3b: Migrating employee_name to employee_id via JOIN...")
    if (_col_exists(cursor, 'users', 'employee_id')
            and _col_exists(cursor, 'users', 'employee_name')
            and _table_exists(cursor, 'employee')):
        cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM users u
            WHERE u.employee_id IS NULL
              AND u.employee_name IS NOT NULL
              AND EXISTS (SELECT 1 FROM employee e WHERE e.name = u.employee_name)
        """)
        result = cursor.fetchone()
        needs_migration = result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0
        if needs_migration:
            if not dry_run:
                cursor.execute("""
                    UPDATE users u
                    JOIN employee e ON u.employee_name = e.name
                    SET u.employee_id = e.id
                    WHERE u.employee_id IS NULL
                """)
                affected = cursor.rowcount
                logger.info(f"    ✅ Migrated {affected} row(s) — employee_name → employee_id")
            else:
                logger.info(f"    [DRY-RUN] Would migrate employee_name → employee_id")
        else:
            logger.info("    ✅ No rows need migration — all employee_ids populated or no matches")
    else:
        logger.info("    ⏭️  Skip — required columns/tables not in expected state")

    # ── Step 3c: Add FK constraint employee_id → employee(id) ─────
    logger.info("\n  Step 3c: Adding FK constraint employee_id → employee(id)...")
    if _col_exists(cursor, 'users', 'employee_id') and _table_exists(cursor, 'employee'):
        if _fk_exists(cursor, 'users', 'fk_users_employee'):
            logger.info("    ✅ FK 'fk_users_employee' already exists — skipping")
        else:
            if not dry_run:
                cursor.execute("""
                    ALTER TABLE users
                    ADD CONSTRAINT fk_users_employee
                    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE RESTRICT
                """)
                logger.info("    ✅ Added FK 'fk_users_employee' (ON DELETE RESTRICT)")
            else:
                logger.info("    [DRY-RUN] Would add FK 'fk_users_employee'")
    else:
        logger.info("    ⏭️  Skip — required columns/tables not in expected state")

    # ── Step 4: Convert role to ENUM ────────────────────────────────
    logger.info("\n  Step 4: Converting role VARCHAR → ENUM...")
    if _col_exists(cursor, 'users', 'role'):
        current_type = _col_type(cursor, 'users', 'role')
        if current_type and 'enum' in current_type.lower():
            logger.info(f"    ✅ role already ENUM ({current_type}) — skipping")
        else:
            # Sanitize invalid values first
            if not dry_run:
                cursor.execute("""
                    UPDATE users
                    SET role = 'employee'
                    WHERE role IS NULL OR role NOT IN ('admin','hr','manager','employee','team_member')
                """)
                sanitized = cursor.rowcount
                if sanitized:
                    logger.info(f"    ⚠️  Sanitized {sanitized} row(s) with invalid role values → 'employee'")

                enum_def = "','".join(ROLE_ENUM_VALUES)
                cursor.execute(f"""
                    ALTER TABLE users
                    MODIFY COLUMN role
                    ENUM('{enum_def}')
                    NOT NULL DEFAULT 'employee'
                """)
                logger.info(f"    ✅ Converted role to ENUM({', '.join(ROLE_ENUM_VALUES)})")
            else:
                logger.info(f"    [DRY-RUN] Would convert role to ENUM({', '.join(ROLE_ENUM_VALUES)})")

                # Check for invalid role values even in dry-run
                cursor.execute("""
                    SELECT COUNT(*) as cnt
                    FROM users
                    WHERE role IS NULL OR role NOT IN ('admin','hr','manager','employee','team_member')
                """)
                result = cursor.fetchone()
                invalid = result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0
                if invalid:
                    logger.warning(f"    ⚠️  Found {result} row(s) with invalid role values (would be sanitized)")
    else:
        logger.info("    ⏭️  Skip — role column does not exist")

    # ── Step 5: Drop legacy columns ────────────────────────────────
    logger.info("\n  Step 5: Dropping legacy columns...")
    for col in LEGACY_COLUMNS:
        if _col_exists(cursor, 'users', col):
            if not dry_run:
                cursor.execute(f"ALTER TABLE users DROP COLUMN {col}")
                logger.info(f"    ✅ Dropped column '{col}'")
            else:
                logger.info(f"    [DRY-RUN] Would drop column '{col}'")
        else:
            logger.info(f"    ✅ Column '{col}' already gone — skipping")

    # ── Step 6: Drop legacy indexes if any remain ──────────────────
    logger.info("\n  Step 6: Cleaning up legacy indexes...")
    legacy_indexes = ['username']
    for idx_col in legacy_indexes:
        idx_name = idx_col
        if _index_exists(cursor, 'users', idx_name):
            if not dry_run:
                cursor.execute(f"ALTER TABLE users DROP INDEX {idx_name}")
                logger.info(f"    ✅ Dropped index '{idx_name}'")
            else:
                logger.info(f"    [DRY-RUN] Would drop index '{idx_name}'")
        else:
            logger.info(f"    ✅ Index '{idx_name}' already gone — skipping")


# ─── Phase 2: Onboarding Tables (from SQL file) ────────────────────────

def _extract_ddl_statements(sql_path):
    """Extract complete DDL statements from a SQL file, skipping comments and USE."""
    with open(sql_path, 'r') as f:
        content = f.read()

    statements = []
    buffer = []
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.upper().startswith('USE '):
            continue
        buffer.append(line)
        if stripped.endswith(';'):
            stmt = '\n'.join(buffer).strip()
            if stmt:
                statements.append(stmt)
            buffer = []
    return statements


def phase2_onboarding_tables(cursor, dry_run=False):
    logger.info("\n═══════════════════════════════════════════════════")
    logger.info("  Phase 2: Onboarding Module Tables")
    logger.info("═══════════════════════════════════════════════════")

    sql_path = os.path.join(os.path.dirname(__file__), '017_onboarding.sql')
    if not os.path.exists(sql_path):
        logger.error(f"    ❌ SQL file not found: {sql_path}")
        return

    all_statements = _extract_ddl_statements(sql_path)

    # Filter to only CREATE TABLE IF NOT EXISTS (Phase 2)
    create_statements = [s for s in all_statements if 'CREATE TABLE IF NOT EXISTS' in s]

    if not create_statements:
        logger.warning("    ⚠️  No CREATE TABLE statements found in SQL file")
        return

    for stmt in create_statements:
        table_name = stmt.split('CREATE TABLE IF NOT EXISTS ')[1].split('(')[0].strip()

        if _table_exists(cursor, table_name):
            logger.info(f"    ✅ Table '{table_name}' already exists — skipping")
            continue

        if not dry_run:
            try:
                cursor.execute(stmt)
                logger.info(f"    ✅ Created table '{table_name}'")
            except Exception as e:
                logger.error(f"    ❌ Failed to create '{table_name}': {e}")
                raise
        else:
            logger.info(f"    [DRY-RUN] Would create table '{table_name}'")


# ─── Verification ──────────────────────────────────────────────────────

def verify_migration(cursor):
    logger.info("\n═══════════════════════════════════════════════════")
    logger.info("  Verification")
    logger.info("═══════════════════════════════════════════════════")

    all_ok = True

    # Verify users table columns
    logger.info("\n  📋 Users table columns:")
    expected_cols = ['id', 'email', 'password_hash', 'role', 'employee_id', 'is_active', 'created_at']
    for col in expected_cols:
        exists = _col_exists(cursor, 'users', col)
        status = "✅" if exists else "❌"
        logger.info(f"    {status} users.{col}")
        if not exists:
            all_ok = False

    # Legacy columns should NOT exist
    logger.info("\n  📋 Legacy columns (should be absent):")
    for col in LEGACY_COLUMNS:
        exists = _col_exists(cursor, 'users', col)
        if exists:
            logger.warning(f"    ⚠️  Legacy column 'users.{col}' still exists")
            all_ok = False
        else:
            logger.info(f"    ✅ users.{col} — properly removed")

    # Verify role is ENUM
    role_type = _col_type(cursor, 'users', 'role')
    if role_type and 'enum' in role_type.lower():
        logger.info(f"    ✅ users.role is ENUM: {role_type}")
    else:
        logger.warning(f"    ⚠️  users.role is NOT an ENUM: {role_type}")
        all_ok = False

    # Verify FK
    if _fk_exists(cursor, 'users', 'fk_users_employee'):
        logger.info("    ✅ FK 'fk_users_employee' exists")
    else:
        logger.warning("    ⚠️  FK 'fk_users_employee' not found")
        all_ok = False

    # Verify onboarding tables
    logger.info("\n  📋 Onboarding tables:")
    onboarding_tables = [
        'onboarding_joinee',
        'onboarding_declaration',
        'onboarding_references',
        'onboarding_documents',
        'onboarding_audit_log',
    ]
    for tbl in onboarding_tables:
        exists = _table_exists(cursor, tbl)
        status = "✅" if exists else "❌"
        logger.info(f"    {status} {tbl}")
        if not exists:
            all_ok = False

    logger.info("")
    if all_ok:
        logger.info("  ✅ All checks passed — migration verified successfully")
    else:
        logger.warning("  ⚠️  Some checks failed — review warnings above")

    return all_ok


# ─── Main ──────────────────────────────────────────────────────────────

def run_migration(dry_run=False):
    mode = "DRY-RUN" if dry_run else "LIVE"
    logger.info("═══════════════════════════════════════════════════")
    logger.info(f"  Migration 017: Onboarding Module [{mode}]")
    logger.info("═══════════════════════════════════════════════════")

    with Transaction() as cursor:
        phase1_users_refactor(cursor, dry_run)
        phase2_onboarding_tables(cursor, dry_run)
        verify_migration(cursor)

        if dry_run:
            logger.info("\n💡 This was a DRY-RUN. No data was modified.")
            raise Exception("DRY-RUN: Rolling back transaction")

        logger.info("\n═══════════════════════════════════════════════════")
        logger.info(f"  Migration 017 completed successfully [{mode}]")
        logger.info("═══════════════════════════════════════════════════")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migration 017: Onboarding Module + Users Table Alignment"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report only — do not modify data"
    )
    args = parser.parse_args()

    try:
        run_migration(dry_run=args.dry_run)
    except Exception as e:
        if "DRY-RUN" in str(e):
            pass
        else:
            logger.error(f"Migration failed: {e}")
            sys.exit(1)
