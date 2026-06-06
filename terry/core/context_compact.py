"""4-layer context compaction system — cheap first, expensive last.

Layers (executed in order before each LLM call):
  1. Budget  — persist large (>50K) tool outputs to disk, replace with [stored] marker
  2. Snip    — trim middle messages, keep head + tail windows
  3. Micro   — compress old tool results into terse [tool:name → result_summary] format
  4. Auto    — LLM-assisted summarization of oldest messages

Design: Each layer is independent and idempotent. Execute 1→4 sequentially.
If layer N brings context below threshold, skip layers N+1..4.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .text_utils import extract_text


class ContextCompactor:
    """4-layer progressive context compaction."""

    def __init__(
        self,
        max_tokens: int = 200000,
        compression_threshold: float = 0.75,
        keep_recent: int = 10,
        budget_dir: Path | None = None,
    ):
        self.max_tokens = max_tokens
        self.compression_threshold = compression_threshold
        self.keep_recent = keep_recent
        self.budget_dir = budget_dir or Path.home() / ".terry" / "budget"
        self.budget_dir.mkdir(parents=True, exist_ok=True)

        # Configurable limits
        self.BUDGET_LIMIT = 50_000   # chars — persist outputs larger than this
        self.SNIP_HEAD = 3           # keep first N messages
        self.SNIP_TAIL = 7           # keep last N messages
        self.MICRO_MAX_LEN = 200     # max chars for micro result summary

    # ── token estimation ──────────────────────────────────────────

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Rough token count: 1 token ≈ 4 characters."""
        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        return total_chars // 4

    def needs_compaction(self, messages: list[dict[str, Any]]) -> bool:
        """Check if any compaction layer is needed."""
        tokens = self.estimate_tokens(messages)
        return tokens > int(self.max_tokens * self.compression_threshold)

    # ── public compact() entry point ───────────────────────────────

    def compact(
        self, messages: list[dict[str, Any]], llm_client: Any = None
    ) -> list[dict[str, Any]]:
        """Apply progressive compaction: budget → snip → micro → auto."""
        # Layer 1: Budget (persist large outputs)
        messages = self._budget_compact(messages)
        if not self.needs_compaction(messages):
            return messages

        # Layer 2: Snip (trim middle)
        messages = self._snip_compact(messages)
        if not self.needs_compaction(messages):
            return messages

        # Layer 3: Micro (terse tool results)
        messages = self._micro_compact(messages)
        if not self.needs_compaction(messages):
            return messages

        # Layer 4: Auto (LLM summarization)
        messages = self._auto_compact(messages, llm_client)
        return messages

    # ── Layer 1: Budget ────────────────────────────────────────────

    def _budget_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Persist large tool outputs to disk, replace with [stored] marker."""
        result = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                # Check each block for large tool results
                new_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_content = str(block.get("content", ""))
                        if len(tool_content) > self.BUDGET_LIMIT:
                            stored_path = self._persist_output(tool_content)
                            block = {**block, "content": f"[stored: {stored_path}]"}
                    new_blocks.append(block)
                msg = {**msg, "content": new_blocks}
            result.append(msg)
        return result

    def _persist_output(self, content: str) -> Path:
        """Save large output to disk, return relative path."""
        h = hashlib.sha256(content.encode()).hexdigest()[:12]
        fpath = self.budget_dir / f"output_{h}.txt"
        if not fpath.exists():
            fpath.write_text(content, encoding="utf-8")
        return fpath

    # ── Layer 2: Snip ──────────────────────────────────────────────

    def _snip_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep head + tail, remove middle messages."""
        if len(messages) <= self.SNIP_HEAD + self.SNIP_TAIL:
            return messages

        system_msg = None
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            messages = messages[1:]

        head = messages[:self.SNIP_HEAD]
        tail = messages[-self.SNIP_TAIL:]
        snipped_count = len(messages) - self.SNIP_HEAD - self.SNIP_TAIL

        placeholder = {
            "role": "system",
            "content": f"[{snipped_count} messages snipped for space]",
        }
        result = head + [placeholder] + tail
        if system_msg:
            result = [system_msg] + result
        return result

    # ── Layer 3: Micro ─────────────────────────────────────────────

    def _micro_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress old tool results to terse summaries."""
        result = []
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            if isinstance(content, list) and i < len(messages) - self.keep_recent:
                # Only compress messages that are not in the recent window
                new_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tc = str(block.get("content", ""))
                        summary = tc[:self.MICRO_MAX_LEN].replace("\n", " ")
                        block = {
                            **block,
                            "content": f"[tool_result: {summary}...]" if len(tc) > self.MICRO_MAX_LEN else tc,
                        }
                    new_blocks.append(block)
                msg = {**msg, "content": new_blocks}
            result.append(msg)
        return result

    # ── Layer 4: Auto ──────────────────────────────────────────────

    def _auto_compact(
        self, messages: list[dict[str, Any]], llm_client: Any = None
    ) -> list[dict[str, Any]]:
        """LLM-assisted summarization of oldest messages."""
        if len(messages) <= self.keep_recent:
            return messages

        system_msg = None
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            messages = messages[1:]

        old = messages[:-self.keep_recent]
        recent = messages[-self.keep_recent:]

        summary = self._summarize(old, llm_client)
        summary_msg = {
            "role": "system",
            "content": f"[Conversation summary]\n{summary}",
        }

        result = [summary_msg] + recent
        if system_msg:
            result = [system_msg] + result
        return result

    def _summarize(self, messages: list[dict[str, Any]], llm_client: Any = None) -> str:
        """Summarize messages using LLM or fallback truncation."""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            texts.append(f"[Tool: {str(block.get('content', ''))[:200]}]")
                content = " ".join(texts)
            if content:
                parts.append(f"{role}: {str(content)[:1000]}")

        conversation = "\n".join(parts)

        if llm_client:
            try:
                prompt = (
                    "Summarize this conversation concisely. "
                    "Focus on: 1) User requests, 2) Key actions taken, "
                    "3) Important results.\n\n"
                    f"Conversation:\n{conversation[:8000]}"
                )
                response = llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                )
                summary = extract_text(response["content"])
                return summary if summary else "(summary unavailable)"
            except Exception:
                pass

        if len(conversation) > 2000:
            return conversation[:2000] + "\n... (truncated)"
        return conversation

    # ── emergency: trim_to_fit ─────────────────────────────────────

    def trim_to_fit(
        self, messages: list[dict[str, Any]], target_tokens: int | None = None
    ) -> list[dict[str, Any]]:
        """Brute-force trim: remove oldest non-system messages."""
        target = target_tokens or self.max_tokens
        system_msg = None
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            messages = messages[1:]

        while messages and self.estimate_tokens(messages) > target:
            messages = messages[1:]

        if system_msg:
            messages = [system_msg] + messages
        return messages
