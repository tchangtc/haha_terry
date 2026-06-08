"""Non-blocking user feedback collection system.

Inspired by Claude Code's subtle rating prompts, this module provides
asynchronous, non-intrusive feedback collection without blocking the
agent's main execution loop.

Key design:
  - Sampling: only prompts on ~15% of responses (configurable)
  - Non-blocking: uses a background thread, 6-second auto-dismiss
  - Minimalist: single keystroke (y/n) or click (thumbs up/down)
  - Persistent: feedback stored to ~/.terry/feedback.jsonl
  - Privacy-first: all data stays local by default
"""

from __future__ import annotations

import json
import logging
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)


class FeedbackEntry:
    """A single feedback record."""

    def __init__(
        self,
        session_id: str = "",
        rating: str = "",        # "good", "bad", "skip"
        user_message: str = "",
        assistant_response_preview: str = "",
        tool_calls: int = 0,
        duration_ms: float = 0,
        metadata: dict | None = None,
    ):
        self.timestamp = datetime.now().isoformat()
        self.session_id = session_id
        self.rating = rating
        self.user_message = user_message[:500]
        self.assistant_response_preview = assistant_response_preview[:500]
        self.tool_calls = tool_calls
        self.duration_ms = round(duration_ms, 0)
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "rating": self.rating,
            "user_message": self.user_message,
            "assistant_preview": self.assistant_response_preview,
            "tool_calls": self.tool_calls,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class FeedbackCollector:
    """Non-blocking feedback collection engine.

    Usage:
        collector = FeedbackCollector()
        collector.start()

        # After agent response:
        collector.maybe_prompt(
            user_message="Fix auth bug",
            assistant_response="I found the issue in auth.py...",
            tool_calls=3,
            duration_ms=2500,
        )
        # ↑ This returns immediately, feedback is collected in background
    """

    def __init__(
        self,
        config: Any = None,
        storage_path: Path | None = None,
        sample_rate: float | None = None,
        min_interval_seconds: int | None = None,
        auto_dismiss_seconds: int | None = None,
        input_fn: Any = None,           # Custom input function (for testing)
    ):
        # Resolve values from config, then kwargs, then defaults
        if config is not None:
            from .config import TerryConfig
            if isinstance(config, TerryConfig):
                if sample_rate is None:
                    sample_rate = config.feedback_sample_rate
                if min_interval_seconds is None:
                    min_interval_seconds = config.feedback_min_interval
                if auto_dismiss_seconds is None:
                    auto_dismiss_seconds = config.feedback_auto_dismiss

        self.storage_path = storage_path or get_terry_dir() / "feedback.jsonl"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate if sample_rate is not None else 0.15
        self.min_interval_seconds = min_interval_seconds if min_interval_seconds is not None else 30
        self.auto_dismiss_seconds = auto_dismiss_seconds if auto_dismiss_seconds is not None else 6
        self._input_fn = input_fn or input
        self._last_prompt_time: float = 0
        self._stats = {"total_responses": 0, "prompts_shown": 0, "responses": 0,
                       "good": 0, "bad": 0, "skipped": 0}

    def should_prompt(self) -> bool:
        """Determine if a feedback prompt should be shown now.

        Uses probabilistic sampling + rate limiting.
        """
        now = time.time()

        # Rate limit: don't prompt too frequently
        if now - self._last_prompt_time < self.min_interval_seconds:
            return False

        # Probabilistic sampling
        if random.random() > self.sample_rate:
            return False

        return True

    def maybe_prompt(
        self,
        user_message: str = "",
        assistant_response: str = "",
        session_id: str = "",
        tool_calls: int = 0,
        duration_ms: float = 0,
        metadata: dict | None = None,
    ) -> FeedbackEntry | None:
        """Potentially show a feedback prompt (non-blocking).

        Returns immediately — feedback is collected in a background thread
        if the sampling criteria are met.

        Returns:
            FeedbackEntry if prompt was shown, None if skipped by sampling
        """
        self._stats["total_responses"] += 1

        if not self.should_prompt():
            return None

        self._last_prompt_time = time.time()
        self._stats["prompts_shown"] += 1

        # Create entry skeleton
        entry = FeedbackEntry(
            session_id=session_id,
            user_message=user_message,
            assistant_response_preview=assistant_response,
            tool_calls=tool_calls,
            duration_ms=duration_ms,
            metadata=metadata,
        )

        # Collect feedback in background thread (non-blocking)
        thread = threading.Thread(
            target=self._collect_async,
            args=(entry,),
            daemon=True,
        )
        thread.start()

        return entry

    def _collect_async(self, entry: FeedbackEntry) -> None:
        """Background thread: show prompt and wait for response."""
        # Show prompt
        self._show_prompt(entry)

        # Simple blocking read with timeout via threading.Timer
        result = {"rating": "skip"}
        done = threading.Event()

        def get_input():
            try:
                response = self._input_fn(
                    "\033[90m  Was this helpful? [y=yes / n=no / Enter=skip] \033[0m"
                ).strip().lower()
                if response in ("y", "yes", "good", "👍"):
                    result["rating"] = "good"
                elif response in ("n", "no", "bad", "👎"):
                    result["rating"] = "bad"
            except (EOFError, KeyboardInterrupt):
                pass
            finally:
                done.set()

        input_thread = threading.Thread(target=get_input, daemon=True)
        input_thread.start()

        # Wait for input or timeout
        done.wait(timeout=self.auto_dismiss_seconds)

        # Record result
        entry.rating = result["rating"]
        if result["rating"] == "good":
            self._stats["good"] += 1
        elif result["rating"] == "bad":
            self._stats["bad"] += 1
        else:
            self._stats["skipped"] += 1
        self._stats["responses"] += 1

        # Clear the prompt line
        sys.stderr.write("\r\033[K")

        # Save to storage
        self._save(entry)

    def _show_prompt(self, entry: FeedbackEntry) -> None:
        """Display a subtle feedback prompt to stderr (TUI element)."""
        preview = entry.assistant_response_preview[:80].replace("\n", " ")
        sys.stderr.write(f"\n\033[90m┌─ Feedback ─────────────────────────────\033[0m\n")
        sys.stderr.write(f"\033[90m│ Q: {entry.user_message[:60]}\033[0m\n")
        sys.stderr.write(f"\033[90m│ A: {preview}...\033[0m\n")
        sys.stderr.write("\033[90m└────────────────────────────────────────\033[0m\n")

    def _save(self, entry: FeedbackEntry) -> None:
        """Append feedback entry to JSONL storage."""
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def record_direct(self, rating: str, **kwargs) -> FeedbackEntry:
        """Directly record feedback without prompting (for API/WebUI use).

        Args:
            rating: "good", "bad", or "skip"
            **kwargs: Passed to FeedbackEntry constructor

        Returns:
            The recorded FeedbackEntry
        """
        entry = FeedbackEntry(rating=rating, **kwargs)
        if rating == "good":
            self._stats["good"] += 1
        elif rating == "bad":
            self._stats["bad"] += 1
        self._stats["total_responses"] += 1
        self._stats["responses"] += 1
        self._save(entry)
        return entry

    def get_stats(self) -> dict[str, Any]:
        """Get feedback collection statistics."""
        total_rated = self._stats["good"] + self._stats["bad"]
        return {
            **self._stats,
            "satisfaction_rate": (
                f"{self._stats['good'] / max(total_rated, 1):.1%}"
            ),
            "prompt_rate": (
                f"{self._stats['prompts_shown'] / max(self._stats['total_responses'], 1):.1%}"
            ),
            "response_rate": (
                f"{self._stats['responses'] / max(self._stats['prompts_shown'], 1):.1%}"
            ),
        }

    def load_history(self, limit: int = 100) -> list[dict]:
        """Load recent feedback history."""
        entries = []
        try:
            if self.storage_path.exists():
                with open(self.storage_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
        except Exception:
            pass
        return entries[-limit:]


# Global instance
_feedback_instance: FeedbackCollector | None = None


def get_feedback_collector(**kwargs) -> FeedbackCollector:
    global _feedback_instance
    if _feedback_instance is None:
        _feedback_instance = FeedbackCollector(**kwargs)
    return _feedback_instance


def set_feedback_collector(instance: FeedbackCollector) -> None:
    global _feedback_instance
    _feedback_instance = instance


def reset_feedback_collector() -> None:
    global _feedback_instance
    _feedback_instance = None
