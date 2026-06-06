"""Session management - save and restore conversation state."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class Session:
    """Manages conversation sessions with persistence."""

    def __init__(self, session_dir: Path | None = None):
        self.session_dir = session_dir or Path.home() / ".terry" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.session_id: str | None = None
        self.messages: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {
            "created_at": None,
            "updated_at": None,
            "tool_calls": 0,
            "tokens_used": 0,
        }

    def new(self, session_id: str | None = None) -> str:
        """Create a new session.

        Args:
            session_id: Optional custom session ID

        Returns:
            Session ID
        """
        if session_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"session_{timestamp}"

        self.session_id = session_id
        self.messages = []
        self.metadata = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "tool_calls": 0,
            "tokens_used": 0,
        }

        self._save()
        return session_id

    def load(self, session_id: str) -> bool:
        """Load an existing session.

        Args:
            session_id: Session ID to load

        Returns:
            True if loaded successfully
        """
        session_file = self.session_dir / f"{session_id}.json"

        if not session_file.exists():
            return False

        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            self.session_id = session_id
            self.messages = data.get("messages", [])
            self.metadata = data.get("metadata", {})
            return True
        except Exception:
            return False

    def save(self) -> bool:
        """Save current session to disk.

        Returns:
            True if saved successfully
        """
        if not self.session_id:
            return False

        self.metadata["updated_at"] = datetime.now().isoformat()
        return self._save()

    def _save(self) -> bool:
        """Internal save method."""
        if not self.session_id:
            return False

        session_file = self.session_dir / f"{self.session_id}.json"

        try:
            data = {
                "session_id": self.session_id,
                "messages": self.messages,
                "metadata": self.metadata,
            }
            session_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False

    def add_message(self, role: str, content: Any) -> None:
        """Add a message to the session.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_messages(self) -> list[dict[str, Any]]:
        """Get all messages in the session.

        Returns:
            List of messages
        """
        return self.messages

    def clear(self) -> None:
        """Clear all messages but keep session ID."""
        self.messages = []
        self.metadata["updated_at"] = datetime.now().isoformat()

    def increment_tool_calls(self, count: int = 1) -> None:
        """Increment tool call counter.

        Args:
            count: Number of tool calls to add
        """
        self.metadata["tool_calls"] = self.metadata.get("tool_calls", 0) + count

    def add_tokens(self, tokens: int) -> None:
        """Add to token usage counter.

        Args:
            tokens: Number of tokens used
        """
        self.metadata["tokens_used"] = self.metadata.get("tokens_used", 0) + tokens

    @staticmethod
    def list_sessions(session_dir: Path | None = None) -> list[dict[str, Any]]:
        """List all available sessions.

        Args:
            session_dir: Optional session directory override

        Returns:
            List of session metadata
        """
        if session_dir is None:
            session_dir = Path.home() / ".terry" / "sessions"

        if not session_dir.exists():
            return []

        sessions = []
        for session_file in session_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id"),
                    "created_at": data.get("metadata", {}).get("created_at"),
                    "updated_at": data.get("metadata", {}).get("updated_at"),
                    "message_count": len(data.get("messages", [])),
                    "tool_calls": data.get("metadata", {}).get("tool_calls", 0),
                })
            except Exception:
                continue

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    def delete(self) -> bool:
        """Delete current session.

        Returns:
            True if deleted successfully
        """
        if not self.session_id:
            return False

        session_file = self.session_dir / f"{self.session_id}.json"

        try:
            if session_file.exists():
                session_file.unlink()
            self.session_id = None
            self.messages = []
            self.metadata = {}
            return True
        except Exception:
            return False


# Global session instance
_session_instance: Session | None = None


def get_session(session_dir: Path | None = None) -> Session:
    """Get or create the global session instance.

    Args:
        session_dir: Optional session directory override

    Returns:
        Session instance
    """
    global _session_instance
    if _session_instance is None:
        _session_instance = Session(session_dir)
    return _session_instance


def set_session(instance: Session) -> None:
    """Inject a custom Session instance (for testing/DI)."""
    global _session_instance
    _session_instance = instance


def reset_session() -> None:
    """Reset session singleton (forces re-initialization on next get)."""
    global _session_instance
    _session_instance = None
