import sqlite3
from datetime import datetime, timezone

c = sqlite3.connect("auth.db")

c.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

c.commit()

print("Documents table created successfully.")

c.close()
