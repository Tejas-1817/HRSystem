import threading
import time
import logging
from app.services.rental_invoice_service import check_and_generate_invoices

logger = logging.getLogger(__name__)

def run_scheduler_loop():
    """Background loop that runs the rental invoice check periodically."""
    logger.info("Rental Invoice Scheduler loop started.")
    
    # Wait a short moment on startup to let DB pool fully initialize
    time.sleep(5)
    
    while True:
        try:
            logger.info("Running automated Rental Invoice check...")
            check_and_generate_invoices()
            logger.info("Automated Rental Invoice check completed.")
        except Exception as e:
            logger.error(f"Error in Rental Invoice check loop: {e}")
        
        # Check every 6 hours (21600 seconds)
        time.sleep(21600)

def start_rental_scheduler(app):
    """Start the background scheduler thread."""
    # We pass app or use app context if needed, but since our DB pool is global,
    # we don't strictly require the active flask request context for raw DB queries.
    thread = threading.Thread(target=run_scheduler_loop, name="RentalInvoiceScheduler")
    thread.daemon = True
    thread.start()
    logger.info("Background thread for Rental Invoice Scheduler spawned.")
