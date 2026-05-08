#!/usr/bin/env python3
"""
Run Migration 002: Help Desk (Ticket Management) Module
Uses the project's database connection settings from .env
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

import mysql.connector

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_NAME = os.getenv("DB_NAME", "starterdata")
DB_USER = os.getenv("DB_USER", "tejas")
DB_PASS = os.getenv("DB_PASS", "password123")

STEPS = [
    (
        "CREATE TABLE helpdesk_tickets",
        """
        CREATE TABLE IF NOT EXISTS helpdesk_tickets (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            ticket_ref    VARCHAR(20) UNIQUE NOT NULL,
            title         VARCHAR(255) NOT NULL,
            description   TEXT NOT NULL,
            category      ENUM('it_issue','hr_issue','payroll','leave','others') NOT NULL,
            priority      ENUM('low','medium','high','urgent') NOT NULL DEFAULT 'medium',
            status        ENUM('open','in_progress','resolved','closed') NOT NULL DEFAULT 'open',
            employee_name VARCHAR(100) NOT NULL,
            assigned_to   VARCHAR(100) NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            resolved_at   TIMESTAMP NULL,
            INDEX idx_hd_emp    (employee_name),
            INDEX idx_hd_status (status),
            INDEX idx_hd_prio   (priority),
            INDEX idx_hd_cat    (category),
            INDEX idx_hd_assign (assigned_to)
        )
        """,
    ),
    (
        "CREATE TABLE helpdesk_ticket_history",
        """
        CREATE TABLE IF NOT EXISTS helpdesk_ticket_history (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id  INT NOT NULL,
            changed_by VARCHAR(100) NOT NULL,
            field      VARCHAR(50) NOT NULL,
            old_value  VARCHAR(255) NULL,
            new_value  VARCHAR(255) NULL,
            note       TEXT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES helpdesk_tickets(id) ON DELETE CASCADE,
            INDEX idx_hdh_ticket (ticket_id)
        )
        """,
    ),
]


def run():
    print(f"Connecting to {DB_USER}@{DB_HOST}/{DB_NAME} ...")
    conn = mysql.connector.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cursor = conn.cursor()

    for i, (label, sql) in enumerate(STEPS, 1):
        print(f"\n[{i}/{len(STEPS)}] {label}")
        try:
            cursor.execute(sql)
            conn.commit()
            print("  ✅ OK")
        except mysql.connector.Error as e:
            print(f"  ❌ ERROR: {e}")
            conn.rollback()
            cursor.close()
            conn.close()
            sys.exit(1)

    # Verify
    print("\n--- Verification ---")
    for table in ("helpdesk_tickets", "helpdesk_ticket_history"):
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (DB_NAME, table),
        )
        exists = cursor.fetchone()[0] > 0
        icon = "✅" if exists else "❌"
        print(f"  {icon} {table}: {'exists' if exists else 'MISSING'}")

    cursor.close()
    conn.close()
    print("\n🎉 Migration 002 completed successfully.")


if __name__ == "__main__":
    run()
