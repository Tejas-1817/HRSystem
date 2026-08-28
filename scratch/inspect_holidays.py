from app import create_app
from app.models.database import execute_query

app = create_app()
with app.app_context():
    holidays = execute_query("SELECT * FROM holidays LIMIT 5")
    for h in holidays:
        print(f"ID: {h.get('id')}, Name: {h.get('name')}, Date: {h.get('date')}, Type: {h.get('date').__class__.__name__ if h.get('date') else None}")
