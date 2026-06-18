"""4-layer progressive context compaction — inspired by opencode + hermes-agent.

Layers (executed in order before each LLM call):
  1. Budget  — persist large (>50K) tool outputs to disk, replace with [stored] marker
  2. Snip    — trim middle messages, keep head + tail windows
  3. Micro   — compress old tool results into terse [tool:name → result_summary] format
  4. Auto    — LLM-assisted summarization of oldest messages

Design principles (from industry leaders):
  - Observable: compaction events emit warnings so users know context was compressed
  - Pluggable: hooks allow customization of compaction prompts (opencode pattern)
  - Safe: feasibility checks before Layer 4 prevent wasted LLM calls (hermes-agent pattern)
  - Memory-aware: auto-saves critical facts to Memory before irreversible compression

Each layer is independent and idempotent. Execute 1→4 sequentially.
If layer N brings context below threshold, skip layers N+1..4.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir
from .text_utils import extract_text

logger = logging.getLogger(__name__)

# ── tiktoken integration (optional) ─────────────────────────────

try:
    import tiktoken

    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

# Model name → tiktoken encoding name mapping
_MODEL_ENCODING_MAP: dict[str, str] = {
    # Anthropic Claude models
    "claude-sonnet-4": "claude",
    "claude-3-5-sonnet": "claude",
    "claude-3-opus": "claude",
    "claude-3-haiku": "claude",
    "claude-3-sonnet": "claude",
    # OpenAI models
    "gpt-4o": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    # DeepSeek models (use cl100k_base approximation)
    "deepseek-chat": "cl100k_base",
    "deepseek-reasoner": "cl100k_base",
    # Qwen models
    "qwen-plus": "cl100k_base",
    "qwen-max": "cl100k_base",
    "qwen-turbo": "cl100k_base",
    # Zhipu GLM models
    "glm-4-flash": "cl100k_base",
    "glm-4-plus": "cl100k_base",
    "glm-4-long": "cl100k_base",
    # Ollama local models
    "llama3": "cl100k_base",
    "mistral": "cl100k_base",
    "codellama": "cl100k_base",
}

# Known model context windows (max tokens)
_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-sonnet-4-20250514": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "o1": 200_000,
    "gpt-4-turbo-preview": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_384,
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "qwen-plus": 131_072,
    "qwen-max": 32_768,
    "qwen-turbo": 1_000_000,
    "glm-4-flash": 128_000,
    "glm-4-plus": 128_000,
    "glm-4-long": 1_000_000,
}

_encoding_cache: dict[str, Any] = {}


def _get_encoding(model: str) -> Any | None:
    """Get tiktoken encoding for a model, with caching."""
    if not _TIKTOKEN_AVAILABLE:
        return None

    # Try exact match first
    if model in _encoding_cache:
        return _encoding_cache[model]

    # Try prefix match
    encoding_name = None
    for prefix, enc in sorted(_MODEL_ENCODING_MAP.items(), key=lambda x: -len(x[0])):
        if model.lower().startswith(prefix) or prefix in model.lower():
            encoding_name = enc
            break

    if encoding_name is None:
        encoding_name = "cl100k_base"  # Default fallback

    try:
        enc = tiktoken.get_encoding(encoding_name)
    except Exception:
        logger.warning("Failed to get tiktoken encoding: %s", encoding_name, exc_info=True)
        enc = tiktoken.get_encoding("cl100k_base")

    _encoding_cache[model] = enc
    return enc


def get_token_count(text: str, model: str = "claude-sonnet-4-20250514") -> int:
    """Get precise token count for text, with CJK-aware correction.

    Uses tiktoken for accurate counting, then applies a correction factor
    for CJK text (Chinese/Japanese/Korean) which tiktoken's English-centric
    encodings may underestimate by 30-50%.

    Args:
        text: Text to count tokens for
        model: Model name for encoding selection

    Returns:
        Token count (falls back to chars//4 if tiktoken unavailable)
    """
    enc = _get_encoding(model)
    if enc is not None:
        try:
            base = len(enc.encode(text))
            # CJK-aware correction: if >30% of characters are CJK,
            # apply a proportional correction factor (up to 1.5x).
            text_len = len(text)
            if text_len > 0:
                cjk_count = sum(
                    1 for c in text
                    if '一' <= c <= '鿿'      # CJK Unified
                    or '㐀' <= c <= '䶿'      # CJK Extension A
                    or '豈' <= c <= '﫿'      # CJK Compatibility
                    or '぀' <= c <= 'ゟ'      # Hiragana
                    or '゠' <= c <= 'ヿ'      # Katakana
                    or '가' <= c <= '힯'      # Hangul
                )
                cjk_ratio = cjk_count / text_len
                if cjk_ratio > 0.3:
                    # merco-inspired: cjk × 1.5 correction, proportional to ratio
                    base = int(base * (1.0 + cjk_ratio * 0.5))
            return base
        except Exception:
            logger.warning("Failed to encode text with tiktoken", exc_info=True)
            pass
    # Fallback: rough estimate with CJK correction
    cjk_count = sum(1 for c in text if '一' <= c <= '鿿')
    return (len(text) - cjk_count) // 4 + int(cjk_count * 1.5)


def get_model_context_window(provider: str, model: str) -> int:
    """Get the context window size for a model.

    Args:
        provider: Provider name
        model: Model name

    Returns:
        Context window in tokens (default 1_000_000 if unknown)
    """
    # Exact match
    if model in _MODEL_CONTEXT_WINDOWS:
        return _MODEL_CONTEXT_WINDOWS[model]
    # Prefix match
    for prefix, window in sorted(_MODEL_CONTEXT_WINDOWS.items(), key=lambda x: -len(x[0])):
        if model.startswith(prefix) or prefix in model:
            return window
    return 1_000_000  # Default to 1M for modern models


@dataclass
class CompactionEvent:
    """Emitted before and after compaction — inspired by opencode's plugin hook."""
    layer: str = ""            # "budget" | "snip" | "micro" | "auto"
    before_count: int = 0      # messages before compaction
    after_count: int = 0       # messages after compaction
    tokens_saved: int = 0      # estimated tokens freed
    custom_prompt: str = ""    # plugin can override Layer 4 prompt
    warnings: list[str] = field(default_factory=list)


# Global hook registry for compaction events
_compaction_hooks: list[Callable[[CompactionEvent], None]] = []


def register_compaction_hook(hook: Callable[[CompactionEvent], None]) -> None:
    """Register a callback invoked before each compaction layer."""
    _compaction_hooks.append(hook)


class ContextCompactor:
    """4-layer progressive context compaction with precise token counting."""

    def __init__(
        self,
        config: Any = None,
        max_tokens: int | None = None,
        compression_threshold: float | None = None,
        keep_recent: int = 10,
        budget_dir: Path | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        if config is not None:
            from .config import TerryConfig
            if isinstance(config, TerryConfig):
                max_tokens = max_tokens or config.max_input_tokens
                compression_threshold = compression_threshold or config.compression_threshold
        self.max_tokens = max_tokens or 1_000_000
        self.compression_threshold = compression_threshold or 0.85
        self.keep_recent = keep_recent
        self.model = model
        self.budget_dir = budget_dir or get_terry_dir("budget")
        self.budget_dir.mkdir(parents=True, exist_ok=True)

        # Configurable limits
        self.BUDGET_LIMIT = 50_000   # chars — persist outputs larger than this
        self.SNIP_HEAD = 3           # keep first N messages
        self.SNIP_TAIL = 7           # keep last N messages
        self.MICRO_MAX_LEN = 200     # max chars for micro result summary

    def reconfigure(self, threshold: float | None = None, max_tokens: int | None = None) -> None:
        """Update compaction parameters at runtime without recreating the compactor.

        Args:
            threshold: New compression_threshold (0.1–0.95). If None, keeps current.
            max_tokens: New max_input_tokens. If None, keeps current.
        """
        if threshold is not None:
            self.compression_threshold = threshold
        if max_tokens is not None:
            self.max_tokens = max_tokens

    # ── token estimation ──────────────────────────────────────────

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Precise token count using tiktoken, with char-based fallback.

        Uses the model's appropriate encoding for accurate counting.
        Falls back to 1 token ≈ 4 characters if tiktoken is unavailable.
        """
        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)

        # Try tiktoken for a sample to estimate ratio, or count precisely
        if _TIKTOKEN_AVAILABLE:
            try:
                # Sample-based estimation for performance on large message sets
                sample_size = min(5, len(messages))
                if sample_size > 0 and len(messages) > 10:
                    sample_chars = sum(
                        len(str(messages[i].get("content", "")))
                        for i in range(sample_size)
                    )
                    sample_text = "\n".join(
                        str(messages[i].get("content", ""))
                        for i in range(sample_size)
                    )
                    sample_tokens = get_token_count(sample_text, self.model)
                    ratio = sample_tokens / max(sample_chars, 1)
                    return int(total_chars * ratio)
                else:
                    # For small message sets, count precisely
                    full_text = "\n".join(
                        str(msg.get("content", "")) for msg in messages
                    )
                    return get_token_count(full_text, self.model)
            except Exception:
                logger.warning("Failed to estimate tokens via tiktoken sample", exc_info=True)
                pass

        # Fallback: 1 token ≈ 4 characters
        return total_chars // 4

    def needs_compaction(self, messages: list[dict[str, Any]]) -> bool:
        """Check if any compaction layer is needed."""
        tokens = self.estimate_tokens(messages)
        return tokens > int(self.max_tokens * self.compression_threshold)

    # ── public compact() entry point ───────────────────────────────

    def compact(
        self, messages: list[dict[str, Any]], llm_client: Any = None,
        memory: Any = None, on_warning: Callable[[str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply progressive compaction: budget → snip → micro → auto.

        Before irreversible compaction, persists key facts to Memory and
        emits observable warnings so users know context was compressed.

        Args:
            messages: Current conversation messages.
            llm_client: LLM client for Layer 4 auto-summarization.
            memory: Optional Memory instance for auto-savepoints.
            on_warning: Optional callback for user-visible compaction notifications.
        """
        before_count = len(messages)
        before_tokens = self.estimate_tokens(messages)

        # Layer 1: Budget (reversible — no data loss)
        messages = self._budget_compact(messages)
        if not self.needs_compaction(messages):
            return messages

        # Emit compaction event to registered hooks (opencode pattern)
        event = CompactionEvent(
            layer="snip",
            before_count=before_count,
            after_count=len(messages),
            tokens_saved=max(0, before_tokens - self.estimate_tokens(messages)),
        )
        for hook in _compaction_hooks:
            try: hook(event)
            except Exception: pass

        if on_warning:
            on_warning(
                f"Context window at {before_tokens:,}/{self.max_tokens:,} tokens "
                f"({before_tokens/self.max_tokens:.0%}). Compacting to preserve context."
            )

        # Memory savepoint: persist key facts before Snip (hermes-agent pattern)
        if memory is not None and len(messages) > self.SNIP_HEAD + self.SNIP_TAIL:
            try:
                middle = messages[self.SNIP_HEAD:-self.SNIP_TAIL]
                self._memory_savepoint(middle, memory)
            except Exception:
                pass  # Memory integration is best-effort

        # Layer 2: Snip (IRREVERSIBLE)
        messages = self._snip_compact(messages)
        if not self.needs_compaction(messages):
            return messages

        # Layer 3: Micro (IRREVERSIBLE)
        messages = self._micro_compact(messages)
        if not self.needs_compaction(messages):
            return messages

        # Layer 4: Auto — only if LLM is available (hermes-agent feasibility check)
        if llm_client is None:
            logger.warning("Layer 4 (Auto) skipped: no LLM client available")
            if on_warning:
                on_warning("Auto-compaction skipped (no LLM). Some context may be lost.")
            return messages

        messages = self._auto_compact(messages, llm_client)
        return messages

    def _memory_savepoint(self, messages: list[dict[str, Any]], memory: Any) -> None:
        """Extract key facts from messages about to be compacted.

        Saves structured summaries as MemoryType.SESSION_COMPACT entries
        so critical context survives compaction.
        """
        import time
        facts = []
        for msg in messages:
            content = str(msg.get("content", ""))
            role = msg.get("role", "unknown")
            # Extract lines that contain code, errors, decisions, or file paths
            for line in content.split("\n"):
                line = line.strip()
                if not line or len(line) < 10:
                    continue
                # Key signal: errors, file changes, decisions
                if any(kw in line.lower() for kw in (
                    "error", "exception", "traceback", "failed", "fixed",
                    "write_file", "edit_file", "created", "modified", "deleted",
                    "decision", "decided", "should", "must", "important",
                    ".py:", ".js:", ".ts:", ".md:",  # file references
                )):
                    facts.append(f"[{role}] {line[:200]}")
                # Tool results
                if role in ("tool", "assistant") and len(line) > 50:
                    facts.append(f"[{role}] {line[:200]}")

        if facts:
            # Deduplicate and limit
            seen = set()
            unique = []
            for f in facts:
                key = f[:80]
                if key not in seen:
                    seen.add(key)
                    unique.append(f)
                    if len(unique) >= 20:
                        break

            timestamp = int(time.time())
            content = "\n".join(unique)
            try:
                memory.add(
                    name=f"session-compact-{timestamp}",
                    content=f"# Context Snapshot ({timestamp})\n\n{content}",
                    memory_type="SESSION_COMPACT",
                    description=f"Auto-saved context from session compaction at {timestamp}",
                    tags=["auto", "compaction", "session"],
                )
                logger.info("Memory savepoint: %d facts saved", len(unique))
            except Exception:
                logger.debug("Memory savepoint failed", exc_info=True)

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
                logger.warning("Failed to summarize conversation with LLM", exc_info=True)
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
