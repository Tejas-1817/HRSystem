import json
from app import create_app
from datetime import datetime

def test_endpoints():
    app = create_app()
    client = app.test_client()
    
    # We need a token since the endpoints are @token_required
    # We'll mock the token_required decorator or just test the logic directly
    # But for a quick check, let's see if the routes are registered
    print("Registered Routes:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule}")

    # To actually test the data, we'd need to mock the DB or have a real one
    # Since I'm on the user's machine, I can try to hit the DB
    with app.app_context():
        from app.models.database import execute_query
        
        # Test Birthdays Today
        print("\nChecking birthdays today...")
        query_today = """
            SELECT name, date_of_birth
            FROM employee
            WHERE MONTH(date_of_birth) = MONTH(CURDATE())
              AND DAY(date_of_birth) = DAY(CURDATE())
        """
        try:
            birthdays = execute_query(query_today)
            print(f"Birthdays today: {birthdays}")
        except Exception as e:
            print(f"Error checking birthdays: {e}")

        # Test Holidays
        print("\nChecking holidays...")
        try:
            holidays = execute_query("SELECT * FROM holidays")
            print(f"Holidays: {len(holidays)} found")
        except Exception as e:
            print(f"Error checking holidays: {e}")

if __name__ == "__main__":
    test_endpoints()
