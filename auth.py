import os
import sqlite3
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import bcrypt
from jose import jwt


# ============================================================
# Configuration
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(
    os.path.join(BASE_DIR, ".env")
)

AUTH_DB = os.path.join(
    BASE_DIR,
    "auth.db",
)

SECRET_KEY = os.getenv(
    "NEXUS_AUTH_SECRET_KEY",
    "nexusai-development-secret-change-this",
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# ============================================================
# Database
# ============================================================

def get_connection():
    connection = sqlite3.connect(AUTH_DB)
    connection.row_factory = sqlite3.Row
    return connection


def init_auth_db():
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# Password Hashing
# ============================================================

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    # bcrypt supports a maximum of 72 bytes.
    if len(password_bytes) > 72:
        raise ValueError(
            "Password cannot be longer than 72 bytes."
        )

    salt = bcrypt.gensalt()

    hashed = bcrypt.hashpw(
        password_bytes,
        salt,
    )

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:

    password_bytes = plain_password.encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")

    if len(password_bytes) > 72:
        return False

    return bcrypt.checkpw(
        password_bytes,
        hash_bytes,
    )


# ============================================================
# User Functions
# ============================================================

def create_user(
    email: str,
    password: str,
):
    email = email.strip().lower()

    password_hash = hash_password(password)

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO users (
                email,
                password_hash,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                email,
                password_hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        connection.commit()

        return {
            "id": cursor.lastrowid,
            "email": email,
        }

    finally:
        connection.close()


def get_user_by_email(email: str):
    email = email.strip().lower()

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                id,
                email,
                password_hash,
                created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        connection.close()


def authenticate_user(
    email: str,
    password: str,
):
    user = get_user_by_email(email)

    if user is None:
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return None

    return user


def update_password(
    email: str,
    new_password: str,
) -> bool:

    email = email.strip().lower()

    password_hash = hash_password(new_password)

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE email = ?
            """,
            (
                password_hash,
                email,
            ),
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


# ============================================================
# JWT
# ============================================================

def create_access_token(
    user_id: int,
    email: str,
) -> str:

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            return None

        return {
            "user_id": int(user_id),
            "email": email,
        }

    except Exception:
        return None


# ============================================================
# Initialize Database
# ============================================================

init_auth_db()
