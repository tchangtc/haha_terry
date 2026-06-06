"""CLI Command Registry — organized command dispatch with metadata.

Replaces the flat if/elif chain in handle_command() with a
registered command pattern. Each command has a name, handler,
category, and description for auto-generated help.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Command:
    """A registered CLI command with metadata."""
    name: str
    handler: Callable
    description: str = ""
    category: str = "general"
    usage: str = ""
    aliases: list[str] = field(default_factory=list)

    @property
    def all_names(self) -> list[str]:
        return [self.name] + self.aliases


class CommandRegistry:
    """Central registry for CLI commands with category-based grouping.

    Usage:
        registry = CommandRegistry()
        registry.register(Command("/help", help_handler, "Show help", "basic"))
        registry.register(Command("/undo", undo_handler, "Undo last change", "safety"))

        # Dispatch
        result = registry.dispatch("/undo", agent)
    """

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, command: Command) -> None:
        """Register a command."""
        for name in command.all_names:
            self._commands[name] = command

        cat = command.category
        if cat not in self._categories:
            self._categories[cat] = []
        if command.name not in self._categories[cat]:
            self._categories[cat].append(command.name)

    def dispatch(self, user_input: str, agent: Any) -> bool | None:
        """Route a command to its handler.

        Returns:
            True = continue REPL
            False = exit REPL
            None = unknown command
        """
        parts = user_input.split(maxsplit=1)
        cmd_name = parts[0].lower()

        command = self._commands.get(cmd_name)
        if command is None:
            # Try prefix match for "did you mean?"
            matches = [n for n in self._commands if n.startswith(cmd_name)]
            if len(matches) == 1:
                command = self._commands[matches[0]]
            elif len(matches) > 1:
                return None  # Ambiguous

        if command is None:
            return None

        return command.handler(cmd_name, parts[1] if len(parts) > 1 else None, agent)

    def list_commands(self, category: str | None = None) -> list[dict]:
        """List commands, optionally filtered by category."""
        result = []
        cats = [category] if category else list(self._categories.keys())
        for cat in cats:
            for name in self._categories.get(cat, []):
                cmd = self._commands.get(name)
                if cmd:
                    result.append({
                        "name": cmd.name,
                        "description": cmd.description,
                        "category": cmd.category,
                        "aliases": cmd.aliases,
                    })
        return result

    def get_categories(self) -> list[str]:
        return list(self._categories.keys())

    def suggest(self, partial: str) -> list[str]:
        """Suggest commands matching a partial prefix."""
        return [n for n in self._commands if n.startswith(partial)]


# ── Global registry ────────────────────────────────────────────────

command_registry = CommandRegistry()
