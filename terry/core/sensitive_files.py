"""Sensitive file exclusion — prevent Terry from reading/editing sensitive files.

Codex users (+447) demand this. Terry should respect .gitignore and common
patterns for secrets, credentials, and private data.

Usage:
    from terry.core.sensitive_files import SensitiveFileGuard
    guard = SensitiveFileGuard()
    guard.is_sensitive(".env")      # → True
    guard.is_sensitive("main.py")   # → False
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Patterns ────────────────────────────────────────────────────────

DEFAULT_SENSITIVE_PATTERNS: list[str] = [
    # Credentials & secrets
    r"\.env(\..*)?$",
    r".*\.pem$",
    r".*\.key$",
    r".*\.p12$",
    r".*\.pfx$",
    r".*\.jks$",
    r".*credentials.*",
    r".*secret.*",
    r".*password.*",
    r".*token.*",
    # Private keys
    r"id_rsa.*",
    r"id_ed25519.*",
    r"id_ecdsa.*",
    # Config with secrets
    r".*secrets\.(yml|yaml|json|toml)$",
    r"\.aws/credentials$",
    r"\.ssh/.*",
    r"\.gnupg/.*",
    # System files
    r"/etc/shadow$",
    r"/etc/passwd$",
    # Environment
    r".*\.env\.(local|production|staging)$",
]

DEFAULT_SENSITIVE_DIRS: list[str] = [
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".terraform",
    ".secrets",
    ".ssh",
    ".gnupg",
]


class SensitiveFileGuard:
    """Guard against reading/editing sensitive files."""

    def __init__(self, extra_patterns: list[str] | None = None,
                 extra_dirs: list[str] | None = None):
        self._patterns = DEFAULT_SENSITIVE_PATTERNS + (extra_patterns or [])
        self._dirs = DEFAULT_SENSITIVE_DIRS + (extra_dirs or [])
        self._gitignore_patterns: list[str] = []
        self._load_gitignore()

    def _load_gitignore(self):
        """Load patterns from .gitignore if present."""
        gitignore = Path.cwd() / ".gitignore"
        if gitignore.exists():
            try:
                for line in gitignore.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._gitignore_patterns.append(line)
            except OSError:
                pass

    def is_sensitive(self, path: str | Path) -> bool:
        """Check if a file path matches sensitive patterns.

        Returns True if the file should NOT be read or edited.
        """
        path_str = str(path)
        basename = os.path.basename(path_str)

        # Check directory exclusion
        for d in self._dirs:
            if f"/{d}/" in f"/{path_str}/" or path_str.startswith(f"{d}/"):
                return True

        # Check filename patterns
        for pattern in self._patterns:
            if re.search(pattern, basename):
                return True
            if re.search(pattern, path_str):
                return True

        # Check .gitignore patterns
        for pattern in self._gitignore_patterns:
            if pattern.endswith("/") and path_str.startswith(pattern.rstrip("/")):
                return True
            if not pattern.endswith("/") and basename == pattern:
                return True

        return False

    def get_blocked_files(self, paths: list[str]) -> list[str]:
        """Filter a list of paths, returning only blocked ones."""
        return [p for p in paths if self.is_sensitive(p)]

    def get_allowed_files(self, paths: list[str]) -> list[str]:
        """Filter a list of paths, returning only allowed ones."""
        return [p for p in paths if not self.is_sensitive(p)]

    def add_pattern(self, pattern: str):
        """Add a custom sensitive pattern."""
        self._patterns.append(pattern)

    def add_dir(self, directory: str):
        """Add a custom sensitive directory."""
        self._dirs.append(directory)

    def get_stats(self) -> dict:
        return {
            "patterns": len(self._patterns),
            "dirs": len(self._dirs),
            "gitignore_rules": len(self._gitignore_patterns),
        }
