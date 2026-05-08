from werkzeug.security import generate_password_hash
import mysql.connector
import sys
import os

# Add root directory to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.config import Config

def reset_test_user():
    print("🔄 Resetting password for tejas@gmail.com to 'Tejas@123'...")
    new_hash = generate_password_hash("Tejas@123")
    
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASS,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password = %s, is_active = TRUE, password_change_required = FALSE WHERE username = 'tejas@gmail.com'", (new_hash,))
        conn.commit()
        print("✅ Password reset successfully.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    reset_test_user()
