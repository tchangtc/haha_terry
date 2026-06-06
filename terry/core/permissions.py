"""Permission engine - fine-grained levels, rule persistence, and access control.

Levels (ascending strictness):
  low      — all operations auto-approved (read/write/network/bash)
  medium   — destructive ops + path escape = ask (default, equivalent to old "ask" mode)
  high     — destructive ops + path escape = deny (equivalent to old "deny" mode)
  critical — everything denied, even safe reads outside workspace

Permission rules are persisted to ~/.terry/permissions.json and checked
before the 3-gate security pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class PermissionLevel(StrEnum):
    """Fine-grained sandbox permission levels."""
    LOW = "low"           # All operations auto-approved
    MEDIUM = "medium"     # Destructive + path-escape = ask (default)
    HIGH = "high"         # Destructive + path-escape = deny
    CRITICAL = "critical" # Everything denied

    @classmethod
    def from_sandbox_mode(cls, mode: str) -> PermissionLevel:
        """Convert legacy sandbox mode to permission level."""
        mapping = {
            "auto": cls.LOW,
            "ask": cls.MEDIUM,
            "deny": cls.HIGH,
        }
        return mapping.get(mode, cls.MEDIUM)

    def to_sandbox_mode(self) -> str:
        """Convert to legacy sandbox mode string."""
        mapping = {
            PermissionLevel.LOW: "auto",
            PermissionLevel.MEDIUM: "ask",
            PermissionLevel.HIGH: "deny",
            PermissionLevel.CRITICAL: "deny",
        }
        return mapping.get(self, "ask")

    @classmethod
    def cycle(cls, current: PermissionLevel) -> PermissionLevel:
        """Cycle: low → medium → high → critical → low."""
        order = [cls.LOW, cls.MEDIUM, cls.HIGH, cls.CRITICAL]
        try:
            idx = order.index(current)
            return order[(idx + 1) % len(order)]
        except ValueError:
            return cls.MEDIUM


class PermissionRule:
    """A single permission rule that can allow, deny, or ask for a specific tool+pattern."""

    def __init__(
        self,
        tool: str,
        pattern: str = "*",
        action: str = "ask",
        level: str = "medium",
        source: str = "user",
        expires_at: str | None = None,
    ):
        self.tool = tool          # Tool name or "*" for all tools
        self.pattern = pattern    # Glob or regex pattern for command/path matching
        self.action = action      # "allow", "deny", "ask"
        self.level = level        # Minimum permission level this rule applies at
        self.source = source      # "builtin", "user", "session"
        self.expires_at = expires_at  # ISO timestamp or None for permanent
        self.created_at = datetime.now().isoformat()

    def matches(self, tool: str, command_or_path: str) -> bool:
        """Check if this rule matches a tool and command/path."""
        if self.tool != "*" and self.tool != tool:
            return False
        if self.pattern == "*":
            return True
        # Simple glob matching
        import fnmatch
        return fnmatch.fnmatch(command_or_path, self.pattern)

    def is_expired(self) -> bool:
        """Check if this rule has expired."""
        if self.expires_at is None:
            return False
        return datetime.now().isoformat() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "pattern": self.pattern,
            "action": self.action,
            "level": self.level,
            "source": self.source,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PermissionRule:
        return cls(
            tool=data.get("tool", "*"),
            pattern=data.get("pattern", "*"),
            action=data.get("action", "ask"),
            level=data.get("level", "medium"),
            source=data.get("source", "user"),
            expires_at=data.get("expires_at"),
        )


class PermissionStore:
    """Persistent permission rule store."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".terry" / "permissions.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rules: list[PermissionRule] = []
        self._load()

    def _load(self) -> None:
        """Load rules from disk."""
        if not self.path.exists():
            self._init_defaults()
            self._save()
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.rules = [
                PermissionRule.from_dict(r)
                for r in data.get("rules", [])
            ]
            # Clean up expired rules
            self._prune_expired()
        except Exception:
            self.rules = []
            self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize with safe defaults."""
        defaults = [
            # Always deny dangerous operations
            PermissionRule(tool="bash", pattern="rm -rf /*", action="deny",
                          level="low", source="builtin"),
            PermissionRule(tool="bash", pattern="sudo *", action="deny",
                          level="low", source="builtin"),
            PermissionRule(tool="bash", pattern="shutdown *", action="deny",
                          level="low", source="builtin"),
            # Allow safe read operations
            PermissionRule(tool="read_file", pattern="*", action="allow",
                          level="medium", source="builtin"),
            PermissionRule(tool="ls", pattern="*", action="allow",
                          level="medium", source="builtin"),
            PermissionRule(tool="find", pattern="*", action="allow",
                          level="medium", source="builtin"),
        ]
        self.rules = defaults

    def _save(self) -> None:
        """Persist rules to disk."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "rules": [r.to_dict() for r in self.rules],
        }
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _prune_expired(self) -> int:
        """Remove expired rules. Returns count removed."""
        before = len(self.rules)
        self.rules = [r for r in self.rules if not r.is_expired()]
        return before - len(self.rules)

    def add_rule(self, rule: PermissionRule) -> None:
        """Add a new rule and persist."""
        # Remove existing rule for same tool+pattern
        self.rules = [
            r for r in self.rules
            if not (r.tool == rule.tool and r.pattern == rule.pattern)
        ]
        self.rules.append(rule)
        self._save()

    def remove_rule(self, tool: str, pattern: str = "*") -> bool:
        """Remove rules matching tool and pattern. Returns True if any removed."""
        before = len(self.rules)
        self.rules = [
            r for r in self.rules
            if not (r.tool == tool and r.pattern == pattern)
        ]
        if len(self.rules) < before:
            self._save()
            return True
        return False

    def get_applicable(self, tool: str, command_or_path: str = "") -> list[PermissionRule]:
        """Get all rules that match a tool and optional command/path."""
        return [
            r for r in self.rules
            if r.matches(tool, command_or_path) and not r.is_expired()
        ]

    def check(
        self,
        tool: str,
        command_or_path: str = "",
        level: PermissionLevel = PermissionLevel.MEDIUM,
    ) -> str | None:
        """Check permission for a tool+command at the given level.

        Returns:
            None = allow (no applicable deny/ask rule)
            "allow" = explicitly allowed
            "deny" = explicitly denied (returns reason string)
            "ask" = requires user confirmation (returns reason string)
        """
        applicable = self.get_applicable(tool, command_or_path)

        # Check explicit denies first (most important)
        for rule in applicable:
            if rule.action == "deny":
                return f"Denied by rule: {rule.tool}/{rule.pattern}"

        # Check explicit allows
        for rule in applicable:
            if rule.action == "allow":
                return None  # Explicitly allowed

        # Check "ask" rules
        for rule in applicable:
            if rule.action == "ask":
                return f"Requires confirmation: {rule.tool}/{rule.pattern}"

        # No applicable rules = None (default allow at current level)
        return None

    def list_rules(self) -> list[dict]:
        """List all rules with metadata."""
        return [
            {
                "tool": r.tool,
                "pattern": r.pattern,
                "action": r.action,
                "level": r.level,
                "source": r.source,
            }
            for r in self.rules
            if not r.is_expired()
        ]

    def clear_user_rules(self) -> int:
        """Remove all user-added rules. Returns count removed."""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.source != "user"]
        removed = before - len(self.rules)
        if removed > 0:
            self._save()
        return removed


# Global instance
_permission_store: PermissionStore | None = None


def get_permission_store(path: Path | None = None) -> PermissionStore:
    """Get or create the global permission store."""
    global _permission_store
    if _permission_store is None:
        _permission_store = PermissionStore(path)
    return _permission_store


def set_permission_store(instance: PermissionStore) -> None:
    """Inject a custom PermissionStore (for testing/DI)."""
    global _permission_store
    _permission_store = instance


def reset_permission_store() -> None:
    """Reset permission store singleton."""
    global _permission_store
    _permission_store = None
