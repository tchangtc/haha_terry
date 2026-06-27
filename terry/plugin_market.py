"""Plugin Marketplace for Terry.

Discover, install, and manage plugins from GitHub repositories,
local directories, and npm packages. Each plugin has a trust level
based on source, verification status, and community ratings.

Usage:
    terry plugin search <query>
    terry plugin install <name>
    terry plugin list
    terry plugin uninstall <name>
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Plugin Types ────────────────────────────────────────────────────


class TrustLevel(StrEnum):
    VERIFIED = "verified"         # Signed by trusted author
    COMMUNITY = "community"       # Popular community plugin
    UNKNOWN = "unknown"           # New or unvetted


class PluginKind(StrEnum):
    SKILL = "skill"               # Terry skill (SKILL.md based)
    TOOL = "tool"                 # Custom tool (BaseTool subclass)
    HOOK = "hook"                 # Lifecycle hook
    THEME = "theme"               # UI theme
    PROFILE = "profile"           # Agent profile preset


@dataclass
class PluginManifest:
    """Descriptor for a plugin in the marketplace."""

    name: str
    version: str
    description: str = ""
    kind: PluginKind = PluginKind.SKILL
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    downloads: int = 0
    rating: float = 0.0
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "kind": self.kind.value,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "trust_level": self.trust_level.value,
            "downloads": self.downloads,
            "rating": self.rating,
            "tags": self.tags,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        return cls(
            name=data["name"],
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            kind=PluginKind(data.get("kind", "skill")),
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            trust_level=TrustLevel(data.get("trust_level", "unknown")),
            downloads=data.get("downloads", 0),
            rating=data.get("rating", 0.0),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
        )


# ── Plugin Registry ─────────────────────────────────────────────────


class PluginRegistry:
    """Local plugin registry managing installed plugins."""

    def __init__(self, plugins_dir: Path | None = None):
        if plugins_dir is None:
            base = os.environ.get("TERRY_HOME", os.path.join(Path.home(), ".local", "share", "terry"))
            plugins_dir = Path(base) / "plugins"
        self._dir = plugins_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"
        self._plugins: dict[str, PluginManifest] = {}
        self._load()

    def _load(self):
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text())
                self._plugins = {
                    k: PluginManifest.from_dict(v) for k, v in data.items()
                }
            except (json.JSONDecodeError, KeyError):
                self._plugins = {}

    def _save(self):
        data = {k: v.to_dict() for k, v in self._plugins.items()}
        self._index_path.write_text(json.dumps(data, indent=2))

    def list_installed(self) -> list[PluginManifest]:
        return list(self._plugins.values())

    def is_installed(self, name: str) -> bool:
        return name in self._plugins

    def install(self, manifest: PluginManifest, source_dir: Path):
        """Install a plugin from a local directory."""
        target = self._dir / manifest.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source_dir, target)

        # Run install hook if present
        install_script = target / "install.py"
        if install_script.exists():
            try:
                subprocess.run(
                    ["python3", str(install_script)],
                    cwd=target,
                    timeout=60,
                    capture_output=True,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.warning("Plugin install script failed for %s: %s", manifest.name, e)

        self._plugins[manifest.name] = manifest
        self._save()

    def uninstall(self, name: str):
        """Remove an installed plugin."""
        target = self._dir / name
        if target.exists():
            shutil.rmtree(target)
        self._plugins.pop(name, None)
        self._save()

    def get(self, name: str) -> PluginManifest | None:
        return self._plugins.get(name)


# ── Marketplace Sources ──────────────────────────────────────────────


@dataclass
class MarketplaceSource:
    """A source of plugins in the marketplace."""

    name: str
    url: str
    kind: str = "github"  # github, url, directory

    def fetch_index(self) -> list[PluginManifest]:
        """Fetch the plugin index from this source."""
        if self.kind == "github":
            return self._fetch_github()
        elif self.kind == "url":
            return self._fetch_url()
        elif self.kind == "directory":
            return self._fetch_directory()
        return []

    def _fetch_github(self) -> list[PluginManifest]:
        """Fetch marketplace.json from a GitHub repo."""
        # Convert github.com URL to raw.githubusercontent.com
        repo = self.url.replace("https://github.com/", "")
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/marketplace.json"
        return self._fetch_json(raw_url)

    def _fetch_url(self) -> list[PluginManifest]:
        return self._fetch_json(self.url)

    def _fetch_json(self, url: str) -> list[PluginManifest]:
        try:
            from urllib.request import urlopen
            with urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
            plugins = data if isinstance(data, list) else data.get("plugins", [])
            return [PluginManifest.from_dict(p) for p in plugins]
        except Exception as e:
            logger.warning("Failed to fetch marketplace from %s: %s", url, e)
            return []

    def _fetch_directory(self) -> list[PluginManifest]:
        path = Path(self.url)
        if not path.exists():
            return []
        manifests = []
        for subdir in path.iterdir():
            if subdir.is_dir():
                manifest_path = subdir / "plugin.json"
                if manifest_path.exists():
                    try:
                        manifests.append(
                            PluginManifest.from_dict(json.loads(manifest_path.read_text()))
                        )
                    except (json.JSONDecodeError, KeyError):
                        pass
        return manifests

    def install_plugin(self, manifest: PluginManifest, registry: PluginRegistry):
        """Install a specific plugin from this source."""
        if self.kind == "github":
            repo = self.url.replace("https://github.com/", "")
            with tempfile.TemporaryDirectory() as tmp:
                clone_url = f"https://github.com/{repo}.git"
                try:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", clone_url, tmp],
                        timeout=60, capture_output=True,
                    )
                    plugin_dir = Path(tmp)
                    if manifest.repository:
                        plugin_dir = plugin_dir / manifest.name
                    registry.install(manifest, plugin_dir)
                except (subprocess.TimeoutExpired, OSError) as e:
                    raise RuntimeError(f"Failed to install {manifest.name}: {e}") from e
        elif self.kind == "directory":
            plugin_dir = Path(self.url) / manifest.name
            if plugin_dir.exists():
                registry.install(manifest, plugin_dir)
            else:
                raise RuntimeError(f"Plugin directory not found: {plugin_dir}")


# ── Default sources ─────────────────────────────────────────────────

DEFAULT_SOURCES: list[MarketplaceSource] = [
    MarketplaceSource(
        name="terry-official",
        url="https://github.com/tchangtc/haha_terry",
        kind="github",
    ),
    MarketplaceSource(
        name="terry-local",
        url=str(Path(__file__).resolve().parent.parent / "marketplace"),
        kind="directory",
    ),
]


# ── Marketplace API ─────────────────────────────────────────────────


def search_plugins(query: str, sources: list[MarketplaceSource] | None = None) -> list[PluginManifest]:
    """Search for plugins across all marketplace sources."""
    if sources is None:
        sources = DEFAULT_SOURCES
    results = []
    for source in sources:
        for plugin in source.fetch_index():
            query_lower = query.lower()
            if (
                query_lower in plugin.name.lower()
                or query_lower in plugin.description.lower()
                or any(query_lower in tag.lower() for tag in plugin.tags)
            ):
                results.append(plugin)
    # Sort by trust + rating + downloads
    trust_order = {TrustLevel.VERIFIED: 0, TrustLevel.COMMUNITY: 1, TrustLevel.UNKNOWN: 2}
    results.sort(key=lambda p: (trust_order.get(p.trust_level, 9), -p.rating, -p.downloads))
    return results


def list_plugins(sources: list[MarketplaceSource] | None = None) -> list[PluginManifest]:
    """List all available plugins."""
    if sources is None:
        sources = DEFAULT_SOURCES
    results = []
    for source in sources:
        results.extend(source.fetch_index())
    return results


def install_plugin(name: str, registry: PluginRegistry | None = None) -> PluginManifest:
    """Install a plugin by name from available sources."""
    if registry is None:
        registry = PluginRegistry()
    for source in DEFAULT_SOURCES:
        plugins = source.fetch_index()
        for p in plugins:
            if p.name == name:
                source.install_plugin(p, registry)
                return p
    raise ValueError(f"Plugin '{name}' not found in any marketplace source")
