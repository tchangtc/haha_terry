"""Error recovery system - handle LLM errors gracefully."""

from __future__ import annotations

import time
from typing import Any


# Model fallback chain: if primary model fails with 529 (overloaded),
# automatically try cheaper/faster alternatives.
# Format: provider_name → [fallback_model, ...]
FALLBACK_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    "openai": ["gpt-4o-mini", "gpt-3.5-turbo"],
    "deepseek": ["deepseek-chat"],
}


class ErrorRecovery:
    """Handles LLM errors with retry logic, model fallback, and recovery."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        model_fallback: bool = True,
        consecutive_529_limit: int = 3,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.model_fallback = model_fallback
        self.consecutive_529_limit = consecutive_529_limit
        self._consecutive_529_count: dict[str, int] = {}
        self._active_fallback: str | None = None

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if an error should be retried."""
        if attempt >= self.max_retries:
            return False

        error_str = str(error).lower()

        # Retryable errors
        retryable_patterns = [
            "rate limit",
            "rate_limit",
            "429",
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "overloaded",
            "capacity",
            "temporarily unavailable",
        ]

        return any(pattern in error_str for pattern in retryable_patterns)

    def get_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)

    def handle_context_length_error(
        self,
        messages: list[dict[str, Any]],
        compactor: Any,
    ) -> list[dict[str, Any]]:
        """Handle context length exceeded error.

        Strategy: Aggressively trim context.
        """
        # Try compaction first
        compacted = compactor.compact(messages)

        # If still too long, trim more aggressively
        if compactor.estimate_tokens(compacted) > compactor.max_tokens:
            compacted = compactor.trim_to_fit(
                compacted,
                target_tokens=int(compactor.max_tokens * 0.7)
            )

        return compacted

    def handle_api_error(self, error: Exception, attempt: int) -> dict[str, Any]:
        """Handle API errors and return recovery action.

        Returns:
            dict with 'action' and optional 'delay' keys.
            action can be: 'retry', 'fallback', 'fail'
        """
        error_str = str(error).lower()

        # Check for specific error types
        if "context_length_exceeded" in error_str or "max_tokens" in error_str:
            return {"action": "compact_context"}

        if self.should_retry(error, attempt):
            delay = self.get_delay(attempt)
            return {"action": "retry", "delay": delay}

        # Model fallback for 529 (overloaded)
        if self.model_fallback and ("529" in error_str or "overloaded" in error_str):
            return {"action": "model_fallback", "error": str(error)}

        # Non-retryable error
        return {"action": "fail", "error": str(error)}

    # ── Model fallback ──────────────────────────────────────────

    def should_fallback_model(self, provider: str, model: str) -> str | None:
        """Check if we should fallback to an alternative model.

        Returns the fallback model name, or None if no fallback available.
        """
        if not self.model_fallback:
            return None

        # Track consecutive 529s
        key = f"{provider}:{model}"
        self._consecutive_529_count[key] = self._consecutive_529_count.get(key, 0) + 1

        if self._consecutive_529_count[key] >= self.consecutive_529_limit:
            fallbacks = FALLBACK_MODELS.get(provider, [])
            # Find first fallback that's different from current model
            for fb in fallbacks:
                if fb != model:
                    self._active_fallback = fb
                    # Reset counter on successful fallback
                    self._consecutive_529_count[key] = 0
                    return fb
        return None

    def reset_fallback(self) -> None:
        """Reset fallback state (call after successful LLM call)."""
        self._active_fallback = None
        self._consecutive_529_count = {}


def wrap_llm_call_with_recovery(
    llm_call: callable,
    error_recovery: ErrorRecovery,
    compactor: Any = None,
) -> callable:
    """Wrap an LLM call with error recovery logic.

    Args:
        llm_call: Function that makes the LLM call
        error_recovery: ErrorRecovery instance
        compactor: Optional ContextCompactor instance

    Returns:
        Wrapped function with recovery
    """
    def wrapped_call(messages: list[dict[str, Any]], **kwargs) -> Any:
        attempt = 0

        while attempt <= error_recovery.max_retries:
            try:
                return llm_call(messages, **kwargs)
            except Exception as e:
                recovery = error_recovery.handle_api_error(e, attempt)

                if recovery["action"] == "retry":
                    delay = recovery.get("delay", 1.0)
                    print(f"[Recovery] Retry attempt {attempt + 1} after {delay:.1f}s...")
                    time.sleep(delay)
                    attempt += 1

                elif recovery["action"] == "compact_context" and compactor:
                    print("[Recovery] Context too long, compacting...")
                    messages = error_recovery.handle_context_length_error(messages, compactor)
                    attempt += 1

                else:
                    # Fail
                    raise

        raise Exception(f"Max retries ({error_recovery.max_retries}) exceeded")

    return wrapped_call
