"""Plugin system — discover and load plugins from ~/.terry/plugins/ and project plugins/.

Plugin format (plugin.yaml):
  name: my-plugin
  version: "0.1.0"
  description: My custom plugin
  tools:
    - my_tool.py
  hooks:
    - my_hook.py
  skills:
    - my-skill/
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Plugin:
    """A loaded plugin with metadata."""
    name: str
    version: str
    description: str
    path: Path
    tools: list[Path] = field(default_factory=list)
    hooks: list[Path] = field(default_factory=list)
    skills: list[Path] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dir(cls, plugin_dir: Path) -> Plugin | None:
        """Load a plugin from its directory."""
        yaml_path = plugin_dir / "plugin.yaml"
        if not yaml_path.exists():
            return None

        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None

            tools = [plugin_dir / t for t in data.get("tools", [])]
            hooks = [plugin_dir / h for h in data.get("hooks", [])]
            skills = [plugin_dir / s for s in data.get("skills", [])]

            return cls(
                name=data.get("name", plugin_dir.name),
                version=data.get("version", "0.1.0"),
                description=data.get("description", ""),
                path=plugin_dir,
                tools=tools,
                hooks=hooks,
                skills=skills,
                metadata=data,
            )
        except Exception:
            return None

    def load_tools(self, tool_registry: Any) -> int:
        """Load plugin tools into tool registry. Returns count loaded."""
        count = 0
        for tool_file in self.tools:
            if not tool_file.exists():
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"plugin_{self.name}_{tool_file.stem}", str(tool_file)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)
                    count += 1
            except Exception:
                pass
        return count

    def load_hooks(self, hook_registry: Any) -> int:
        """Load plugin hooks into hook registry. Returns count loaded."""
        count = 0
        for hook_file in self.hooks:
            if not hook_file.exists():
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"plugin_hook_{self.name}_{hook_file.stem}", str(hook_file)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)
                    # Look for register_hooks() function convention
                    if hasattr(module, "register_hooks"):
                        module.register_hooks(hook_registry)
                        count += 1
            except Exception:
                pass
        return count


class PluginManager:
    """Discovers and manages plugins."""

    def __init__(self, plugin_dirs: list[Path] | None = None):
        self.plugin_dirs = plugin_dirs or [
            Path.home() / ".terry" / "plugins",       # User plugins
            Path.cwd() / ".terry" / "plugins",         # Project plugins
        ]
        self.plugins: dict[str, Plugin] = {}

    def discover(self) -> list[Plugin]:
        """Discover all plugins from configured directories. Returns newly found plugins."""
        found = []
        for base_dir in self.plugin_dirs:
            if not base_dir.exists():
                continue
            for plugin_dir in base_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                if plugin_dir.name in self.plugins:
                    continue  # Already loaded
                plugin = Plugin.from_dir(plugin_dir)
                if plugin:
                    self.plugins[plugin.name] = plugin
                    found.append(plugin)
        return found

    def list_plugins(self) -> list[Plugin]:
        """List all discovered plugins."""
        return list(self.plugins.values())

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self.plugins.get(name)

    def load_all(self, tool_registry: Any = None, hook_registry: Any = None) -> dict[str, dict]:
        """Discover and load all plugins. Returns load summary."""
        self.discover()
        summary = {}
        for name, plugin in self.plugins.items():
            summary[name] = {
                "tools_loaded": plugin.load_tools(tool_registry) if tool_registry else 0,
                "hooks_loaded": plugin.load_hooks(hook_registry) if hook_registry else 0,
            }
        return summary


# Global instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager(plugin_dirs: list[Path] | None = None) -> PluginManager:
    """Get or create the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(plugin_dirs)
    return _plugin_manager


def set_plugin_manager(instance: PluginManager) -> None:
    """Inject a custom PluginManager (for testing/DI)."""
    global _plugin_manager
    _plugin_manager = instance


def reset_plugin_manager() -> None:
    """Reset plugin manager singleton."""
    global _plugin_manager
    _plugin_manager = None
