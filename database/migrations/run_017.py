#!/usr/bin/env python3
"""
Run Migration 017: Welcome Email Feature Table & Seeding
Uses the project's database connection settings from .env
"""
import sys
import os
import logging
from dotenv import load_dotenv

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path)

from app.models.database import Transaction

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def run_migration():
    logger.info("═══════════════════════════════════════════════════")
    logger.info("  Migration 017: Welcome Email Table & Seeding")
    logger.info("═══════════════════════════════════════════════════")

    sql_path = os.path.join(os.path.dirname(__file__), '017_welcome_email.sql')
    if not os.path.exists(sql_path):
        logger.error(f"SQL migration file not found at: {sql_path}")
        sys.exit(1)

    with open(sql_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split statements by semicolon, stripping comments
    statements = []
    for raw_stmt in sql_content.split(';'):
        cleaned_lines = []
        for line in raw_stmt.split('\n'):
            stripped = line.strip()
            if stripped and not stripped.startswith('--'):
                cleaned_lines.append(line)
        stmt = '\n'.join(cleaned_lines).strip()
        if stmt:
            statements.append(stmt)

    with Transaction() as cursor:
        for i, stmt in enumerate(statements, 1):
            logger.info(f"[{i}/{len(statements)}] Executing: {stmt.splitlines()[0]}...")
            try:
                cursor.execute(stmt)
            except Exception as e:
                logger.error(f"❌ Failed executing statement: {stmt}\nError: {e}")
                raise

    logger.info("🎉 Migration 017 completed successfully.")


if __name__ == "__main__":
    run_migration()
