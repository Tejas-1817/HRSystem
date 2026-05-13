"""
Migration 006 Runner: Device Management + Helpdesk Device Link
Executes 006_device_management.sql against the configured database.
"""
import os
import re
import sys
import mysql.connector

# Allow running from project root or migrations/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv()


def _split_statements(sql_text: str) -> list[str]:
    """Split SQL file into executable statements, removing -- comments."""
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        line = re.sub(r"--.*$", "", line)
        lines.append(line)

    full_text = "\n".join(lines)
    statements = []
    for stmt in full_text.split(";"):
        stmt = stmt.strip()
        if stmt and stmt.upper() not in ("", "USE STARTERDATA"):
            statements.append(stmt)
    return statements


def run():
    sql_path = os.path.join(os.path.dirname(__file__), "006_device_management.sql")
    with open(sql_path, "r") as f:
        sql = f.read()

    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", ""),
        database=os.getenv("DB_NAME", "starterdata"),
        port=int(os.getenv("DB_PORT", 3306)),
    )
    cursor = conn.cursor()

    print("🚀 Running Migration 006: Device Management + Helpdesk device link ...")

    statements = _split_statements(sql)
    executed = 0
    i = 0

    try:
        for i, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
                try:
                    cursor.fetchall()
                except mysql.connector.errors.InterfaceError:
                    pass
                executed += 1
            except mysql.connector.Error as e:
                # Idempotency: already exists/duplicate object.
                if e.errno in (1060, 1061, 1050, 1826):
                    # 1826 = duplicate foreign key constraint name
                    print(f"  ⏩ Skipped (already applied): {stmt[:60]}...")
                    executed += 1
                else:
                    raise

        conn.commit()
        print(f"✅ Migration 006 completed successfully. ({executed}/{len(statements)} statements)")
    except mysql.connector.Error as e:
        conn.rollback()
        print(f"❌ Migration 006 failed at statement {i}: {e}")
        print(f"   Statement: {stmt[:120]}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run()
