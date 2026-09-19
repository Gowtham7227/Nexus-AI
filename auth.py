import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

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

AUTH_DB = os.getenv("AUTH_DB_PATH")
if not AUTH_DB:
    local_db = os.path.join(BASE_DIR, "auth.db")
    alt_db = os.path.join(BASE_DIR, "..", "backend", "auth.db")
    if os.path.exists(local_db) and os.path.getsize(local_db) > 0:
        AUTH_DB = local_db
    elif os.path.exists(alt_db) and os.path.getsize(alt_db) > 0:
        AUTH_DB = alt_db
    else:
        AUTH_DB = local_db

SECRET_KEY = os.getenv(
    "NEXUS_AUTH_SECRET_KEY",
    "nexusai-secure-default-jwt-secret-key-2026",
)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

if ENVIRONMENT == "production" and (not SECRET_KEY or SECRET_KEY == "nexusai-secure-default-jwt-secret-key-2026"):
    raise RuntimeError("NEXUS_AUTH_SECRET_KEY must be set to a strong secret in production mode.")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))  # 24 hours default


# ============================================================
# Database
# ============================================================

def get_connection():
    connection = sqlite3.connect(AUTH_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_auth_db():
    """
    Initialize users, documents, conversations, messages, and conversation_documents tables automatically.
    Perform non-destructive schema migrations for existing databases.
    """
    connection = get_connection()

    try:
        # 1. Users table
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

        # 2. Documents table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT,
                file_size INTEGER DEFAULT 0,
                file_type TEXT,
                created_at TEXT NOT NULL,
                processing_status TEXT DEFAULT 'completed',
                processing_error TEXT,
                vector_status TEXT DEFAULT 'indexed',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # 3. Conversations table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # 4. Messages table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )

        # 5. Conversation Documents mapping table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )

        # 6. Indexes for high performance
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_docs_conv_id ON conversation_documents(conversation_id)"
        )

        # 7. Schema migration: check for missing columns in existing documents table
        cursor = connection.execute("PRAGMA table_info(documents)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        col_defs = {
            "original_filename": "TEXT",
            "file_size": "INTEGER DEFAULT 0",
            "file_type": "TEXT",
            "processing_status": "TEXT DEFAULT 'completed'",
            "processing_error": "TEXT",
            "vector_status": "TEXT DEFAULT 'indexed'",
            "privacy_risk": "TEXT DEFAULT 'LOW'",
            "privacy_details": "TEXT",
            "extraction_method": "TEXT DEFAULT 'native'",
            "ocr_used": "INTEGER DEFAULT 0",
            "ocr_page_count": "INTEGER DEFAULT 0",
            "page_count": "INTEGER DEFAULT 0",
            "extracted_char_count": "INTEGER DEFAULT 0",
        }

        for col_name, col_type in col_defs.items():
            if col_name not in existing_cols:
                try:
                    connection.execute(
                        f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"
                    )
                except Exception as migration_err:
                    print(f"Migration note ({col_name}):", str(migration_err))

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

    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

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

    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters.")

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


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.
    Strictly enforces algorithm to prevent alg:none or algorithm confusion attacks.
    """
    if not token or not isinstance(token, str):
        return None

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
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
# Persistent Conversations & Messages
# ============================================================

def generate_conversation_title(question: str) -> str:
    """Generate a clean, deterministic title for a conversation from the first question."""
    if not question or not question.strip():
        return "New Conversation"

    cleaned = question.strip()

    # Remove common conversational prefixes
    prefixes = [
        "what is the", "what are the", "what is", "what are",
        "how does", "how do", "how to", "can you explain",
        "can you", "could you", "please explain", "please summarize",
        "please tell me about", "please", "explain the", "explain",
        "summarize the", "summarize", "tell me about", "give me"
    ]
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix + " "):
            cleaned = cleaned[len(prefix):].strip()
            break

    # Strip punctuation characters at ends
    cleaned = cleaned.strip("?:!.,;\"' \t\n\r")
    if not cleaned:
        cleaned = question.strip()

    words = cleaned.split()
    if not words:
        return "New Conversation"

    # Take first 6-7 words up to 60 characters
    title_words = words[:7]
    title = " ".join(title_words)
    if len(title) > 60:
        title = title[:60].rsplit(" ", 1)[0]

    if not title:
        title = "New Conversation"

    return title[0].upper() + title[1:] if len(title) > 1 else title.upper()


def create_conversation(user_id: int, title: str = "New Conversation") -> Dict[str, Any]:
    """Create a new conversation belonging to the specified user."""
    title = (title or "New Conversation").strip()
    if len(title) > 100:
        title = title[:100]

    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO conversations (user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, title, now, now),
        )
        connection.commit()
        conv_id = cursor.lastrowid
        return {
            "id": conv_id,
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        connection.close()


def get_user_conversations(user_id: int) -> list:
    """Return all conversations for a user, sorted by updated_at descending (metadata only)."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_conversation(conversation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full conversation metadata, documents, and messages with ownership verification."""
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()

        if row is None:
            return None

        conv = dict(row)

        # Retrieve valid user documents attached to this conversation
        doc_rows = connection.execute(
            """
            SELECT cd.filename
            FROM conversation_documents cd
            JOIN documents d ON cd.filename = d.filename AND d.user_id = ?
            WHERE cd.conversation_id = ?
            ORDER BY cd.id ASC
            """,
            (user_id, conversation_id),
        ).fetchall()
        conv["documents"] = [r["filename"] for r in doc_rows]

        # Retrieve all messages in chronological order
        msg_rows = connection.execute(
            """
            SELECT id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()
        conv["messages"] = [dict(m) for m in msg_rows]

        return conv
    finally:
        connection.close()


def update_conversation_title(conversation_id: int, user_id: int, title: str) -> bool:
    """Rename a conversation with ownership validation."""
    title = (title or "").strip()
    if not title:
        raise ValueError("Title cannot be empty.")
    if len(title) > 100:
        title = title[:100]

    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, now, conversation_id, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def delete_conversation(conversation_id: int, user_id: int) -> bool:
    """Delete a conversation, cascading messages and document mappings while preserving uploaded files."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            DELETE FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def save_message(conversation_id: int, role: str, content: str) -> int:
    """Persist a message (user or assistant) into the conversation history."""
    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, now),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def touch_conversation(conversation_id: int, user_id: int) -> None:
    """Update conversation updated_at timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (now, conversation_id, user_id),
        )
        connection.commit()
    finally:
        connection.close()


def set_conversation_documents(conversation_id: int, user_id: int, filenames: list) -> None:
    """Persist selected documents associated with a conversation, verifying user ownership."""
    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        # Clear existing mappings for this conversation
        connection.execute(
            "DELETE FROM conversation_documents WHERE conversation_id = ?",
            (conversation_id,),
        )

        if filenames:
            # Only associate filenames that actually belong to this user
            placeholders = ",".join(["?"] * len(filenames))
            valid_rows = connection.execute(
                f"""
                SELECT filename FROM documents
                WHERE user_id = ? AND filename IN ({placeholders})
                """,
                [user_id] + list(filenames),
            ).fetchall()
            valid_filenames = [r["filename"] for r in valid_rows]

            for fname in valid_filenames:
                connection.execute(
                    """
                    INSERT INTO conversation_documents (conversation_id, filename, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (conversation_id, fname, now),
                )

        connection.commit()
    finally:
        connection.close()


# ============================================================


# ============================================================
# Document Privacy Functions
# ============================================================

def update_document_privacy(
    filename: str,
    user_id: int,
    privacy_risk: str,
    privacy_details: Optional[str] = None
) -> bool:
    """Update privacy risk and findings for a user document."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            UPDATE documents
            SET privacy_risk = ?, privacy_details = ?
            WHERE filename = ? AND user_id = ?
            """,
            (privacy_risk, privacy_details, filename, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def get_document_privacy(
    filename: str,
    user_id: int
) -> Optional[Dict[str, Any]]:
    """Retrieve privacy info for a specific user document."""
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT filename, privacy_risk, privacy_details
            FROM documents
            WHERE filename = ? AND user_id = ?
            """,
            (filename, user_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()

# Initialize Database on Module Import
# ============================================================

init_auth_db()
