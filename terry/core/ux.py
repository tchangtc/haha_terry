"""UX enhancements — first-run wizard, friendly errors, tips, progress feedback."""

from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any

from .platform_utils import get_terry_dir


class FirstRunWizard:
    """Detects first run and provides guided onboarding."""

    STATE_FILE = get_terry_dir() / ".onboarding_complete"

    WELCOME_MESSAGES = [
        "👋 Welcome! I'm Terry, your AI coding agent. Type anything to get started.",
        "💡 Tip: Use /plan before big tasks — I'll show you my approach first.",
        "🔍 Try: 'Find where authentication logic is implemented'",
        "🛠️  Try: 'Fix the bug in the login function'",
        "📝 Try: 'Review this file for security issues'",
        "🧪 Try: 'Generate tests for the User class'",
    ]

    @classmethod
    def is_first_run(cls) -> bool:
        return not cls.STATE_FILE.exists()

    @classmethod
    def mark_complete(cls) -> None:
        cls.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.STATE_FILE.write_text(datetime.now().isoformat())

    @classmethod
    def get_welcome(cls) -> str:
        if cls.is_first_run():
            return "\n".join(f"  {m}" for m in cls.WELCOME_MESSAGES)
        return cls.WELCOME_MESSAGES[random.randint(0, len(cls.WELCOME_MESSAGES) - 1)]


class FriendlyErrors:
    """Maps raw errors to user-friendly messages with actionable suggestions."""

    SUGGESTIONS = {
        "command not found": (
            "The command '{cmd}' wasn't found on your system. "
            "Install it with your package manager (e.g., brew install {cmd}, apt install {cmd}) "
            "or check if it's available under a different name."
        ),
        "ModuleNotFoundError": (
            "Python module '{module}' is missing. "
            "Install it with: pip install {module}"
        ),
        "FileNotFoundError": (
            "The file '{path}' doesn't exist. "
            "Check the path spelling or use 'ls' to see what's in the current directory."
        ),
        "Permission denied": (
            "Permission denied for '{path}'. "
            "Check file permissions or try running with appropriate access rights."
        ),
        "Connection refused": (
            "Couldn't connect to the server. "
            "Check your network connection and verify the URL is correct."
        ),
        "timeout": (
            "The operation timed out. "
            "The server might be slow or unreachable. Try again or increase the timeout."
        ),
        "API key": (
            "API key not configured. "
            "Set your key with: export ANTHROPIC_API_KEY=sk-ant-... "
            "or use /config to configure it."
        ),
        "rate limit": (
            "Rate limit reached. "
            "Wait a moment before retrying. Consider using a cheaper model for simple tasks."
        ),
        "context length": (
            "Context window is full. "
            "The conversation is too long — use /new to start fresh or /context to check usage."
        ),
    }

    @classmethod
    def translate(cls, error_text: str, context: dict | None = None) -> str:
        """Convert raw error to friendly message."""
        ctx = context or {}
        error_lower = error_text.lower()

        for pattern, template in cls.SUGGESTIONS.items():
            if pattern.lower() in error_lower:
                # Extract relevant values
                cmd = ctx.get("cmd", "the command")
                module = ctx.get("module", "the module")
                path = ctx.get("path", "the file")
                return template.format(cmd=cmd, module=module, path=path)

        # Generic friendly wrapper
        return f"Something went wrong: {error_text[:200]}\n\nRun /help for available commands or try again."


class TipsEngine:
    """Contextual tips shown during agent usage."""

    TIPS = [
        "💡 Use /plan before big refactors — Terry will outline the approach first.",
        "💡 Use @file:path to give Terry direct context about a specific file.",
        "💡 Use /undo to revert the last file change. Run /checkpoints to see all snapshots.",
        "💡 Use /search to find anything in your conversation history.",
        "💡 Run 'terry webui' for a visual chat interface in your browser.",
        "💡 Use /stream for real-time token-by-token responses.",
        "💡 Terry auto-creates skills from repeated workflows. Check /auto-skills.",
        "💡 Use /fork to explore alternative approaches without losing your main conversation.",
        "💡 Press Tab to autocomplete commands in the CLI.",
    ]

    SHOWN_TIPS: set[int] = set()

    @classmethod
    def get_random_tip(cls) -> str | None:
        """Get a random unshown tip. Returns None if all tips have been shown."""
        available = [i for i in range(len(cls.TIPS)) if i not in cls.SHOWN_TIPS]
        if not available:
            cls.SHOWN_TIPS.clear()
            available = list(range(len(cls.TIPS)))

        idx = random.choice(available)
        cls.SHOWN_TIPS.add(idx)
        return cls.TIPS[idx]

    @classmethod
    def get_tip_for_context(cls, tool_name: str = "", message: str = "") -> str | None:
        """Get a contextual tip based on what the user is doing."""
        msg_lower = message.lower()

        if "fix" in msg_lower or "bug" in msg_lower:
            return "💡 After fixing, use /undo if the fix doesn't work as expected."
        if "refactor" in msg_lower or "restructure" in msg_lower:
            return "💡 Use /plan first for complex refactoring tasks."
        if "test" in msg_lower:
            return "💡 Use /benchmark to measure your agent's performance."
        if tool_name in ("write_file", "edit_file"):
            return "💡 File changes are checkpointed. Use /undo to revert."

        # Show random tip ~10% of the time
        if random.random() < 0.1:
            return cls.get_random_tip()
        return None


class UXFormatter:
    """Consistent output formatting for terminal UX."""

    @staticmethod
    def success(message: str) -> str:
        return f"\033[32m✅ {message}\033[0m"

    @staticmethod
    def warning(message: str) -> str:
        return f"\033[33m⚠️  {message}\033[0m"

    @staticmethod
    def error(message: str) -> str:
        return f"\033[31m❌ {message}\033[0m"

    @staticmethod
    def info(message: str) -> str:
        return f"\033[36mℹ️  {message}\033[0m"

    @staticmethod
    def tip(message: str) -> str:
        return f"\033[90m💡 {message}\033[0m"

    @staticmethod
    def section(title: str) -> str:
        return f"\n\033[1m{title}\033[0m\n{'─' * len(title)}"

    @staticmethod
    def summary(agent: Any) -> str:
        """Generate a human-readable summary of what the agent just did."""
        status = agent.get_status()
        tool_calls = status.get("tool_call_count", 0)
        msg_count = status.get("message_count", 0)
        parts = ["\n\033[90m─── Session ───\033[0m"]
        if tool_calls > 0:
            parts.append(f"\033[90m  Tools used: {tool_calls}\033[0m")
        parts.append(f"\033[90m  Messages: {msg_count}\033[0m")
        return "\n".join(parts)

    @staticmethod
    def spinner(message: str) -> str:
        """Spinner text for long operations."""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = int(time.time() * 10) % len(frames)
        return f"\r{frames[idx]} {message}"
