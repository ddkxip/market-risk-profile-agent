import sqlite3
import os
import json
from datetime import datetime

class SessionStore:
    def __init__(self, db_name="sessions.db"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Store database in the workspace cache or config folder
        db_dir = os.path.join(base_dir, ".cache")
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, db_name)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_metadata (
                session_id TEXT PRIMARY KEY,
                last_ticker TEXT,
                user_preferences TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def save_message(self, session_id: str, role: str, content: str):
        """Saves a message in the session history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO session_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()
        conn.close()

    def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """Retrieves message history for a session, returning the most recent messages in chronological order."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Retrieve the latest messages first by auto-incrementing id (DESC)
        cursor.execute(
            "SELECT role, content FROM session_messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        # Reverse them so they are chronologically ordered (oldest to newest)
        history = [{"role": r["role"], "content": r["content"]} for r in rows]
        history.reverse()
        return history

    def update_metadata(self, session_id: str, last_ticker: str = None, prefs: dict = None):
        """Updates session-wide metadata such as the last analyzed ticker."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT session_id FROM session_metadata WHERE session_id = ?", (session_id,))
        exists = cursor.fetchone()
        
        prefs_json = json.dumps(prefs) if prefs else "{}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if exists:
            if last_ticker:
                cursor.execute(
                    "UPDATE session_metadata SET last_ticker = ?, updated_at = ? WHERE session_id = ?",
                    (last_ticker, now, session_id)
                )
            if prefs:
                cursor.execute(
                    "UPDATE session_metadata SET user_preferences = ?, updated_at = ? WHERE session_id = ?",
                    (prefs_json, now, session_id)
                )
        else:
            cursor.execute(
                "INSERT INTO session_metadata (session_id, last_ticker, user_preferences, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, last_ticker or "", prefs_json, now)
            )
            
        conn.commit()
        conn.close()

    def get_metadata(self, session_id: str) -> dict:
        """Retrieves session-wide metadata."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT last_ticker, user_preferences FROM session_metadata WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "last_ticker": row["last_ticker"],
                "preferences": json.loads(row["user_preferences"] or "{}")
            }
        return {"last_ticker": None, "preferences": {}}

    def clear_history(self, session_id: str):
        """Clears all message history for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
