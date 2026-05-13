#!/usr/bin/env python3
"""
Run Migration 001: Half-Day Leave Support
Uses the project's database connection settings from .env
"""
import sys
import os

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import mysql.connector

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_NAME = os.getenv("DB_NAME", "hrms")
DB_USER = os.getenv("DB_USER",  "hrmsuser")
DB_PASS = os.getenv("DB_PASS",  "Altzor@123")

def _col_exists(cursor, table: str, column: str, db: str) -> bool:
    """Check if a column exists in a table (compatible with all MySQL versions)."""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
    """, (db, table, column))
    return cursor.fetchone()[0] > 0


def build_migration_steps(cursor, db: str) -> list:
    """
    Build the list of DDL/DML statements to execute, skipping any ADD COLUMN
    steps for columns that already exist (full MySQL-version compatibility).
    """
    steps = []

    if not _col_exists(cursor, "leaves", "leave_type_category", db):
        steps.append((
            "ADD leaves.leave_type_category",
            """ALTER TABLE leaves
               ADD COLUMN leave_type_category
                   ENUM('full_day', 'half_day') NOT NULL DEFAULT 'full_day'
                   AFTER leave_type"""
        ))
    else:
        print("  ℹ️  leaves.leave_type_category already exists — skipping")

    if not _col_exists(cursor, "leaves", "half_day_period", db):
        steps.append((
            "ADD leaves.half_day_period",
            """ALTER TABLE leaves
               ADD COLUMN half_day_period
                   ENUM('first_half', 'second_half') NULL
                   AFTER leave_type_category"""
        ))
    else:
        print("  ℹ️  leaves.half_day_period already exists — skipping")

    if not _col_exists(cursor, "leaves", "leave_duration", db):
        steps.append((
            "ADD leaves.leave_duration",
            """ALTER TABLE leaves
               ADD COLUMN leave_duration
                   DECIMAL(4,2) NOT NULL DEFAULT 1.00
                   AFTER half_day_period"""
        ))
    else:
        print("  ℹ️  leaves.leave_duration already exists — skipping")

    # MODIFY is always safe (idempotent for decimal widening)
    steps.append((
        "MODIFY leave_balance.used_leaves to DECIMAL(6,2)",
        "ALTER TABLE leave_balance MODIFY COLUMN used_leaves DECIMAL(6,2) NOT NULL DEFAULT 0.00"
    ))
    steps.append((
        "MODIFY leave_balance.total_leaves to DECIMAL(6,2)",
        "ALTER TABLE leave_balance MODIFY COLUMN total_leaves DECIMAL(6,2) NOT NULL DEFAULT 0.00"
    ))

    # Back-fill — only runs if the column now exists
    if _col_exists(cursor, "leaves", "leave_type_category", db):
        steps.append((
            "Back-fill leaves with full_day defaults",
            """UPDATE leaves
               SET leave_type_category = 'full_day', leave_duration = 1.00
               WHERE leave_type_category IS NULL OR leave_duration IS NULL"""
        ))

    return steps

def run():
    print(f"Connecting to {DB_USER}@{DB_HOST}/{DB_NAME} ...")
    conn = mysql.connector.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cursor = conn.cursor()

    print("Building migration steps (checking existing schema) ...")
    steps = build_migration_steps(cursor, DB_NAME)

    for i, (label, sql) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {label}")
        try:
            cursor.execute(sql)
            conn.commit()
            print(f"  ✅ OK")
        except mysql.connector.Error as e:
            print(f"  ❌ ERROR: {e}")
            conn.rollback()
            cursor.close()
            conn.close()
            sys.exit(1)

    # Verify results
    print("\n--- Verification ---")
    cursor.execute("DESCRIBE leaves")
    cols = {r[0] for r in cursor.fetchall()}
    needed = {"leave_type_category", "half_day_period", "leave_duration"}
    missing = needed - cols
    if missing:
        print(f"❌ Missing columns in `leaves`: {missing}")
    else:
        print(f"✅ leaves table: {', '.join(sorted(needed))} all present")

    cursor.execute("SHOW COLUMNS FROM leave_balance LIKE 'used_leaves'")
    row = cursor.fetchone()
    if row:
        print(f"✅ leave_balance.used_leaves type: {row[1]}")
    else:
        print("❌ Could not verify leave_balance.used_leaves type")

    cursor.close()
    conn.close()
    print("\n🎉 Migration 001 completed successfully.")


if __name__ == "__main__":
    run()
