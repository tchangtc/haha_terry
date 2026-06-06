"""Tool system - base class, registry, and auto-discovery."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""
    input_schema: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool and return the result as a string."""
        pass


class ToolRegistry:
    """Central tool registry with auto-discovery."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for LLM function calling."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def execute(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        if not tool:
            return f"Error: Unknown tool '{tool_name}'"
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return f"Error: {e}"


# Global registry instance
tool_registry = ToolRegistry()


def discover_tools():
    """Import built-in tool modules to trigger auto-registration.

    Returns:
        ToolRegistry: The global tool registry with all discovered tools
    """
    from . import (  # noqa: F401
        bash,
        calculator,
        edit_file,
        find_tool,
        git,
        glob_tool,
        grep_tool,
        harness_tool,
        ls_tool,
        notebook,
        notes,
        read_file,
        reminder,
        timer,
        todo_write,
        weather,
        web_fetch,
        web_search,
        write_file,
    )

    # Optional: multimodal support (requires PyMuPDF for PDF text extraction)
    try:
        from . import read_image  # noqa: F401
    except ImportError:
        pass

    return tool_registry
