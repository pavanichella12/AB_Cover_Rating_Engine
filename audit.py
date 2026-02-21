"""
Logging and audit trail for ABCover Rating Engine.
- Application logs: logs/app.log (uploads, steps, errors with traceback).
- Run history: rating_runs table in same DB as auth (who, when, file, filters, results or error).
"""

import logging
import os
import json
import traceback
from datetime import datetime
from typing import Optional, Any

# Use same DB as auth
from auth import get_connection

# Log directory and file; use APP_DATA_DIR in Docker for persistent logs
_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.environ.get("APP_DATA_DIR", _DIR)
LOG_DIR = os.path.join(_DATA_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_logger_initialized = False


def setup_logging() -> None:
    """Configure logging to file and console. Safe to call multiple times."""
    global _logger_initialized
    if _logger_initialized:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("abcover")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    _logger_initialized = True


def get_logger():
    setup_logging()
    return logging.getLogger("abcover")


def init_audit_db() -> None:
    """Create rating_runs table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rating_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_email TEXT,
                filename TEXT,
                filters_json TEXT,
                rows_raw INTEGER,
                rows_selected INTEGER,
                rows_cleaned INTEGER,
                total_teachers INTEGER,
                total_premium REAL,
                status TEXT NOT NULL,
                error_message TEXT,
                step TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def log_run(
    status: str,
    user_email: Optional[str] = None,
    filename: Optional[str] = None,
    filters: Optional[dict] = None,
    rows_raw: Optional[int] = None,
    rows_selected: Optional[int] = None,
    rows_cleaned: Optional[int] = None,
    total_teachers: Optional[int] = None,
    total_premium: Optional[float] = None,
    error_message: Optional[str] = None,
    step: Optional[str] = None,
) -> None:
    """Record a run (success or error) in the audit table."""
    init_audit_db()
    conn = get_connection()
    try:
        filters_json = json.dumps(filters, default=str) if filters else None
        conn.execute(
            """INSERT INTO rating_runs (
                created_at, user_email, filename, filters_json,
                rows_raw, rows_selected, rows_cleaned, total_teachers, total_premium,
                status, error_message, step
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                user_email,
                filename,
                filters_json,
                rows_raw,
                rows_selected,
                rows_cleaned,
                total_teachers,
                total_premium,
                status,
                error_message,
                step,
            ),
        )
        conn.commit()
    except Exception as e:
        get_logger().exception("Failed to write audit record: %s", e)
    finally:
        conn.close()


def log_error(step: str, error: Exception, user_email: Optional[str] = None, **kwargs: Any) -> None:
    """Log exception to file (with full traceback) and record failed run in audit."""
    logger = get_logger()
    err_msg = str(error)
    tb = traceback.format_exc()
    logger.error("Step %s failed: %s\n%s", step, err_msg, tb, exc_info=False)
    full_error = f"{err_msg}\n\nTraceback:\n{tb}" if tb and tb != "NoneType: None\n" else err_msg
    log_run(
        status="error",
        user_email=user_email,
        error_message=full_error,
        step=step,
        **kwargs,
    )


def log_login_success(email: str) -> None:
    """Log successful login."""
    get_logger().info("Login success: user=%s", email)
    _log_login_event(email, "login_success")


def log_login_failure(email: str, reason: str = "invalid_credentials") -> None:
    """Log failed login attempt (email only, no password)."""
    get_logger().warning("Login failed: email=%s reason=%s", email, reason)
    _log_login_event(email, "login_failed", reason)


def log_logout(email: str) -> None:
    """Log user logout."""
    get_logger().info("Logout: user=%s", email)
    _log_login_event(email, "logout")


def _log_login_event(email: str, event: str, detail: Optional[str] = None) -> None:
    """Record login event in DB."""
    init_login_events_db()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO login_events (created_at, email, event, detail)
               VALUES (?, ?, ?, ?)""",
            (datetime.utcnow().isoformat(), email, event, detail),
        )
        conn.commit()
    except Exception as e:
        get_logger().exception("Failed to write login event: %s", e)
    finally:
        conn.close()


def init_login_events_db() -> None:
    """Create login_events table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                email TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()
