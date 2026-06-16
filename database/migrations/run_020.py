"""
Migration 020 Runner: Device Hardware Specifications
Executes 020_device_hardware_specs.sql against the configured database.

Adds:
  - devices.processor (VARCHAR 150)
  - devices.ram (VARCHAR 50)
  - devices.storage (VARCHAR 100)
"""
import os
import sys
import mysql.connector

# Allow running from project root or migrations/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv()


def run():
    sql_path = os.path.join(os.path.dirname(__file__), "020_device_hardware_specs.sql")
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

    print("🚀 Running Migration 020: Device Hardware Specifications ...")

    try:
        for result in cursor.execute(sql, multi=True):
            try:
                result.fetchall()
            except mysql.connector.errors.InterfaceError:
                pass

        conn.commit()
        print("✅ Migration 020 completed successfully.")
        print("   Added: devices.processor, devices.ram, devices.storage")
    except mysql.connector.Error as e:
        conn.rollback()
        if e.errno == 1060:
            print(f"  ⏩ Skipped (already applied): {e}")
        else:
            print(f"❌ Migration 020 failed: {e}")
            sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run()
