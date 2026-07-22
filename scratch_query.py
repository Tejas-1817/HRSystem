import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.models.database import get_connection

try:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email, role FROM users WHERE role='superadmin'")
    rows = cursor.fetchall()
    print("Found superadmins:")
    for row in rows:
        print(row)
except Exception as e:
    print("Error:", e)
