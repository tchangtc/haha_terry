"""Error recovery system - handle LLM errors gracefully with auto-healing."""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


class AutoHealer:
    """Attempts to auto-fix common tool execution errors.

    When a tool returns an error, AutoHealer analyzes the error message
    and attempts corrective actions before giving up.
    """

    # Common error patterns and their fixes
    HEALING_PATTERNS: list[tuple[str, str, str]] = [
        # (error_regex, fix_description, fix_command_template)
        (r"command not found:?\s*(\S+)", "Install missing command", "which {cmd} 2>/dev/null || apt-get install -y {cmd} 2>/dev/null || brew install {cmd} 2>/dev/null || pip install {cmd}"),
        (r"No module named ['\"]?(\w+)['\"]?", "Install missing Python module", "pip install {cmd}"),
        (r"cannot access ['\"]?([^'\"]+)['\"]?: No such file", "Create parent directory", "mkdir -p $(dirname {path})"),
        (r"Permission denied", "Retry with sudo", "sudo !!"),
        (r"ModuleNotFoundError: No module named ['\"]?(\w+)['\"]?", "Install Python package", "pip install {cmd}"),
        (r"SyntaxError:.*", "Check syntax", None),  # Just report, can't auto-fix
        (r"ImportError:.*", "Check imports", None),
    ]

    def __init__(self, workdir: Path | None = None, max_attempts: int = 2):
        self.workdir = workdir or Path.cwd()
        self.max_attempts = max_attempts

    def analyze_error(self, tool_name: str, error_text: str) -> dict[str, Any] | None:
        """Analyze a tool error and determine if it can be healed.

        Returns:
            Dict with 'healable', 'suggestion', 'fix_command' or None
        """
        for pattern, description, fix_template in self.HEALING_PATTERNS:
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                cmd = match.group(1) if match.groups() else ""
                path_match = re.search(r"['\"]?([^'\"]+)['\"]?", error_text)
                path = path_match.group(1) if path_match else ""

                fix_cmd = None
                if fix_template:
                    fix_cmd = fix_template.format(cmd=cmd, path=path)

                return {
                    "healable": fix_cmd is not None,
                    "pattern": pattern,
                    "description": description,
                    "fix_command": fix_cmd,
                    "matched_value": cmd or path,
                }
        return None

    def attempt_heal(
        self,
        tool_name: str,
        tool_input: dict,
        error_text: str,
        retry_count: int = 0,
    ) -> str | None:
        """Attempt to heal a tool error and retry.

        Returns:
            Fixed result string if healed, None if couldn't heal
        """
        if retry_count >= self.max_attempts:
            return None

        analysis = self.analyze_error(tool_name, error_text)
        if analysis is None or not analysis["healable"]:
            return None

        fix_cmd = analysis["fix_command"]
        if fix_cmd is None:
            return None

        # Try the fix command
        try:
            result = subprocess.run(
                ["/bin/sh", "-c", fix_cmd],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            fix_output = (result.stdout + result.stderr).strip()

            # Don't retry if fix failed
            if result.returncode != 0 and "apt-get" not in fix_cmd:
                return None

            return (
                f"[AutoHealer] Applied fix: {analysis['description']}\n"
                f"Fix command: {fix_cmd}\n"
                f"Fix output: {fix_output[:500]}\n\n"
                f"Original error: {error_text}"
            )
        except Exception:
            return None


def auto_commit_after_edit(
    workdir: Path,
    tool_name: str,
    tool_input: dict,
    tool_output: str,
) -> str | None:
    """Auto-commit changes after write/edit operations.

    Only commits if the working directory is a git repo and the
    tool execution was successful (no error in output).

    Returns commit message or None if no commit made.
    """
    if "Error" in tool_output or "Permission denied" in tool_output:
        return None

    if tool_name not in ("write_file", "edit_file", "multi_edit"):
        return None

    # Check if it's a git repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
    except Exception:
        return None

    # Get the file path
    file_path = tool_input.get("path", "")
    if not file_path:
        return None

    # Stage and commit
    try:
        # Use conventional commit format with meaningful context
        commit_type = "chore"
        if tool_name == "write_file":
            commit_type = "feat" if file_path.endswith(".py") else "chore"
        elif tool_name in ("edit_file", "multi_edit"):
            commit_type = "fix"

        scope = Path(file_path).parent.name if Path(file_path).parent.name else "root"
        msg = f"{commit_type}({scope}): update {Path(file_path).name}"

        subprocess.run(
            ["git", "add", "--", file_path],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Dedup: only commit if there are staged changes
        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=workdir,
            capture_output=True,
            timeout=5,
        )
        if diff_check.returncode == 0:
            return None  # No changes to commit

        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            logger.info("Auto-committed: %s", msg)
            return f"Committed: {msg}"
        return None
    except Exception:
        return None


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
                    logger.info("Retry attempt %d after %.1fs...", attempt + 1, delay)
                    time.sleep(delay)
                    attempt += 1

                elif recovery["action"] == "compact_context" and compactor:
                    logger.info("Context too long, compacting...")
                    messages = error_recovery.handle_context_length_error(messages, compactor)
                    attempt += 1

                else:
                    # Fail
                    raise

        raise Exception(f"Max retries ({error_recovery.max_retries}) exceeded")

    return wrapped_call
