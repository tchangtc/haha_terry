"""Slash Command tool — lets the LLM invoke registered CLI slash commands.

Exposes the CommandRegistry to the agent so the LLM can call /help, /doctor,
/tasks, /agents, /config, and other registered commands from within the
conversation.
"""

from __future__ import annotations

from . import BaseTool, tool_registry


class SlashCommandTool(BaseTool):
    """Invoke a registered slash command from the conversation."""

    name = "slash_command"
    description = (
        "Invoke a registered Terry slash command. "
        "Use for /help, /doctor, /tasks, /agents, /config, /model, etc."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The slash command to run, e.g. /doctor, /tasks, /model.",
            },
            "args": {
                "type": "string",
                "description": "Optional arguments for the command.",
            },
        },
        "required": ["command"],
    }

    def __init__(self, agent=None):
        self._agent = agent

    def execute(self, command: str, args: str = "") -> str:
        # Security: block destructive commands from being called by the LLM
        blocked = {"/exit", "/quit", "/q", "/bash", "/mode"}
        cmd_clean = command.strip().lower()
        if cmd_clean in blocked:
            return f"Error: '{command}' is not available via this tool for safety reasons."

        try:
            from terry.cli_commands import cli_registry

            cmd_obj = cli_registry._commands.get(command.strip())
            if not cmd_obj:
                return f"Error: Unknown command '{command}'. Use /help to see available commands."

            if self._agent:
                result = cmd_obj.handler(command, args if args else None, self._agent)
                return f"Command '{command}' executed successfully." if result else f"Command '{command}' returned."
            return "Error: No agent context available."
        except Exception as e:
            return f"Error executing '{command}': {e}"


def register(agent=None):
    """Register the slash_command tool with the global registry."""
    tool = SlashCommandTool(agent=agent)
    tool_registry.register(tool)
    return tool
