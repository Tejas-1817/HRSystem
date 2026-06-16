"""
Migration 021 Runner: Device Asset ID
Executes 021_device_asset_id.sql against the configured database.

Adds:
  - devices.asset_id (VARCHAR 100 UNIQUE)
"""
import os
import sys
import mysql.connector

# Allow running from project root or migrations/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv()


def run():
    sql_path = os.path.join(os.path.dirname(__file__), "021_device_asset_id.sql")
    with open(sql_path, "r") as f:
        sql = f.read()

    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "hrmsuser"),
        password=os.getenv("DB_PASS", "Altzor@123"),
        database=os.getenv("DB_NAME", "hrms"),
        port=int(os.getenv("DB_PORT", 3306)),
    )
    cursor = conn.cursor()

    print("🚀 Running Migration 021: Device Asset ID ...")

    try:
        for result in cursor.execute(sql, multi=True):
            try:
                result.fetchall()
            except mysql.connector.errors.InterfaceError:
                pass

        conn.commit()
        print("✅ Migration 021 completed successfully.")
        print("   Added: devices.asset_id")
    except mysql.connector.Error as e:
        conn.rollback()
        if e.errno == 1060:
            print(f"  ⏩ Skipped (already applied): {e}")
        else:
            print(f"❌ Migration 021 failed: {e}")
            sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run()
