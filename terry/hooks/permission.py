"""Permission hook - 3-mode security pipeline with Shift+Tab mode cycling.

Modes (cycle with Shift+Tab or /mode command):
  deny — strictest: hard deny + all destructive/path-escape blocked
  ask  — default: hard deny + user prompt for destructive/path-escape
  auto — loosest: hard deny + destructive auto-approved, path-escape blocked

Architecture:
  Gate 1: Hard deny list — ALWAYS blocked regardless of mode
  Gate 2: Destructive patterns — mode-dependent
  Gate 3: Path escape — mode-dependent (blocked even in auto)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path


class SandboxMode(StrEnum):
    DENY = "deny"
    ASK = "ask"
    AUTO = "auto"

    @classmethod
    def cycle(cls, current: SandboxMode) -> SandboxMode:
        """Cycle to the next mode in order: ask → auto → deny → ask."""
        order = [cls.ASK, cls.AUTO, cls.DENY]
        try:
            idx = order.index(current)
            return order[(idx + 1) % len(order)]
        except ValueError:
            return cls.ASK


# ── Gate 1: Hard deny — always blocked ──────────────────────────────
DENY_PATTERNS = [
    r":\(\)\s*\{\s*:\|\:&\s*\}\s*;",      # fork bomb
    r"\bdd\s+if=",                         # disk destruction
    r">\s*/dev/sd[a-z]",
    r">\s*/dev/nvme",
    r"\bmkfs\b",
    r"\b(shutdown|reboot|halt|poweroff)\b", # system shutdown
    r"\brm\s+-rf\s+/(\*|\s|$)",            # rm -rf /
    r"\brm\s+-rf\s+/\*",
    r"\brm\s+-rf\s+~\s*/\*",
    r"\bchmod\s+-R?\s*777\s+/(\s|$)",     # chmod 777 /
    r":\(\)\s*\{",                         # fork bomb alt
    r"\bsudo\b",                           # privilege escalation
    r"\bsu\s+-",
    r"\bcurl\b.+\|\s*(bash|sh|zsh)\b",    # curl | bash
    r"\bwget\b.+\|\s*(bash|sh|zsh)\b",    # wget | bash
    r"\bcurl\b.*\b-o\b",                  # curl download
    r"\bwget\b.*\b-O\b",                  # wget download
    r"\bnc\s+-[eln]",                      # netcat reverse shell
    r"\bsocat\b",                          # socat
    r"\$\(.*\)",                           # $(cmd) injection
    r"`[^`]+`",                            # backtick injection
    r"\bsystemctl\s+(disable|mask|stop)\b",
    r"\bmodprobe\b", r"\binsmod\b",
    r">\s*/boot/", r">\s*/proc/", r">\s*/sys/",
    r"\bcrontab\b",
]

# ── Gate 2: Destructive — mode-dependent ─────────────────────────────
DESTRUCTIVE_PATTERNS = [
    (r"\brm\s+-r[fi]?\b", "Recursive file deletion"),
    (r"\brm\s+[^-]", "File deletion"),
    (r"\bchmod\s+777\b", "World-writable permissions"),
    (r"\bchmod\s+-R\s+777\b", "Recursive world-writable permissions"),
    (r"\bchown\b", "File ownership change"),
    (r"\bgit\s+push\s+--force\b", "Force push to remote"),
    (r"\bgit\s+reset\s+--hard\b", "Hard git reset"),
    (r">\s*/etc/", "Writing to /etc/"),
    (r"\bdocker\s+rm\b", "Docker container removal"),
    (r"\bdocker\s+system\s+prune\b", "Docker system prune"),
    (r"\bDROP\s+TABLE\b", "SQL DROP TABLE"),
    (r"\bDROP\s+DATABASE\b", "SQL DROP DATABASE"),
    (r"\bTRUNCATE\s+TABLE\b", "SQL TRUNCATE TABLE"),
    (r"\bDEL\s+/[FSQ]\b", "Windows force delete"),
]

# ── Mode labels & colors for UI ──────────────────────────────────────
MODE_LABELS = {
    SandboxMode.DENY: "\033[31mdeny\033[0m",   # red
    SandboxMode.ASK:  "\033[33mask\033[0m",    # yellow
    SandboxMode.AUTO: "\033[32mauto\033[0m",   # green
}


def format_mode(mode: SandboxMode) -> str:
    """Return colored mode string for display."""
    color = {SandboxMode.DENY: "31", SandboxMode.ASK: "33", SandboxMode.AUTO: "32"}
    c = color.get(mode, "37")
    return f"\033[{c}m{mode.value}\033[0m"


# ── Check functions ──────────────────────────────────────────────────

def check_deny_list(command: str) -> str | None:
    """Gate 1: Hard deny check. Returns reason to block or None."""
    for pattern in DENY_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Blocked: matches deny pattern '{pattern}'"
    return None


def check_destructive(command: str) -> str | None:
    """Gate 2: Destructive pattern check. Returns description or None."""
    for pattern, description in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"{description}: '{pattern}'"
    return None


def check_path_escape(tool_name: str, args: dict, workdir: Path) -> str | None:
    """Gate 3: Workspace escape check."""
    if tool_name in ("write_file", "edit_file", "read_file"):
        path = args.get("path", "")
        if path:
            resolved = (workdir / path).resolve()
            if not resolved.is_relative_to(workdir.resolve()):
                return f"Path escapes workspace: {path}"
    return None


# ── Input override for testing ──────────────────────────────────────

_input_fn: Callable[[str], str] = input


def set_input_function(fn: Callable[[str], str]) -> None:
    global _input_fn
    _input_fn = fn


def reset_input_function() -> None:
    global _input_fn
    _input_fn = input


def _prompt(question: str) -> str | None:
    try:
        return _input_fn(question).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None


# ── Mode-cycling callback (set by CLI) ──────────────────────────────

_mode_callback: Callable[[], SandboxMode] | None = None


def set_mode_callback(cb: Callable[[], SandboxMode]) -> None:
    """Register a callback that cycles to the next mode when Shift+Tab is pressed."""
    global _mode_callback
    _mode_callback = cb


# ── Main permission hook ────────────────────────────────────────────

def permission_hook(
    block,
    workdir: Path,
    mode: SandboxMode = SandboxMode.ASK,
    permission_store=None,
    permission_level=None,
) -> str | None:
    """PreToolUse hook: mode-aware 3-gate permission check with rule store.

    Args:
        block: Tool call block with .name and .input attributes
        workdir: Working directory for path escape checks
        mode: Sandbox mode (deny/ask/auto)
        permission_store: Optional PermissionStore for rule checking
        permission_level: Optional PermissionLevel for fine-grained control

    Returns:
        None = allow execution
        str  = block with this reason
    """
    tool_name = block.name
    args = block.input

    # Resolve permission level from mode if not explicitly provided
    from ..core.permissions import PermissionLevel
    if permission_level is None:
        permission_level = PermissionLevel.from_sandbox_mode(mode.value)

    # ── Check persistent permission rules first ──────────────────
    if permission_store is not None:
        command_or_path = ""
        if tool_name == "bash":
            command_or_path = args.get("command", "")
        elif tool_name in ("write_file", "edit_file", "read_file", "multi_edit"):
            command_or_path = args.get("path", "")

        rule_result = permission_store.check(
            tool_name, command_or_path, permission_level
        )
        if rule_result is not None and "Denied" in rule_result:
            print(f"\033[31m⛔ {rule_result}\033[0m")
            return rule_result
        # Explicit allow from rules
        if rule_result is None and permission_store.get_applicable(tool_name, command_or_path):
            # Has an explicit allow rule
            pass

    # ── Gate 1: Hard deny (always enforced regardless of level) ──
    if tool_name == "bash":
        command = args.get("command", "")
        reason = check_deny_list(command)
        if reason:
            print(f"\033[31m⛔ {reason}\033[0m")
            return "Permission denied by deny list"

    # ── Gate 2: Destructive (level-dependent) ────────────────────
    if tool_name == "bash":
        command = args.get("command", "")
        reason = check_destructive(command)
        if reason:
            if permission_level in (PermissionLevel.HIGH, PermissionLevel.CRITICAL):
                print(f"\033[31m⛔ [{permission_level.value}] {reason}\033[0m")
                return f"Permission denied: {reason}"

            elif permission_level == PermissionLevel.MEDIUM:
                print(f"\033[33m⚠  {reason}\033[0m")
                print(f"   Tool: {tool_name}({args})")
                print("   [y=allow N=deny Shift+Tab=cycle mode]")
                choice = _prompt("   ▸ ")
                if choice in ("", "n", "no"):
                    return "Permission denied by user"
                if choice in ("y", "yes"):
                    # Optionally save as persistent rule
                    if permission_store and choice == "allow-always":
                        from ..core.permissions import PermissionRule
                        permission_store.add_rule(PermissionRule(
                            tool=tool_name,
                            pattern=command[:80],
                            action="allow",
                        ))
                    return None
                return "Permission denied (invalid response)"

            elif permission_level == PermissionLevel.LOW:
                print(f"\033[33m⚡ [{permission_level.value}] {reason} — auto-approved\033[0m")

    # ── Gate 3: Path escape (level-dependent) ────────────────────
    reason = check_path_escape(tool_name, args, workdir)
    if reason:
        if permission_level in (PermissionLevel.HIGH, PermissionLevel.CRITICAL):
            print(f"\033[31m⛔ [{permission_level.value}] {reason}\033[0m")
            return f"Permission denied: {reason}"

        elif permission_level == PermissionLevel.MEDIUM:
            print(f"\033[33m⚠  {reason}\033[0m")
            print(f"   Tool: {tool_name}({args})")
            print("   [y=allow N=deny]")
            choice = _prompt("   ▸ ")
            if choice not in ("y", "yes"):
                return "Permission denied by user"

        elif permission_level == PermissionLevel.LOW:
            # Path escape blocked even in low (too dangerous)
            print(f"\033[31m⛔ [{permission_level.value}] {reason} — blocked\033[0m")
            return f"Permission denied: {reason}"

    # ── Critical level: deny everything else ─────────────────────
    if permission_level == PermissionLevel.CRITICAL:
        print("\033[31m⛔ [critical] All operations blocked\033[0m")
        return "Permission denied: critical mode"

    return None
