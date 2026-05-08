import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "starterdata")
    DB_USER = os.getenv("DB_USER", "tejas")
    DB_PASS = os.getenv("DB_PASS", "password123")
    JWT_SECRET = os.getenv("JWT_SECRET", "default-secret-key")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    PORT = int(os.getenv("PORT", 5000))

    # Database connection pool size (max simultaneous connections)
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 10))

    # SMTP Settings (For Forgot Password)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "your-email@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "your-app-password")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "HRMS Support <your-email@gmail.com>")

    @staticmethod
    def get_db_config():
        return {
            "host": Config.DB_HOST,
            "database": Config.DB_NAME,
            "user": Config.DB_USER,
            "password": Config.DB_PASS
        }
