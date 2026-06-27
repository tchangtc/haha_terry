"""Role-Based Access Control for Terry.

Defines roles with granular permissions for multi-user/team scenarios.
Integrates with existing PermissionStore for enforcement.

Roles: admin, developer, reviewer, viewer

Usage:
    from terry.core.rbac import RoleManager, Role
    rm = RoleManager()
    rm.assign("alice", Role.ADMIN)
    rm.can_execute("alice", "bash")  # → True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


# ── Permission Matrix ───────────────────────────────────────────────

ROLE_PERMISSIONS: dict[Role, dict[str, bool]] = {
    Role.ADMIN: {
        "bash": True,
        "write_file": True,
        "edit_file": True,
        "multi_edit": True,
        "read_file": True,
        "grep": True,
        "glob": True,
        "find": True,
        "ls": True,
        "git_commit": True,
        "git_push": True,
        "git_checkout": True,
        "git_merge": True,
        "git_branch": True,
        "git_diff": True,
        "git_log": True,
        "git_status": True,
        "web_search": True,
        "web_fetch": True,
        "config_change": True,
        "session_manage": True,
        "plugin_install": True,
    },
    Role.DEVELOPER: {
        "bash": True,
        "write_file": True,
        "edit_file": True,
        "multi_edit": True,
        "read_file": True,
        "grep": True,
        "glob": True,
        "find": True,
        "ls": True,
        "git_commit": True,
        "git_branch": True,
        "git_diff": True,
        "git_log": True,
        "git_status": True,
        "web_search": True,
        "web_fetch": True,
        "plugin_install": True,
        # Denied for developer
        "git_push": False,
        "git_checkout": False,
        "git_merge": False,
        "config_change": False,
        "session_manage": False,
    },
    Role.REVIEWER: {
        "read_file": True,
        "grep": True,
        "glob": True,
        "find": True,
        "ls": True,
        "git_diff": True,
        "git_log": True,
        "git_status": True,
        "web_search": True,
        # Read-only — no write/bash
        "bash": False,
        "write_file": False,
        "edit_file": False,
        "multi_edit": False,
        "git_commit": False,
    },
    Role.VIEWER: {
        "read_file": True,
        "grep": True,
        "glob": True,
        "find": True,
        "ls": True,
        "git_log": True,
        "git_status": True,
        # Most restricted
        "bash": False,
        "write_file": False,
        "edit_file": False,
        "web_fetch": False,
    },
}


@dataclass
class UserContext:
    """A user in the RBAC system."""

    name: str
    role: Role = Role.VIEWER
    metadata: dict = field(default_factory=dict)


class RoleManager:
    """Manage user roles and permission checks."""

    def __init__(self):
        self._users: dict[str, UserContext] = {}

    def assign(self, username: str, role: Role):
        """Assign a role to a user."""
        if username not in self._users:
            self._users[username] = UserContext(name=username, role=role)
        else:
            self._users[username].role = role

    def get_role(self, username: str) -> Role:
        """Get a user's role, defaults to VIEWER."""
        ctx = self._users.get(username)
        return ctx.role if ctx else Role.VIEWER

    def can_execute(self, username: str, permission: str) -> bool:
        """Check if a user has permission to perform an action."""
        role = self.get_role(username)
        perms = ROLE_PERMISSIONS.get(role, {})
        return perms.get(permission, False)  # Deny by default

    def list_users(self) -> list[UserContext]:
        return list(self._users.values())

    def get_permissions(self, role: Role) -> dict[str, bool]:
        """Get all permissions for a role."""
        return dict(ROLE_PERMISSIONS.get(role, {}))

    def remove(self, username: str):
        """Remove a user from RBAC."""
        self._users.pop(username, None)
