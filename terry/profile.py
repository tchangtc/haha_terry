"""Agent Profile system — preset configurations for different roles.

Profiles define agent behavior, tools, and system prompts for specific
use cases: coder, reviewer, architect, debugger, etc.

Usage:
    terry profile list
    terry profile use coder
    terry profile create my-profile
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Profile:
    """An agent profile defining behavior for a specific role."""

    name: str
    description: str = ""
    system_prompt: str = ""
    tools_allow: list[str] = field(default_factory=list)
    tools_deny: list[str] = field(default_factory=list)
    effort: str = "medium"  # low, medium, high, xhigh
    model_override: str = ""  # Override default model
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools_allow": self.tools_allow,
            "tools_deny": self.tools_deny,
            "effort": self.effort,
            "model_override": self.model_override,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            tools_allow=data.get("tools_allow", []),
            tools_deny=data.get("tools_deny", []),
            effort=data.get("effort", "medium"),
            model_override=data.get("model_override", ""),
            metadata=data.get("metadata", {}),
        )


# ── Built-in profiles ──────────────────────────────────────────────

BUILTIN_PROFILES: dict[str, Profile] = {
    "coder": Profile(
        name="coder",
        description="General-purpose coding assistant — write, edit, and refactor code",
        system_prompt="You are a skilled software engineer. Write clean, well-documented code. "
        "Prefer simplicity over cleverness. Add type hints and tests.",
        tools_allow=["read_file", "write_file", "edit_file", "multi_edit", "bash"],
        effort="high",
    ),
    "reviewer": Profile(
        name="reviewer",
        description="Code reviewer — find bugs, security issues, and style violations",
        system_prompt="You are a thorough code reviewer. Find bugs, logic errors, "
        "security vulnerabilities, and style issues. Be specific about what is wrong "
        "and how to fix it. Rate severity: minor, major, critical.",
        tools_allow=["read_file", "grep", "glob", "find", "git_diff", "git_log"],
        tools_deny=["write_file", "edit_file", "multi_edit", "bash"],
        effort="high",
    ),
    "architect": Profile(
        name="architect",
        description="System architect — design architecture, plan features, review tradeoffs",
        system_prompt="You are a system architect. Design scalable, maintainable architectures. "
        "Consider tradeoffs: simplicity vs flexibility, performance vs readability. "
        "Produce architecture diagrams (Mermaid), API designs, and data models. "
        "Do NOT write implementation code unless asked.",
        tools_allow=["read_file", "grep", "glob", "find", "repomap"],
        tools_deny=["write_file", "edit_file", "multi_edit"],
        effort="xhigh",
    ),
    "debugger": Profile(
        name="debugger",
        description="Debugging specialist — find and fix bugs systematically",
        system_prompt="You are a debugging specialist. Reproduce bugs, trace execution paths, "
        "add diagnostic logging, and verify fixes. Use git bisect logic to narrow down "
        "regressions. Always confirm a fix actually resolves the issue.",
        tools_allow=["read_file", "edit_file", "bash", "grep", "git_log", "git_diff"],
        effort="high",
    ),
    "devops": Profile(
        name="devops",
        description="DevOps engineer — CI/CD, Docker, deployment, infrastructure",
        system_prompt="You are a DevOps engineer. Manage CI/CD pipelines, Docker containers, "
        "Kubernetes deployments, and cloud infrastructure. Prefer infrastructure-as-code. "
        "Always consider security and cost implications.",
        tools_allow=["bash", "read_file", "write_file", "edit_file", "glob"],
        effort="medium",
    ),
}


# ── Profile Manager ──────────────────────────────────────────────────


class ProfileManager:
    """Manage agent profiles — built-in and user-created."""

    def __init__(self, profiles_dir: Path | None = None):
        if profiles_dir is None:
            from terry.core.platform_utils import get_terry_dir
            profiles_dir = get_terry_dir() / "profiles"
        self._dir = profiles_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._active_profile: str | None = None

    def list_all(self) -> list[Profile]:
        """List built-in + user profiles."""
        profiles = list(BUILTIN_PROFILES.values())
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                if data["name"] not in BUILTIN_PROFILES:
                    profiles.append(Profile.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                pass
        return profiles

    def get(self, name: str) -> Profile | None:
        """Get a profile by name (built-in first, then user)."""
        if name in BUILTIN_PROFILES:
            return BUILTIN_PROFILES[name]
        user_path = self._dir / f"{name}.json"
        if user_path.exists():
            try:
                return Profile.from_dict(json.loads(user_path.read_text()))
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def create(self, profile: Profile) -> None:
        """Save a user-defined profile."""
        if profile.name in BUILTIN_PROFILES:
            raise ValueError(f"Cannot override built-in profile: {profile.name}")
        path = self._dir / f"{profile.name}.json"
        path.write_text(json.dumps(profile.to_dict(), indent=2))

    def delete(self, name: str) -> None:
        """Delete a user-defined profile."""
        if name in BUILTIN_PROFILES:
            raise ValueError(f"Cannot delete built-in profile: {name}")
        path = self._dir / f"{name}.json"
        if path.exists():
            path.unlink()

    def use(self, name: str) -> Profile:
        """Activate a profile and return it."""
        profile = self.get(name)
        if not profile:
            raise ValueError(f"Profile not found: {name}")
        self._active_profile = name
        return profile

    def get_active(self) -> Profile | None:
        if self._active_profile:
            return self.get(self._active_profile)
        return None
