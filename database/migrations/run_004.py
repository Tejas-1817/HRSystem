import mysql.connector
import sys
import os

# Add root directory to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.config import Config

def run_migration():
    print("🚀 Running Migration 004: Token Blacklist Table...")
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASS,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # Read SQL file
        sql_path = os.path.join(os.path.dirname(__file__), '004_token_blacklist.sql')
        with open(sql_path, 'r') as f:
            sql_commands = f.read().split(';')

        for command in sql_commands:
            if command.strip():
                cursor.execute(command)
        
        conn.commit()
        print("✅ Migration 004 completed successfully!")
        
    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    run_migration()
