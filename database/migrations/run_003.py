#!/usr/bin/env python3
"""
Run Migration 003: Reimbursement (Expense Management) Module
Uses the project's database connection settings from .env
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

import mysql.connector

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_NAME = os.getenv("DB_NAME", "hrms")
DB_USER = os.getenv("DB_USER", "hrmsuser")
DB_PASS = os.getenv("DB_PASS", "Altzor@123")

STEPS = [
    (
        "CREATE TABLE reimbursements",
        """
        CREATE TABLE IF NOT EXISTS reimbursements (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            ref              VARCHAR(20) UNIQUE NOT NULL,
            employee_name    VARCHAR(100) NOT NULL,
            title            VARCHAR(255) NOT NULL,
            description      TEXT NULL,
            amount           DECIMAL(10,2) NOT NULL,
            currency         VARCHAR(10) NOT NULL DEFAULT 'INR',
            expense_date     DATE NOT NULL,
            category         ENUM('travel','food','accommodation','office_supplies','others') NOT NULL,
            receipt_file     VARCHAR(500) NULL,
            status           ENUM('pending','approved','rejected','paid') NOT NULL DEFAULT 'pending',
            approved_by      VARCHAR(100) NULL,
            approved_at      TIMESTAMP NULL,
            rejection_reason TEXT NULL,
            payment_status   ENUM('pending','processed') NOT NULL DEFAULT 'pending',
            payment_date     DATE NULL,
            project_id       INT NULL,
            billable         TINYINT(1) NOT NULL DEFAULT 0,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_reimb_emp    (employee_name),
            INDEX idx_reimb_status (status),
            INDEX idx_reimb_cat    (category),
            INDEX idx_reimb_proj   (project_id)
        )
        """,
    ),
    (
        "CREATE TABLE reimbursement_history",
        """
        CREATE TABLE IF NOT EXISTS reimbursement_history (
            id                INT AUTO_INCREMENT PRIMARY KEY,
            reimbursement_id  INT NOT NULL,
            changed_by        VARCHAR(100) NOT NULL,
            field             VARCHAR(50) NOT NULL,
            old_value         VARCHAR(255) NULL,
            new_value         VARCHAR(255) NULL,
            note              TEXT NULL,
            changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE CASCADE,
            INDEX idx_rh_reimb (reimbursement_id)
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
    for table in ("reimbursements", "reimbursement_history"):
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (DB_NAME, table),
        )
        exists = cursor.fetchone()[0] > 0
        icon = "✅" if exists else "❌"
        print(f"  {icon} {table}: {'exists' if exists else 'MISSING'}")

    cursor.close()
    conn.close()
    print("\n🎉 Migration 003 completed successfully.")


if __name__ == "__main__":
    run()
