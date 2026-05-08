import sys
import os
import requests
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app
from app.models.database import execute_single, execute_query
from werkzeug.security import check_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_login_repaired():
    """Verify that a repaired account can log in."""
    logger.info("--- Testing Repaired Account Login ---")
    
    # Test for Arnav
    username = "arnav@example.com"
    user = execute_single("SELECT * FROM users WHERE username=%s", (username,))
    
    if not user:
        logger.error(f"❌ User {username} not found in DB")
        return
    
    if check_password_hash(user['password'], "Welcome@123"):
        logger.info(f"✅ User {username} can log in with default password")
    else:
        logger.error(f"❌ User {username} password hash mismatch")

if __name__ == "__main__":
    verify_login_repaired()
