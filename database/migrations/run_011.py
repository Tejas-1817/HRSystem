"""
Migration 011 Runner: Role-Based Leave Approval Workflow
Executes 011_leave_approval_workflow.sql against the configured database.

Usage:
    python database/migrations/run_011.py
    # or from project root:
    python -m database.migrations.run_011
"""
import os
import sys
import re
import mysql.connector

# Allow running from project root or migrations/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from dotenv import load_dotenv

load_dotenv()


def _split_statements(sql_text: str) -> list[str]:
    """
    Split a SQL file into individual executable statements.
    Strips single-line comments (-- ...) and blank lines, splits on ';'.
    """
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        # Remove inline comments
        line = re.sub(r'--.*$', '', line)
        lines.append(line)

    full_text = '\n'.join(lines)

    statements = []
    for stmt in full_text.split(';'):
        stmt = stmt.strip()
        if stmt and stmt.upper() not in ('', 'USE hrms'):
            statements.append(stmt)
    return statements


def run():
    sql_path = os.path.join(os.path.dirname(__file__), '011_leave_approval_workflow.sql')
    with open(sql_path, 'r') as f:
        sql = f.read()

    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'hrmsuser'),
        password=os.getenv('DB_PASS', 'Altzor@123'),
        database=os.getenv('DB_NAME', 'hrms'),
        port=int(os.getenv('DB_PORT', 3306)),
    )
    cursor = conn.cursor()

    print("🚀 Running Migration 011: Role-Based Leave Approval Workflow ...")

    statements = _split_statements(sql)
    executed = 0
    i = 0

    try:
        for i, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
                # Consume any result set to avoid "commands out of sync" errors
                try:
                    cursor.fetchall()
                except mysql.connector.errors.InterfaceError:
                    pass  # DDL/DML — no result set
                executed += 1
                print(f"  ✓ Statement {i}: {stmt[:70].replace(chr(10), ' ')}...")
            except mysql.connector.Error as e:
                # Idempotent: skip "already exists" errors
                if e.errno in (1060, 1061, 1050, 1091):
                    # 1060=Duplicate column, 1061=Duplicate key name,
                    # 1050=Table exists,    1091=Can't DROP non-existent key
                    print(f"  ⏩ Skipped (already applied): {stmt[:60]}...")
                    executed += 1
                else:
                    raise

        conn.commit()
        print(f"\n✅ Migration 011 completed successfully. ({executed}/{len(statements)} statements applied)")

    except mysql.connector.Error as e:
        conn.rollback()
        print(f"\n❌ Migration 011 FAILED at statement {i}: {e}")
        print(f"   Statement: {stmt[:120]}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    run()
