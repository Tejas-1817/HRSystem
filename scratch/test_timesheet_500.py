
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app import create_app
from flask import json

def test_timesheet_load():
    app = create_app()
    client = app.test_client()
    
    # Simulate a logged-in user (Admin)
    # We need to bypass the token_required decorator or provide a mock token
    # Since token_required decodes the JWT, we'd need the secret.
    # Alternatively, we can mock the decorator or just call the function directly if possible.
    
    # Let's try to mock the database to see if the code itself has issues
    from unittest.mock import patch
    
    with patch('app.api.middleware.auth.token_required', lambda f: f):
        with patch('app.api.routes.timesheet_routes.token_required', lambda f: f):
            with app.test_request_context('/timesheets/'):
                # We need to provide current_user because the decorator is bypassed
                from app.api.routes.timesheet_routes import view_timesheets
                current_user = {
                    "user_id": 1,
                    "username": "admin",
                    "role": "admin",
                    "employee_name": "Admin User"
                }
                try:
                    response, status = view_timesheets(current_user=current_user)
                    print(f"Status: {status}")
                    print(f"Data: {response.get_json()}")
                except Exception as e:
                    import traceback
                    print(f"Error: {e}")
                    traceback.print_exc()

if __name__ == "__main__":
    test_timesheet_load()
