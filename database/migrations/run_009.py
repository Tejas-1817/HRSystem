"""
Migration 009 Runner: Role-Based Timesheet Approval Workflow
Executes 009_timesheet_approval_workflow.sql against the configured database.
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
    Strips comments (-- ...) and blank lines, splits on ';'.
    """
    # Remove single-line comments
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
    sql_path = os.path.join(os.path.dirname(__file__), '009_timesheet_approval_workflow.sql')
    with open(sql_path, 'r') as f:
        sql = f.read()

    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'hrmsuser'),
        password=os.getenv('DB_PASS', 'Altzor@123'),
        database=os.getenv('DB_NAME', 'hrms'),
    )
    cursor = conn.cursor()

    print("🚀 Running Migration 009: Role-Based Timesheet Approval Workflow ...")

    statements = _split_statements(sql)
    executed = 0

    try:
        for i, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
                # Consume any result set to avoid errors on the next statement
                try:
                    cursor.fetchall()
                except mysql.connector.errors.InterfaceError:
                    pass  # No result set (DDL / DML)
                executed += 1
            except mysql.connector.Error as e:
                # Skip "duplicate column" or "already exists" errors for idempotency
                if e.errno in (1060, 1061, 1050):  # Duplicate column, Duplicate key, Table exists
                    print(f"  ⏩ Skipped (already exists): {stmt[:60]}...")
                    executed += 1
                else:
                    raise

        conn.commit()
        print(f"✅ Migration 009 completed successfully. ({executed} statements executed)")
    except mysql.connector.Error as e:
        conn.rollback()
        print(f"❌ Migration 009 failed at statement {i}: {e}")
        print(f"   Statement: {stmt[:120]}...")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    run()
