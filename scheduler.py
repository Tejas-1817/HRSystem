"""
Dedicated Background Scheduler Process for RISE HRMS
=====================================================
Executes all scheduled background tasks for the HRMS system in a single,
dedicated process independent of Gunicorn worker processes.

Scheduled Jobs:
  1. Rental Invoice Generation (job_rental_invoice_check):
     - Checks active rental devices and auto-generates invoices due within 7 days.
     - Frequency: Every 6 hours (interval=6h, with immediate run on startup).
  2. Daily Leave Credit Sweep (job_leave_credit_sweep):
     - Automatically credits quarterly leaves for eligible Full Time employees.
     - Frequency: Daily at 01:00 AM (cron: hour=1, minute=0).

Usage:
  python scheduler.py
"""

import os
import sys
import signal
import logging
from datetime import datetime
from dotenv import load_dotenv

# Ensure the project root directory is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HRMS-Scheduler] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("HRMSScheduler")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.services.rental_invoice_service import check_and_generate_invoices
from app.services.leave_credit_service import run_credit_sweep
from app.models.database import (
    initialize_rental_invoice_tables,
    initialize_reimbursement_tables,
    initialize_holiday_tables,
    initialize_software_tables
)


def job_rental_invoice_check():
    """Execute scheduled rental invoice check with robust error handling."""
    logger.info("Executing scheduled rental invoice generation check...")
    try:
        check_and_generate_invoices()
        logger.info("Rental invoice generation check completed successfully.")
    except Exception as e:
        logger.error(f"Error during rental invoice generation check: {e}", exc_info=True)


def job_leave_credit_sweep():
    """Execute scheduled daily leave credit sweep with robust error handling."""
    logger.info("Executing scheduled daily leave credit sweep...")
    try:
        summary = run_credit_sweep()
        logger.info(
            f"Daily leave credit sweep completed. "
            f"Employees processed: {summary.get('employees_processed', 0)}, "
            f"Quarters credited: {summary.get('quarters_credited', 0)}, "
            f"Quarters skipped: {summary.get('quarters_skipped', 0)}, "
            f"Quarters failed: {summary.get('quarters_failed', 0)}"
        )
    except Exception as e:
        logger.error(f"Error during daily leave credit sweep: {e}", exc_info=True)


def main():
    logger.info("=" * 65)
    logger.info("Starting RISE HRMS Dedicated Background Scheduler Process")
    logger.info("=" * 65)

    # Verify and initialize database tables
    try:
        initialize_rental_invoice_tables()
        initialize_reimbursement_tables()
        initialize_holiday_tables()
        initialize_software_tables()
        logger.info("Database tables initialized/verified.")
    except Exception as e:
        logger.error(f"Warning: Database initialization error in scheduler: {e}")

    scheduler = BlockingScheduler()

    # 1. Rental Invoice Check (every 6 hours, starts immediately)
    scheduler.add_job(
        func=job_rental_invoice_check,
        trigger=IntervalTrigger(hours=6),
        next_run_time=datetime.now(),
        id="rental_invoice_check",
        name="Rental Invoice Check (every 6h)",
        max_instances=1,
        coalesce=True,
        replace_existing=True
    )
    logger.info("Job registered: [rental_invoice_check] Interval: every 6 hours (initial execution: now)")

    # 2. Daily Leave Credit Sweep (every day at 01:00 AM)
    scheduler.add_job(
        func=job_leave_credit_sweep,
        trigger=CronTrigger(hour=1, minute=0),
        id="daily_leave_credit_sweep",
        name="Daily Leave Credit Sweep (01:00 AM)",
        max_instances=1,
        coalesce=True,
        replace_existing=True
    )
    logger.info("Job registered: [daily_leave_credit_sweep] Cron: daily at 01:00 AM")

    # Graceful shutdown handler for SIGINT (Ctrl+C) and SIGTERM (systemd stop)
    def handle_shutdown(signum, frame):
        try:
            sig_name = signal.Signals(signum).name
        except Exception:
            sig_name = str(signum)
        logger.info(f"Received shutdown signal {sig_name}. Stopping scheduler gracefully...")
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("Scheduler loop is running. Press Ctrl+C or send SIGTERM to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler process stopped cleanly.")


if __name__ == "__main__":
    main()
