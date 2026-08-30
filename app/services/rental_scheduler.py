import time
import logging
from app.services.rental_invoice_service import check_and_generate_invoices

logger = logging.getLogger(__name__)

def run_rental_invoice_check():
    """Execute a single run of the rental invoice check."""
    try:
        logger.info("Running automated Rental Invoice check...")
        check_and_generate_invoices()
        logger.info("Automated Rental Invoice check completed.")
    except Exception as e:
        logger.error(f"Error in Rental Invoice check: {e}", exc_info=True)

def run_scheduler_loop():
    """
    Dedicated loop that runs the rental invoice check periodically.
    Used by standalone scheduler process or standalone scripts.
    """
    logger.info("Rental Invoice Scheduler loop started.")
    # Wait a short moment on startup to let DB pool fully initialize
    time.sleep(2)
    
    while True:
        run_rental_invoice_check()
        # Check every 6 hours (21600 seconds)
        time.sleep(21600)

def start_rental_scheduler(app=None):
    """
    Deprecated: In-process background thread initialization.
    In production, background schedulers run in the dedicated scheduler process
    (scheduler.py / rise-hrms-rental-scheduler.service) to prevent duplicate execution
    across multiple Gunicorn workers.
    """
    logger.warning(
        "start_rental_scheduler() called in-process. In production (Gunicorn multi-worker), "
        "use the dedicated scheduler process (scheduler.py) instead."
    )
