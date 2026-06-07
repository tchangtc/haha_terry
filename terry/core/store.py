"""TerryStore — unified persistent data layer.

Consolidates all scattered persistence into a single SQLite-backed store:
  - Memory, Sessions, Feedback, Permissions, Tasks, Checkpoints
  - Key-value config, JSON documents, event log
  - Migration support for version upgrades
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .platform_utils import get_terry_dir


class TerryStore:
    """Unified SQLite-backed persistent store for all Terry data."""

    DB_PATH = get_terry_dir() / "terry.db"
    VERSION = 1

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or self.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS _meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS kv_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                collection TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_kv_namespace ON kv_store(namespace);
            CREATE INDEX IF NOT EXISTS idx_docs_collection ON documents(collection);
            CREATE INDEX IF NOT EXISTS idx_events_type ON event_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON event_log(timestamp);
        """)
        conn.commit()

        # Version check / migration
        current = self._meta_get("schema_version")
        if not current:
            self._meta_set("schema_version", str(self.VERSION))
            self._meta_set("created_at", datetime.now().isoformat())

    # ── Key-Value ───────────────────────────────────────────────────

    def kv_get(self, namespace: str, key: str, default: str = "") -> str:
        row = self._connect().execute(
            "SELECT value FROM kv_store WHERE namespace=? AND key=?",
            (namespace, key)
        ).fetchone()
        return row["value"] if row else default

    def kv_set(self, namespace: str, key: str, value: str) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (namespace, key, value, datetime.now().isoformat())
        )
        conn.commit()

    def kv_delete(self, namespace: str, key: str) -> None:
        self._connect().execute(
            "DELETE FROM kv_store WHERE namespace=? AND key=?", (namespace, key)
        ).connection.commit()

    def kv_list(self, namespace: str) -> dict[str, str]:
        rows = self._connect().execute(
            "SELECT key, value FROM kv_store WHERE namespace=?", (namespace,)
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ── Documents ────────────────────────────────────────────────────

    def doc_save(self, collection: str, doc_id: str, content: str, metadata: dict | None = None) -> None:
        now = datetime.now().isoformat()
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO documents (id, collection, content, created_at, updated_at, metadata) "
            "VALUES (?, ?, ?, COALESCE((SELECT created_at FROM documents WHERE id=?), ?), ?, ?)",
            (doc_id, collection, content, doc_id, now, now, json.dumps(metadata or {}))
        )
        conn.commit()

    def doc_get(self, doc_id: str) -> dict | None:
        row = self._connect().execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def doc_list(self, collection: str) -> list[dict]:
        rows = self._connect().execute(
            "SELECT * FROM documents WHERE collection=? ORDER BY updated_at DESC", (collection,)
        ).fetchall()
        return [dict(r) for r in rows]

    def doc_delete(self, doc_id: str) -> None:
        self._connect().execute("DELETE FROM documents WHERE id=?", (doc_id,)).connection.commit()

    # ── Event Log ────────────────────────────────────────────────────

    def event_log(self, event_type: str, data: dict) -> int:
        cursor = self._connect().execute(
            "INSERT INTO event_log (event_type, data, timestamp) VALUES (?, ?, ?)",
            (event_type, json.dumps(data), datetime.now().isoformat())
        )
        cursor.connection.commit()
        return cursor.lastrowid

    def event_query(self, event_type: str | None = None, limit: int = 100) -> list[dict]:
        if event_type:
            rows = self._connect().execute(
                "SELECT * FROM event_log WHERE event_type=? ORDER BY id DESC LIMIT ?",
                (event_type, limit)
            ).fetchall()
        else:
            rows = self._connect().execute(
                "SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Metadata ─────────────────────────────────────────────────────

    def _meta_get(self, key: str) -> str | None:
        row = self._connect().execute("SELECT value FROM _meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._connect().execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)", (key, value)
        ).connection.commit()

    def stats(self) -> dict:
        conn = self._connect()
        return {
            "db_path": str(self.db_path),
            "kv_entries": conn.execute("SELECT COUNT(*) FROM kv_store").fetchone()[0],
            "documents": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "events": conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0],
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
