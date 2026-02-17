"""
Authentication module: SQLite + bcrypt.
- Users table: email (unique), password_hash, name, created_at
- No self-signup; use add_user.py (or admin) to create accounts.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional

import bcrypt

# Database path (in project directory; add abcover_users.db to .gitignore)
_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DIR, "abcover_users.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create users table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                name TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def verify_password(password: str, password_hash: bytes) -> bool:
    if isinstance(password_hash, str):
        password_hash = password_hash.encode("utf-8")
    return bcrypt.checkpw(password.encode("utf-8"), password_hash)


def create_user(email: str, password: str, name: str = "") -> bool:
    """Create a new user. Returns True on success, False if email already exists."""
    init_db()
    email = email.strip().lower()
    if not email or not password:
        return False
    pw_hash = hash_password(password)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
            (email, pw_hash.decode("utf-8") if isinstance(pw_hash, bytes) else pw_hash, name or "", datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[dict]:
    """Return user row as dict or None."""
    init_db()
    email = email.strip().lower()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT email, password_hash, name, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if not row:
            return None
        return {
            "email": row[0],
            "password_hash": row[1],
            "name": row[2],
            "created_at": row[3],
        }
    finally:
        conn.close()


def check_credentials(email: str, password: str) -> bool:
    """Verify email + password. Returns True if valid."""
    user = get_user_by_email(email)
    if not user:
        return False
    stored = user["password_hash"]
    if isinstance(stored, str):
        stored = stored.encode("utf-8")
    return verify_password(password, stored)


def list_users():
    """Return list of user emails (for admin)."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute("SELECT email, name, created_at FROM users ORDER BY created_at").fetchall()
        return [{"email": r[0], "name": r[1] or "", "created_at": r[2]} for r in rows]
    finally:
        conn.close()
