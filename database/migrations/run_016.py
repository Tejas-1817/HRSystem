"""
Migration 016: Team Member Professional Information Fields
──────────────────────────────────────────────────────────
Adds enterprise-grade HR fields (designation, department, gender, address,
employment_type) to the employee table, creates dynamic departments and
designations management tables, and seeds default values.

Usage:
    python database/migrations/run_016.py              # Run live
    python database/migrations/run_016.py --dry-run    # Scan only, no changes

Safe to run multiple times — uses IF NOT EXISTS guards.
"""

import sys
import os
import argparse
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction, execute_query, execute_single

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def check_column_exists(cursor, table, column):
    """Check if a column already exists in a table."""
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """, (table, column))
    result = cursor.fetchone()
    return result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0


def check_table_exists(cursor, table):
    """Check if a table already exists."""
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
    """, (table,))
    result = cursor.fetchone()
    return result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0


def run_migration(dry_run=False):
    mode = "DRY-RUN" if dry_run else "LIVE"
    logger.info("═══════════════════════════════════════════════════")
    logger.info(f"  Migration 016: Team Member Info Fields [{mode}]")
    logger.info("═══════════════════════════════════════════════════")

    with Transaction() as cursor:
        # ─── Phase 1: Add new columns to employee table ───────────────
        logger.info("\n📊 Phase 1: Adding new columns to employee table...")

        new_columns = [
            ("designation",      "VARCHAR(100) NULL"),
            ("department",       "VARCHAR(100) NULL"),
            ("gender",           "VARCHAR(30) NULL"),
            ("address",          "TEXT NULL"),
            ("employment_type",  "VARCHAR(50) NULL"),
            ("team_member_code", "VARCHAR(20) NULL"),
            ("created_by",       "VARCHAR(100) NULL"),
            ("updated_by",       "VARCHAR(100) NULL"),
        ]

        for col_name, col_def in new_columns:
            if check_column_exists(cursor, 'employee', col_name):
                logger.info(f"  ✅ Column '{col_name}' already exists — skipping")
            else:
                if not dry_run:
                    cursor.execute(f"ALTER TABLE employee ADD COLUMN {col_name} {col_def}")
                    logger.info(f"  ✅ Added column '{col_name}' ({col_def})")
                else:
                    logger.info(f"  [DRY-RUN] Would add column '{col_name}' ({col_def})")

        # Check updated_at column
        if not check_column_exists(cursor, 'employee', 'updated_at'):
            if not dry_run:
                cursor.execute(
                    "ALTER TABLE employee ADD COLUMN updated_at "
                    "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                )
                logger.info("  ✅ Added column 'updated_at'")
            else:
                logger.info("  [DRY-RUN] Would add column 'updated_at'")
        else:
            logger.info("  ✅ Column 'updated_at' already exists — skipping")

        # ─── Phase 2: Add indexes ─────────────────────────────────────
        logger.info("\n📊 Phase 2: Adding indexes...")

        indexes = [
            ("idx_emp_department",        "employee", "department"),
            ("idx_emp_employment_type",   "employee", "employment_type"),
            ("idx_emp_gender",            "employee", "gender"),
        ]

        for idx_name, table, column in indexes:
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND INDEX_NAME = %s
            """, (table, idx_name))
            result = cursor.fetchone()
            exists = result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0

            if exists:
                logger.info(f"  ✅ Index '{idx_name}' already exists — skipping")
            else:
                if not dry_run:
                    cursor.execute(f"CREATE INDEX {idx_name} ON {table}({column})")
                    logger.info(f"  ✅ Created index '{idx_name}' on {table}.{column}")
                else:
                    logger.info(f"  [DRY-RUN] Would create index '{idx_name}'")

        # Unique index for team_member_code
        cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'employee'
              AND INDEX_NAME = 'idx_emp_team_member_code'
        """)
        result = cursor.fetchone()
        exists = result['cnt'] > 0 if isinstance(result, dict) else result[0] > 0
        if not exists:
            if not dry_run:
                cursor.execute(
                    "CREATE UNIQUE INDEX idx_emp_team_member_code "
                    "ON employee(team_member_code)"
                )
                logger.info("  ✅ Created unique index 'idx_emp_team_member_code'")
            else:
                logger.info("  [DRY-RUN] Would create unique index 'idx_emp_team_member_code'")
        else:
            logger.info("  ✅ Index 'idx_emp_team_member_code' already exists — skipping")

        # ─── Phase 3: Create departments table ────────────────────────
        logger.info("\n📊 Phase 3: Creating departments table...")

        if check_table_exists(cursor, 'departments'):
            logger.info("  ✅ Table 'departments' already exists — skipping creation")
        else:
            if not dry_run:
                cursor.execute("""
                    CREATE TABLE departments (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        description VARCHAR(255) NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_by VARCHAR(100) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_dept_active (is_active)
                    )
                """)
                logger.info("  ✅ Created table 'departments'")
            else:
                logger.info("  [DRY-RUN] Would create table 'departments'")

        # ─── Phase 4: Create designations table ───────────────────────
        logger.info("\n📊 Phase 4: Creating designations table...")

        if check_table_exists(cursor, 'designations'):
            logger.info("  ✅ Table 'designations' already exists — skipping creation")
        else:
            if not dry_run:
                cursor.execute("""
                    CREATE TABLE designations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        department_id INT NULL,
                        description VARCHAR(255) NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_by VARCHAR(100) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
                        INDEX idx_desig_active (is_active),
                        INDEX idx_desig_dept (department_id)
                    )
                """)
                logger.info("  ✅ Created table 'designations'")
            else:
                logger.info("  [DRY-RUN] Would create table 'designations'")

        # ─── Phase 5: Seed default departments ────────────────────────
        logger.info("\n📊 Phase 5: Seeding default departments...")

        default_departments = [
            ("Engineering",          "Software development and technical operations"),
            ("HR",                   "Human Resources and people management"),
            ("Finance",              "Financial operations and accounting"),
            ("Recruitment",          "Talent acquisition and hiring"),
            ("Operations",           "Business operations and logistics"),
            ("Marketing",            "Marketing and brand management"),
            ("Sales",                "Sales and business development"),
            ("Legal",                "Legal and compliance"),
            ("IT",                   "IT infrastructure and support"),
            ("Administration",       "General administration and office management"),
            ("Product",              "Product management and strategy"),
            ("Design",               "UI/UX and graphic design"),
            ("Quality Assurance",    "Testing and quality control"),
            ("Customer Support",     "Customer service and support"),
            ("Research & Development", "R&D and innovation"),
        ]

        seeded_depts = 0
        for name, desc in default_departments:
            cursor.execute(
                "SELECT id FROM departments WHERE name = %s", (name,)
            )
            if cursor.fetchone():
                continue
            if not dry_run:
                cursor.execute(
                    "INSERT INTO departments (name, description, created_by) "
                    "VALUES (%s, %s, 'system')",
                    (name, desc)
                )
                seeded_depts += 1

        logger.info(f"  ✅ Seeded {seeded_depts} new department(s)")

        # ─── Phase 6: Seed default designations ───────────────────────
        logger.info("\n📊 Phase 6: Seeding default designations...")

        default_designations = [
            "Software Engineer", "Senior Software Engineer", "HR Executive",
            "HR Manager", "Project Manager", "Recruiter", "Senior Developer",
            "Team Lead", "QA Engineer", "DevOps Engineer", "Business Analyst",
            "Product Manager", "Technical Lead", "Data Analyst",
            "UI/UX Designer", "System Administrator", "Intern", "Trainee",
        ]

        seeded_desigs = 0
        for name in default_designations:
            cursor.execute(
                "SELECT id FROM designations WHERE name = %s", (name,)
            )
            if cursor.fetchone():
                continue
            if not dry_run:
                cursor.execute(
                    "INSERT INTO designations (name, created_by) "
                    "VALUES (%s, 'system')",
                    (name,)
                )
                seeded_desigs += 1

        logger.info(f"  ✅ Seeded {seeded_desigs} new designation(s)")

        # ─── Summary ──────────────────────────────────────────────────
        logger.info("\n═══════════════════════════════════════════════════")
        logger.info(f"  Migration 016 completed successfully [{mode}]")
        logger.info("═══════════════════════════════════════════════════")

        if dry_run:
            logger.info("💡 This was a DRY-RUN. No data was modified.")
            raise Exception("DRY-RUN: Rolling back transaction")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migration 016: Team Member Professional Information Fields"
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
