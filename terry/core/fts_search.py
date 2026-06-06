"""FTS5 full-text search for conversation history.

Provides fast full-text search across conversation archives
using SQLite FTS5 for instant multi-keyword queries.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class FTSSearch:
    """Full-text search over conversation history using SQLite FTS5."""

    MAX_CONVERSATIONS = 10_000

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path.home() / ".terry" / "conversations.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the FTS5 database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations
            USING fts5(
                session_id,
                role,
                content,
                timestamp,
                tokenize='porter unicode61'
            )
        """)
        conn.commit()
        conn.close()

    def index_message(
        self, session_id: str, role: str, content: str, timestamp: str | None = None
    ) -> None:
        """Index a single message for search."""
        ts = timestamp or datetime.now().isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, ts),
        )
        conn.commit()

        # Prune old entries
        count = conn.execute(
            "SELECT COUNT(*) FROM conversations"
        ).fetchone()[0]
        if count > self.MAX_CONVERSATIONS:
            conn.execute(
                "DELETE FROM conversations WHERE rowid IN ("
                "  SELECT rowid FROM conversations "
                "  ORDER BY timestamp ASC "
                f" LIMIT {count - self.MAX_CONVERSATIONS}"
                ")"
            )
            conn.commit()
        conn.close()

    def search(
        self,
        query: str,
        limit: int = 20,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text search across conversations.

        Args:
            query: Search query
            limit: Max results
            session_id: Optional filter by session

        Returns:
            List of matching messages
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            if session_id:
                results = conn.execute(
                    "SELECT session_id, role, content, timestamp, rank "
                    "FROM conversations "
                    "WHERE conversations MATCH ? AND session_id = ? "
                    "ORDER BY rank "
                    "LIMIT ?",
                    (query, session_id, limit),
                ).fetchall()
            else:
                results = conn.execute(
                    "SELECT session_id, role, content, timestamp, rank "
                    "FROM conversations "
                    "WHERE conversations MATCH ? "
                    "ORDER BY rank "
                    "LIMIT ?",
                    (query, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            # FTS5 syntax error — try simple LIKE search
            results = conn.execute(
                "SELECT session_id, role, content, timestamp, 0 as rank "
                "FROM conversations "
                "WHERE content LIKE ? "
                "ORDER BY timestamp DESC "
                "LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "session_id": r[0],
                "role": r[1],
                "content": r[2][:500],  # Preview
                "timestamp": r[3],
                "rank": r[4],
            }
            for r in results
        ]

    def get_session_messages(self, session_id: str) -> list[dict[str, str]]:
        """Get all messages for a session."""
        conn = sqlite3.connect(str(self.db_path))
        results = conn.execute(
            "SELECT role, content, timestamp "
            "FROM conversations "
            "WHERE session_id = ? "
            "ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        conn.close()

        return [
            {"role": r[0], "content": r[1], "timestamp": r[2]}
            for r in results
        ]

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent sessions."""
        conn = sqlite3.connect(str(self.db_path))
        results = conn.execute(
            "SELECT session_id, MIN(timestamp), COUNT(*) "
            "FROM conversations "
            "GROUP BY session_id "
            "ORDER BY MIN(timestamp) DESC "
            "LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()

        return [
            {
                "session_id": r[0],
                "started_at": r[1],
                "message_count": r[2],
            }
            for r in results
        ]

    def clear_session(self, session_id: str) -> int:
        """Delete all messages for a session. Returns count deleted."""
        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()
        return count
