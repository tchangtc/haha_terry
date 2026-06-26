"""Conversational MCP Configuration UI for Terry.

Allows users to add, edit, and manage MCP (Model Context Protocol) servers
through natural language or a guided CLI, without editing JSON by hand.

Usage:
    terry mcp add <name> --command "python server.py"
    terry mcp list
    terry mcp remove <name>
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    """Configuration for a single MCP server."""

    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""  # For remote MCP servers
    auto_approve: bool = False
    description: str = ""

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"name": self.name}
        if self.command:
            d["command"] = self.command
        if self.args:
            d["args"] = self.args
        if self.env:
            d["env"] = self.env
        if self.url:
            d["url"] = self.url
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "McpServerConfig":
        return cls(
            name=data["name"],
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            url=data.get("url", ""),
            auto_approve=data.get("autoApprove", False),
            description=data.get("description", ""),
        )


class McpConfigManager:
    """Manage MCP server configurations via CLI or programmatic API."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            from terry.core.platform_utils import get_terry_dir
            config_path = get_terry_dir() / "mcp_servers.json"
        self._path = config_path
        self._servers: dict[str, McpServerConfig] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                servers = data if isinstance(data, list) else data.get("mcpServers", data.get("servers", []))
                for s in servers:
                    cfg = McpServerConfig.from_dict(s)
                    self._servers[cfg.name] = cfg
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        data = {"mcpServers": [s.to_dict() for s in self._servers.values()]}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def list_servers(self) -> list[McpServerConfig]:
        return list(self._servers.values())

    def add_server(self, config: McpServerConfig):
        """Add or update an MCP server configuration."""
        self._servers[config.name] = config
        self._save()

    def remove_server(self, name: str):
        """Remove an MCP server configuration."""
        self._servers.pop(name, None)
        self._save()

    def get_server(self, name: str) -> McpServerConfig | None:
        return self._servers.get(name)

    def test_server(self, name: str) -> dict:
        """Test an MCP server connection by launching it and checking capabilities."""
        cfg = self.get_server(name)
        if not cfg:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if cfg.command:
            try:
                cmd = [cfg.command] + cfg.args
                env = {**os.environ, **cfg.env}
                result = subprocess.run(
                    cmd,
                    input=json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 1}),
                    capture_output=True, text=True, timeout=10, env=env,
                )
                if result.returncode == 0:
                    return {"status": "ok", "message": "Server responded successfully"}
                return {"status": "error", "message": f"Exit code {result.returncode}: {result.stderr[:200]}"}
            except subprocess.TimeoutExpired:
                return {"status": "timeout", "message": "Server did not respond within 10s"}
            except FileNotFoundError:
                return {"status": "error", "message": f"Command not found: {cfg.command}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        if cfg.url:
            return {
                "status": "warning",
                "message": "URL-based servers cannot be tested via CLI — check from your editor",
            }

        return {"status": "error", "message": "No command or URL configured"}


def discover_mcp_json(path: Path | None = None) -> dict | None:
    """Discover MCP servers from a project's .mcp.json or mcp.json file."""
    search_path = path or Path.cwd()
    for config_name in (".mcp.json", "mcp.json"):
        config_file = search_path / config_name
        if config_file.exists():
            try:
                return json.loads(config_file.read_text())
            except json.JSONDecodeError:
                pass
    return None
