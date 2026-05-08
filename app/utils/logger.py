import logging
import sys

def setup_logger():
    """Configure basic logging for the HRMS application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Set levels for noisy libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
