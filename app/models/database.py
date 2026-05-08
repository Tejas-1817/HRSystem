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
