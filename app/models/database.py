import mysql.connector as mysql
from mysql.connector import pooling
from app.config import Config
import logging
import threading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection Pool (singleton, thread-safe)
# ---------------------------------------------------------------------------
_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """Lazily initialise a shared MySQLConnectionPool (thread-safe)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:                       # double-checked locking
                db_cfg = Config.get_db_config()
                try:
                    _pool = pooling.MySQLConnectionPool(
                        pool_name="hrms_pool",
                        pool_size=Config.DB_POOL_SIZE,
                        pool_reset_session=True,     # reset session state on return
                        **db_cfg,
                    )
                    logger.info(
                        "Database connection pool created  "
                        "(pool_size=%d, host=%s, db=%s)",
                        Config.DB_POOL_SIZE,
                        db_cfg.get("host"),
                        db_cfg.get("database"),
                    )
                except mysql.Error as e:
                    logger.error("Failed to create connection pool: %s", e)
                    raise
    return _pool


def get_connection():
    """
    Return a connection from the pool.

    The caller MUST close the connection when done so it is returned to the
    pool.  All existing call-sites already do this (via `finally: conn.close()`
    or through the `Transaction` context manager).
    """
    try:
        conn = _get_pool().get_connection()
        return conn
    except mysql.Error as e:
        logger.error("Failed to get connection from pool: %s", e)
        raise


# ---------------------------------------------------------------------------
# Transaction context manager (unchanged public API)
# ---------------------------------------------------------------------------
class Transaction:
    """
    Context manager for handling database transactions.
    Usage:
        with Transaction() as cursor:
            cursor.execute(...)
            cursor.execute(...)
    """
    def __init__(self, dictionary=True):
        self.conn = None
        self.cursor = None
        self.dictionary = dictionary

    def __enter__(self):
        self.conn = get_connection()
        self.cursor = self.conn.cursor(dictionary=self.dictionary)
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.conn.rollback()
                logger.error("Transaction rolled back due to error: %s", exc_val)
            else:
                self.conn.commit()
        finally:
            self.cursor.close()
            self.conn.close()           # returns connection to pool


# ---------------------------------------------------------------------------
# Query helpers (unchanged public API)
# ---------------------------------------------------------------------------
def execute_query(query, params=None, dictionary=True, commit=False, cursor=None):
    """
    Execute a query. If 'cursor' is provided, it uses that cursor (and doesn't commit/close).
    Otherwise, it opens a new connection and handles closing.
    """
    if cursor:
        cursor.execute(query, params or ())
        return cursor.fetchall() if not commit else cursor.rowcount

    conn = get_connection()
    _cursor = conn.cursor(dictionary=dictionary)
    try:
        _cursor.execute(query, params or ())
        if commit:
            conn.commit()
            return _cursor.lastrowid
        return _cursor.fetchall()
    finally:
        _cursor.close()
        conn.close()                    # returns connection to pool


def execute_single(query, params=None, dictionary=True, cursor=None):
    """Execute a query and return a single row."""
    if cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()

    conn = get_connection()
    _cursor = conn.cursor(dictionary=dictionary)
    try:
        _cursor.execute(query, params or ())
        return _cursor.fetchone()
    finally:
        _cursor.close()
        conn.close()                    # returns connection to pool


def initialize_rental_invoice_tables():
    """Ensure database has next_due_date column, rental_invoices, and rental_payments tables."""
    try:
        # 1. Add next_due_date to devices table if not exists
        check_col = execute_single("""
            SELECT COUNT(*) AS cnt 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
              AND TABLE_NAME = 'devices' 
              AND COLUMN_NAME = 'next_due_date'
        """)
        if check_col and check_col['cnt'] == 0:
            execute_query("ALTER TABLE devices ADD COLUMN next_due_date DATE NULL AFTER renewal_date", commit=True)
            logger.info("Added next_due_date column to devices table")

        # 2. Create rental_invoices table
        execute_query("""
            CREATE TABLE IF NOT EXISTS rental_invoices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_number VARCHAR(50) UNIQUE NOT NULL,
                device_id INT NOT NULL,
                vendor_name VARCHAR(150) NOT NULL,
                asset_name VARCHAR(200) NOT NULL,
                device_type VARCHAR(50) NOT NULL,
                rental_start_date DATE NOT NULL,
                rental_end_date DATE NOT NULL,
                monthly_rental_amount DECIMAL(10, 2) NOT NULL,
                gst_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                total_amount DECIMAL(10, 2) NOT NULL,
                due_date DATE NOT NULL,
                status ENUM('Pending', 'Paid') NOT NULL DEFAULT 'Pending',
                generated_date DATE NOT NULL,
                payment_date DATE NULL,
                payment_mode VARCHAR(50) NULL,
                reference_number VARCHAR(100) NULL,
                remarks TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            )
        """, commit=True)

        # 3. Create rental_payments table
        execute_query("""
            CREATE TABLE IF NOT EXISTS rental_payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                device_id INT NOT NULL,
                payment_date DATE NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                payment_mode VARCHAR(50) NOT NULL,
                reference_number VARCHAR(100) NULL,
                remarks TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES rental_invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            )
        """, commit=True)
        logger.info("Rental invoice and payment tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing rental invoice tables: {e}")


def initialize_reimbursement_tables():
    """Ensure database has reimbursements and reimbursement_history tables."""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS reimbursements (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                ref              VARCHAR(20) UNIQUE NOT NULL,
                employee_name    VARCHAR(100) NOT NULL,
                title            VARCHAR(255) NOT NULL,
                description      TEXT NULL,
                amount           DECIMAL(10,2) NOT NULL,
                currency         VARCHAR(10) NOT NULL DEFAULT 'INR',
                expense_date     DATE NOT NULL,
                category         ENUM('travel','food','accommodation','office_supplies','others') NOT NULL,
                receipt_file     VARCHAR(500) NULL,
                status           ENUM('pending','approved','rejected','paid') NOT NULL DEFAULT 'pending',
                approved_by      VARCHAR(100) NULL,
                approved_at      TIMESTAMP NULL,
                rejection_reason TEXT NULL,
                payment_status   ENUM('pending','processed') NOT NULL DEFAULT 'pending',
                payment_date     DATE NULL,
                project_id       INT NULL,
                billable         TINYINT(1) NOT NULL DEFAULT 0,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_reimb_emp    (employee_name),
                INDEX idx_reimb_status (status),
                INDEX idx_reimb_cat    (category),
                INDEX idx_reimb_proj   (project_id)
            )
        """, commit=True)

        execute_query("""
            CREATE TABLE IF NOT EXISTS reimbursement_history (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                reimbursement_id  INT NOT NULL,
                changed_by        VARCHAR(100) NOT NULL,
                field             VARCHAR(50) NOT NULL,
                old_value         VARCHAR(255) NULL,
                new_value         VARCHAR(255) NULL,
                note              TEXT NULL,
                changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE CASCADE,
                INDEX idx_rh_reimb (reimbursement_id)
            )
        """, commit=True)
        logger.info("Reimbursement tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing reimbursement tables: {e}")


def initialize_holiday_tables():
    """Ensure database has holidays table and default company holidays seeded."""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS holidays (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                date DATE NOT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'public',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_holiday_date (date)
            )
        """, commit=True)

        # Check if holidays table is empty and seed standard default holidays
        count_row = execute_single("SELECT COUNT(*) AS cnt FROM holidays")
        if count_row and count_row['cnt'] == 0:
            default_holidays = [
                ("New Years", "2026-01-01", "optional", "New Years"),
                ("Makara Sankranthi", "2026-01-15", "optional", "Makara Sankranthi"),
                ("Republic Day", "2026-01-26", "public", "Republic Day"),
                ("Holi", "2026-03-03", "optional", "Holi"),
                ("Ugadi/Gudi Padwa", "2026-03-19", "optional", "Ugadi/Gudi Padwa"),
                ("Good Friday", "2026-04-03", "optional", "Good Friday"),
                ("May Day & Maharashtra Day", "2026-05-01", "public", "May Day & Maharashtra Day"),
                ("Bakrid", "2026-05-28", "public", "Bakrid"),
                ("Independence Day", "2026-08-15", "public", "Independence Day"),
                ("Ganesh Chaturthi", "2026-09-14", "public", "Ganesh Chaturthi"),
                ("Gandhi Jayanti", "2026-10-02", "public", "Gandhi Jayanti"),
                ("Dasara", "2026-10-20", "optional", "Dasara"),
                ("Diwali", "2026-11-09", "public", "Diwali"),
                ("Christmas", "2026-12-25", "public", "Christmas"),
            ]
            for name, date, htype, desc in default_holidays:
                execute_query(
                    "INSERT INTO holidays (name, date, type, description) VALUES (%s, %s, %s, %s)",
                    (name, date, htype, desc),
                    commit=True
                )
            logger.info("Default company holidays seeded successfully")
        logger.info("Holiday tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing holiday tables: {e}")


def initialize_software_tables():
    """Ensure database has software_licenses table."""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS software_licenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                publisher VARCHAR(200) NOT NULL,
                category VARCHAR(100) NOT NULL,
                version VARCHAR(100) NOT NULL,
                license_type VARCHAR(100) NOT NULL,
                allocated VARCHAR(100) NOT NULL DEFAULT '—',
                status ENUM('Active', 'Renewal Soon', 'Expired') NOT NULL DEFAULT 'Active',
                assigned_names JSON NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """, commit=True)
        logger.info("Software tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing software tables: {e}")




