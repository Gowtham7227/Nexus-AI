import os
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

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

import threading

_thread_local = threading.local()

import random
import time
from functools import wraps
from typing import Optional, Dict, Any, List, Tuple, Union

def retry_on_db_lock(max_retries: int = 5, initial_delay: float = 0.02, max_delay: float = 0.25):
    """
    Decorator to safely retry SQLite write transactions when experiencing contention (locked/busy).
    Uses exponential backoff with random jitter to prevent thundering herd under high concurrency.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    err_msg = str(e).lower()
                    if ("locked" in err_msg or "busy" in err_msg) and attempt < max_retries - 1:
                        time.sleep(delay + random.uniform(0.005, 0.025))
                        delay = min(delay * 2, max_delay)
                        continue
                    raise
        return wrapper
    return decorator

def get_connection():
    conn = getattr(_thread_local, "connection", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            conn = None
            _thread_local.connection = None

    conn = sqlite3.connect(AUTH_DB, timeout=10.0, check_same_thread=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _thread_local.connection = conn
    return conn


def init_auth_db():
    """
    Initialize users, documents, conversations, messages, and conversation_documents tables automatically.
    Perform non-destructive schema migrations for existing databases.
    """
    connection = get_connection()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 5000")
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
                content_hash TEXT,
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

        # 6. AI Request Metrics (Telemetry & Observability)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_request_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                conversation_id INTEGER,
                timestamp TEXT NOT NULL,
                query_type TEXT,
                optimizer_strategy TEXT,
                retrieval_ms REAL,
                chroma_ms REAL,
                bm25_ms REAL,
                cross_encoder_ms REAL,
                compression_ms REAL,
                ttft_ms REAL,
                generation_ms REAL,
                total_ms REAL,
                context_tokens INTEGER,
                output_tokens INTEGER,
                citation_count INTEGER DEFAULT 0,
                grounding_score REAL,
                model TEXT,
                streaming INTEGER DEFAULT 0,
                cache_hit INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
            )
            """
        )

        # 7. User Message Feedback Loop
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS message_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                conversation_id INTEGER,
                message_id INTEGER,
                request_id TEXT,
                rating INTEGER NOT NULL,
                feedback_reason TEXT,
                reason TEXT,
                feedback_text TEXT,
                latency_perceived TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
            """
        )

        # 8. AI Response Cache (Tenant-Isolated & Document-Fingerprinted)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_response_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                conversation_id INTEGER,
                normalized_query TEXT NOT NULL,
                document_fingerprint TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT DEFAULT 'v1.1',
                optimizer_version TEXT DEFAULT 'v1.1',
                answer TEXT NOT NULL,
                citations_json TEXT,
                grounding_json TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                last_accessed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # 9. Indexes for high performance & fast analytical querying
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
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_user_time ON ai_request_metrics(user_id, timestamp DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_user_query ON ai_request_metrics(user_id, query_type)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_user_model ON ai_request_metrics(user_id, model)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_request_id ON ai_request_metrics(request_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_user_conv ON message_feedback(user_id, conversation_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_msg ON message_feedback(message_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_key ON ai_response_cache(cache_key)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_user_expires ON ai_response_cache(user_id, expires_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_user_doc ON ai_response_cache(user_id, document_fingerprint)"
        )

        # 10. Schema migration: check for missing columns in existing documents table
        cursor = connection.execute("PRAGMA table_info(documents)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        col_defs = {
            "original_filename": "TEXT",
            "file_size": "INTEGER DEFAULT 0",
            "file_type": "TEXT",
            "content_hash": "TEXT",
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

        # 11. Schema migration for message_feedback table
        try:
            fb_cursor = connection.execute("PRAGMA table_info(message_feedback)")
            existing_fb_cols = {row["name"] for row in fb_cursor.fetchall()}
            fb_col_defs = {
                "feedback_reason": "TEXT",
                "reason": "TEXT",
                "feedback_text": "TEXT",
                "latency_perceived": "TEXT",
            }
            for col_name, col_type in fb_col_defs.items():
                if col_name not in existing_fb_cols:
                    try:
                        connection.execute(f"ALTER TABLE message_feedback ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass
        except Exception:
            pass

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

@retry_on_db_lock()
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


@retry_on_db_lock()
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


def is_token_expired(exp_timestamp: Optional[Union[int, float]]) -> bool:
    """Check if a JWT exp timestamp (in epoch seconds) has expired."""
    if not exp_timestamp:
        return False
    return datetime.now(timezone.utc).timestamp() >= float(exp_timestamp)

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
            "exp": payload.get("exp"),
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


@retry_on_db_lock()
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


@retry_on_db_lock()
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


@retry_on_db_lock()
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


@retry_on_db_lock()
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


@retry_on_db_lock()
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


@retry_on_db_lock()
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


# ============================================================
# Telemetry & Observability Functions
# ============================================================

@retry_on_db_lock()
def record_ai_metric(
    request_id: str,
    user_id: int,
    conversation_id: Optional[int] = None,
    query_type: Optional[str] = None,
    optimizer_strategy: Optional[str] = None,
    retrieval_ms: Optional[float] = None,
    chroma_ms: Optional[float] = None,
    bm25_ms: Optional[float] = None,
    cross_encoder_ms: Optional[float] = None,
    compression_ms: Optional[float] = None,
    ttft_ms: Optional[float] = None,
    generation_ms: Optional[float] = None,
    total_ms: Optional[float] = None,
    context_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    citation_count: int = 0,
    grounding_score: Optional[float] = None,
    model: Optional[str] = None,
    streaming: int = 0,
    cache_hit: int = 0,
    status: str = "success",
) -> Optional[int]:
    """
    Safely records an AI request telemetry metric in SQLite.
    Never throws exceptions so telemetry failure NEVER breaks chat.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        connection = get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT INTO ai_request_metrics (
                    request_id, user_id, conversation_id, timestamp,
                    query_type, optimizer_strategy, retrieval_ms, chroma_ms, bm25_ms,
                    cross_encoder_ms, compression_ms, ttft_ms, generation_ms, total_ms,
                    context_tokens, output_tokens, citation_count, grounding_score,
                    model, streaming, cache_hit, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id, user_id, conversation_id, now,
                    query_type, optimizer_strategy, retrieval_ms, chroma_ms, bm25_ms,
                    cross_encoder_ms, compression_ms, ttft_ms, generation_ms, total_ms,
                    context_tokens, output_tokens, citation_count, grounding_score,
                    model, streaming, cache_hit, status,
                ),
            )
            connection.commit()
            return cursor.lastrowid
        except Exception:
            raise
    except Exception as e:
        print(f"[TELEMETRY WARNING] Failed to record AI metric: {e}")
        return None


def get_user_analytics_summary(user_id: int, days: int = 7) -> Dict[str, Any]:
    """Calculate aggregate telemetry overview metrics for the authenticated user."""
    safe_days = max(1, min(int(days), 90))
    since = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
    connection = get_connection()
    try:
        # 1. Metric aggregates
        row = connection.execute(
            """
            SELECT
                COUNT(*) as total_queries,
                AVG(total_ms) as avg_total_latency,
                AVG(retrieval_ms) as avg_retrieval_latency,
                AVG(CASE WHEN streaming = 1 AND ttft_ms IS NOT NULL THEN ttft_ms ELSE NULL END) as avg_ttft,
                AVG(CASE WHEN grounding_score IS NOT NULL THEN grounding_score ELSE NULL END) as avg_grounding,
                SUM(citation_count) as total_citations,
                SUM(cache_hit) as total_cache_hits,
                SUM(streaming) as total_streaming_queries,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as total_errors
            FROM ai_request_metrics
            WHERE user_id = ? AND timestamp >= ?
            """,
            (user_id, since),
        ).fetchone()

        total_queries = int(row["total_queries"] or 0)
        avg_total_latency = round(float(row["avg_total_latency"]), 2) if row["avg_total_latency"] is not None else 0.0
        avg_retrieval_latency = round(float(row["avg_retrieval_latency"]), 2) if row["avg_retrieval_latency"] is not None else 0.0
        avg_ttft = round(float(row["avg_ttft"]), 2) if row["avg_ttft"] is not None else 0.0
        avg_grounding = round(float(row["avg_grounding"]), 4) if row["avg_grounding"] is not None else 1.0
        total_citations = int(row["total_citations"] or 0)
        total_cache_hits = int(row["total_cache_hits"] or 0)
        total_streaming_queries = int(row["total_streaming_queries"] or 0)
        total_errors = int(row["total_errors"] or 0)

        cache_hit_rate = round((total_cache_hits / total_queries) * 100.0, 2) if total_queries > 0 else 0.0
        streaming_rate = round((total_streaming_queries / total_queries) * 100.0, 2) if total_queries > 0 else 0.0

        # 2. Feedback stats
        fb_row = connection.execute(
            """
            SELECT
                SUM(CASE WHEN rating IN ('helpful', '1', 1) THEN 1 ELSE 0 END) as helpful_count,
                SUM(CASE WHEN rating IN ('unhelpful', '-1', -1) THEN 1 ELSE 0 END) as unhelpful_count
            FROM message_feedback
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, since),
        ).fetchone()

        helpful_count = int(fb_row["helpful_count"] or 0)
        unhelpful_count = int(fb_row["unhelpful_count"] or 0)
        total_feedback = helpful_count + unhelpful_count
        satisfaction = round((helpful_count / total_feedback) * 100.0, 1) if total_feedback > 0 else 100.0

        # 3. Documents count & cache entries
        doc_count_row = connection.execute(
            "SELECT COUNT(*) as doc_count FROM documents WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        doc_count = int(doc_count_row["doc_count"] or 0)

        now_iso = datetime.now(timezone.utc).isoformat()
        cache_row = connection.execute(
            "SELECT COUNT(*) as active_cache FROM ai_response_cache WHERE user_id = ? AND expires_at > ?",
            (user_id, now_iso),
        ).fetchone()
        active_cache = int(cache_row["active_cache"] or 0)

        return {
            "time_window_days": safe_days,
            "total_queries": total_queries,
            "total_requests": total_queries,
            "avg_total_latency_ms": avg_total_latency,
            "avg_total_ms": avg_total_latency,
            "avg_retrieval_latency_ms": avg_retrieval_latency,
            "avg_retrieval_ms": avg_retrieval_latency,
            "avg_ttft_ms": avg_ttft,
            "avg_grounding_score": avg_grounding,
            "total_citations": total_citations,
            "total_cache_hits": total_cache_hits,
            "cache_hits": total_cache_hits,
            "cache_hit_rate_pct": cache_hit_rate,
            "cache_hit_ratio": cache_hit_rate,
            "streaming_percentage": streaming_rate,
            "streaming_requests": total_streaming_queries,
            "error_count": total_errors,
            "feedback_helpful_count": helpful_count,
            "feedback_unhelpful_count": unhelpful_count,
            "total_feedback": total_feedback,
            "satisfaction_ratio": satisfaction,
            "total_documents": doc_count,
            "active_cache_entries": active_cache,
        }
    finally:
        connection.close()


def get_user_latency_series(user_id: int, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve time-series latency breakdown points for telemetry charts."""
    safe_days = max(1, min(int(days), 90))
    limit = max(1, min(int(limit), 200))
    since = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                id, request_id, timestamp, query_type, model,
                retrieval_ms, cross_encoder_ms, generation_ms, total_ms, ttft_ms,
                cache_hit, streaming
            FROM ai_request_metrics
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, since, limit),
        ).fetchall()
        result = []
        for r in reversed(rows):
            d = dict(r)
            d["created_at"] = d["timestamp"]
            result.append(d)
        return result
    finally:
        connection.close()


def get_user_rag_distribution(user_id: int, days: int = 7) -> Dict[str, Any]:
    """Retrieve query type classification distribution and optimizer strategies."""
    safe_days = max(1, min(int(days), 90))
    since = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
    connection = get_connection()
    try:
        # Query types breakdown
        qt_rows = connection.execute(
            """
            SELECT query_type, COUNT(*) as count, AVG(grounding_score) as avg_grounding, AVG(total_ms) as avg_latency
            FROM ai_request_metrics
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY query_type
            ORDER BY count DESC
            """,
            (user_id, since),
        ).fetchall()

        # Optimizer strategies breakdown
        st_rows = connection.execute(
            """
            SELECT optimizer_strategy, COUNT(*) as count
            FROM ai_request_metrics
            WHERE user_id = ? AND timestamp >= ? AND optimizer_strategy IS NOT NULL
            GROUP BY optimizer_strategy
            ORDER BY count DESC
            """,
            (user_id, since),
        ).fetchall()

        # Grounding quality brackets
        g_row = connection.execute(
            """
            SELECT
                SUM(CASE WHEN grounding_score >= 0.8 THEN 1 ELSE 0 END) as high_grounding,
                SUM(CASE WHEN grounding_score >= 0.5 AND grounding_score < 0.8 THEN 1 ELSE 0 END) as medium_grounding,
                SUM(CASE WHEN grounding_score < 0.5 THEN 1 ELSE 0 END) as low_grounding
            FROM ai_request_metrics
            WHERE user_id = ? AND timestamp >= ? AND grounding_score IS NOT NULL
            """,
            (user_id, since),
        ).fetchone()

        query_types_dict = {r["query_type"]: r["count"] for r in qt_rows if r["query_type"]}
        strategies_dict = {r["optimizer_strategy"]: r["count"] for r in st_rows if r["optimizer_strategy"]}

        return {
            "query_types": query_types_dict,
            "strategies": strategies_dict,
            "query_types_list": [dict(r) for r in qt_rows],
            "optimizer_strategies": [dict(r) for r in st_rows],
            "grounding_brackets": {
                "high": int(g_row["high_grounding"] or 0),
                "medium": int(g_row["medium_grounding"] or 0),
                "low": int(g_row["low_grounding"] or 0),
            },
        }
    finally:
        connection.close()


def get_user_model_stats(user_id: int, days: int = 7) -> List[Dict[str, Any]]:
    """Retrieve model usage breakdown and cache effectiveness."""
    safe_days = max(1, min(int(days), 90))
    since = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
    connection = get_connection()
    try:
        model_rows = connection.execute(
            """
            SELECT
                model,
                COUNT(*) as count,
                AVG(total_ms) as avg_total_ms,
                AVG(CASE WHEN streaming = 1 THEN ttft_ms ELSE NULL END) as avg_ttft_ms
            FROM ai_request_metrics
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY model
            ORDER BY count DESC
            """,
            (user_id, since),
        ).fetchall()

        results = []
        for r in model_rows:
            d = dict(r)
            d["request_count"] = d["count"]
            results.append(d)
        return results
    finally:
        connection.close()


# ============================================================
# User Feedback Functions
# ============================================================

ALLOWED_FEEDBACK_RATINGS = {"helpful", "unhelpful", "1", "-1", 1, -1}
ALLOWED_FEEDBACK_REASONS = {
    "accurate",
    "fast",
    "helpful",
    "good_citations",
    "hallucination",
    "missing_info",
    "slow",
    "poor_citations",
    "incorrect_facts",
    "refused_answer",
    "incorrect_answer",
    "missing_information",
    "poor_citation",
    "irrelevant_sources",
    "too_verbose",
    "other",
}

@retry_on_db_lock()
def save_message_feedback(
    user_id: int,
    conversation_id: int,
    rating: Any,
    message_id: Optional[int] = None,
    feedback_reason: Optional[str] = None,
    reason: Optional[str] = None,
    feedback_text: Optional[str] = None,
    note: Optional[str] = None,
    latency_perceived: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Optional[int]:
    """
    Save or update user feedback for an assistant message with strict validation.
    Returns integer feedback_id on success, or None on failure.
    """
    if rating not in ALLOWED_FEEDBACK_RATINGS:
        return None

    # Normalize rating representation
    norm_rating = 1 if rating in (1, "1", "helpful") else -1

    chosen_reason = feedback_reason or reason
    if chosen_reason:
        chosen_reason = str(chosen_reason).strip().lower()
        if chosen_reason not in ALLOWED_FEEDBACK_REASONS:
            return None
    else:
        chosen_reason = "accurate" if norm_rating == 1 else "other"

    chosen_text = feedback_text or note
    if chosen_text:
        chosen_text = str(chosen_text).strip()[:1000]

    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        # Validate conversation belongs to authenticated user
        conv = connection.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if conv is None:
            return None

        # Resolve message_id if omitted (attach to latest assistant message in conversation)
        if message_id is None:
            last_msg = connection.execute(
                "SELECT id FROM messages WHERE conversation_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if last_msg:
                message_id = last_msg["id"]
        else:
            # Validate that the provided message_id actually belongs to this conversation
            msg_check = connection.execute(
                "SELECT id FROM messages WHERE id = ? AND conversation_id = ?",
                (message_id, conversation_id),
            ).fetchone()
            if msg_check is None:
                return None

        # Check existing feedback
        existing = None
        if message_id is not None:
            existing = connection.execute(
                "SELECT id FROM message_feedback WHERE user_id = ? AND message_id = ?",
                (user_id, message_id),
            ).fetchone()

        if existing:
            connection.execute(
                """
                UPDATE message_feedback
                SET rating = ?, feedback_reason = ?, feedback_text = ?, latency_perceived = ?, request_id = COALESCE(?, request_id), updated_at = ?
                WHERE id = ?
                """,
                (norm_rating, chosen_reason, chosen_text, latency_perceived, request_id, now, existing["id"]),
            )
            feedback_id = existing["id"]
        else:
            cursor = connection.execute(
                """
                INSERT INTO message_feedback (user_id, conversation_id, message_id, request_id, rating, feedback_reason, feedback_text, latency_perceived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, conversation_id, message_id, request_id, norm_rating, chosen_reason, chosen_text, latency_perceived, now, now),
            )
            feedback_id = cursor.lastrowid

        connection.commit()
        return feedback_id
    except Exception as e:
        print(f"[FEEDBACK ERROR]: {e}")
        return None
    finally:
        connection.close()


def get_conversation_feedback(arg1: int, arg2: int) -> List[Dict[str, Any]]:
    """Retrieve all feedback submitted for a conversation."""
    connection = get_connection()
    try:
        # Determine which parameter is conversation_id and which is user_id
        # Check if conversation exists for arg1 as conv_id and arg2 as user_id
        c1 = connection.execute("SELECT id, user_id FROM conversations WHERE id = ? AND user_id = ?", (arg1, arg2)).fetchone()
        if c1:
            conv_id, u_id = arg1, arg2
        else:
            c2 = connection.execute("SELECT id, user_id FROM conversations WHERE id = ? AND user_id = ?", (arg2, arg1)).fetchone()
            if c2:
                conv_id, u_id = arg2, arg1
            else:
                return []

        rows = connection.execute(
            """
            SELECT id, user_id, conversation_id, message_id, request_id, rating, feedback_reason, feedback_text, latency_perceived, created_at, updated_at
            FROM message_feedback
            WHERE user_id = ? AND conversation_id = ?
            ORDER BY id ASC
            """,
            (u_id, conv_id),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["rating"] = int(d["rating"])
            except (ValueError, TypeError):
                d["rating"] = 1 if d["rating"] in ("helpful", "1") else -1
            d["feedback_reason"] = d["feedback_reason"] or d.get("reason")
            d["reason"] = d["feedback_reason"]
            result.append(d)
        return result
    finally:
        connection.close()


# ============================================================
# Response Cache Functions
# ============================================================

def compute_document_fingerprint(user_id: int, filenames: List[str]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a list of document filenames.
    Changes whenever file metadata (content hash, size, upload timestamp) changes.
    """
    if not filenames:
        return "none"

    clean_names = sorted(list(set(filenames)))
    connection = get_connection()
    try:
        placeholders = ",".join("?" for _ in clean_names)
        rows = connection.execute(
            f"""
            SELECT filename, file_size, created_at, content_hash
            FROM documents
            WHERE user_id = ? AND filename IN ({placeholders})
            ORDER BY filename ASC
            """,
            [user_id] + clean_names,
        ).fetchall()

        parts = []
        for r in rows:
            h = r["content_hash"] if ("content_hash" in r.keys() and r["content_hash"]) else r["created_at"]
            parts.append(f"{r['filename']}:{r['file_size']}:{h}")

        raw = "|".join(parts) if parts else "missing_docs"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    finally:
        connection.close()


def compute_cache_key(
    user_id: int,
    normalized_query: str,
    doc_fingerprint: str,
    model: str,
    prompt_version: str = "v1.1",
    optimizer_version: str = "v1.1",
) -> str:
    """Computes a cryptographically safe cache key partitioned by user and document fingerprint."""
    raw = f"{user_id}|{normalized_query.strip().lower()}|{doc_fingerprint}|{model}|{prompt_version}|{optimizer_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_response(user_id: int, cache_key: str) -> Optional[Dict[str, Any]]:
    """Retrieves an active cached response if available and not expired (pure read for sub-millisecond lookup)."""
    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT id, answer, citations_json, grounding_json, model, created_at, expires_at
            FROM ai_response_cache
            WHERE user_id = ? AND cache_key = ? AND expires_at > ?
            """,
            (user_id, cache_key, now),
        ).fetchone()

        if row is None:
            return None

        citations = json.loads(row["citations_json"]) if row["citations_json"] else []
        grounding = json.loads(row["grounding_json"]) if row["grounding_json"] else None

        return {
            "answer": row["answer"],
            "citations": citations,
            "grounding": grounding,
            "model": row["model"],
            "created_at": row["created_at"],
            "cache_hit": True,
        }
    except Exception as e:
        print(f"[CACHE WARNING] Failed to read from response cache: {e}")
        return None


@retry_on_db_lock()
def set_cached_response(
    user_id: int,
    cache_key: str,
    normalized_query: str,
    doc_fingerprint: str,
    model: str,
    answer: str,
    citations: Optional[List[Any]] = None,
    grounding: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[int] = None,
    prompt_version: str = "v1.1",
    optimizer_version: str = "v1.1",
    ttl_seconds: int = 86400,
) -> bool:
    """Stores an AI response in the response cache with TTL, automatically cleaning up expired entries."""
    try:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
        citations_json = json.dumps(citations or [])
        grounding_json = json.dumps(grounding or {})

        connection = get_connection()
        try:
            # Purge expired cache entries opportunistically to prevent indefinite table growth
            connection.execute(
                "DELETE FROM ai_response_cache WHERE expires_at <= ?",
                (now,),
            )

            connection.execute(
                """
                INSERT INTO ai_response_cache (
                    cache_key, user_id, conversation_id, normalized_query,
                    document_fingerprint, model, prompt_version, optimizer_version,
                    answer, citations_json, grounding_json, created_at, expires_at,
                    hit_count, last_accessed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    answer = excluded.answer,
                    citations_json = excluded.citations_json,
                    grounding_json = excluded.grounding_json,
                    expires_at = excluded.expires_at,
                    last_accessed_at = excluded.last_accessed_at
                """,
                (
                    cache_key, user_id, conversation_id, normalized_query,
                    doc_fingerprint, model, prompt_version, optimizer_version,
                    answer, citations_json, grounding_json, now, expires_at, now
                ),
            )
            connection.commit()
            return True
        except Exception:
            raise
    except Exception as e:
        print(f"[CACHE WARNING] Failed to write to response cache: {e}")
        return False


@retry_on_db_lock()
def invalidate_document_cache(user_id: int, filename: str) -> int:
    """Invalidates all cached responses for a user when a document is modified or deleted."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            "DELETE FROM ai_response_cache WHERE user_id = ?",
            (user_id,),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


@retry_on_db_lock()
def clear_user_response_cache(user_id: int) -> int:
    """Clears all response cache entries for a user."""
    connection = get_connection()
    try:
        cursor = connection.execute(
            "DELETE FROM ai_response_cache WHERE user_id = ?",
            (user_id,),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


# ============================================================
# Initialize Database on Module Import
# ============================================================

init_auth_db()
