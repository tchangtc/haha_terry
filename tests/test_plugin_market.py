"""Tests for terry.plugin_market — manifests, local registry, directory sources.

All tests are network-free: marketplace sources use the ``directory`` kind and
the registry is pinned to a ``tmp_path`` so nothing touches the real filesystem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from terry.plugin_market import (
    DEFAULT_SOURCES,
    MarketplaceSource,
    PluginKind,
    PluginManifest,
    PluginRegistry,
    TrustLevel,
    install_plugin,
    list_plugins,
    search_plugins,
)


def _make_manifest(name: str = "demo", **overrides) -> PluginManifest:
    data = {
        "name": name,
        "version": "1.2.3",
        "description": "A demo plugin",
        "kind": PluginKind.TOOL,
        "author": "melyssa",
        "trust_level": TrustLevel.COMMUNITY,
        "tags": ["search", "demo"],
    }
    data.update(overrides)
    return PluginManifest(**data)


def _seed_marketplace(root: Path, manifests: list[PluginManifest]) -> MarketplaceSource:
    """Create a directory-kind marketplace laid out as <root>/<name>/plugin.json."""
    for m in manifests:
        pdir = root / m.name
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "plugin.json").write_text(json.dumps(m.to_dict()))
        # A payload file so registry.install has something to copy.
        (pdir / "SKILL.md").write_text(f"# {m.name}\n")
    return MarketplaceSource(name="local", url=str(root), kind="directory")


class TestPluginManifest:
    def test_to_dict_from_dict_roundtrip(self):
        m = _make_manifest(downloads=42, rating=4.5, dependencies=["x"])
        restored = PluginManifest.from_dict(m.to_dict())
        assert restored == m
        # enum fields survive the round trip as enums
        assert restored.kind is PluginKind.TOOL
        assert restored.trust_level is TrustLevel.COMMUNITY

    def test_from_dict_applies_defaults(self):
        m = PluginManifest.from_dict({"name": "minimal"})
        assert m.name == "minimal"
        assert m.version == "0.1.0"
        assert m.kind is PluginKind.SKILL
        assert m.trust_level is TrustLevel.UNKNOWN
        assert m.license == "MIT"
        assert m.tags == []

    def test_from_dict_requires_name(self):
        with pytest.raises(KeyError):
            PluginManifest.from_dict({"version": "1.0.0"})


class TestPluginRegistry:
    def test_install_lists_and_persists(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("payload")
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
        m = _make_manifest("alpha")

        reg.install(m, src)

        assert reg.is_installed("alpha")
        assert [p.name for p in reg.list_installed()] == ["alpha"]
        assert (tmp_path / "plugins" / "alpha" / "file.txt").read_text() == "payload"

        # A fresh registry over the same dir reloads from index.json.
        reloaded = PluginRegistry(plugins_dir=tmp_path / "plugins")
        assert reloaded.is_installed("alpha")
        assert reloaded.get("alpha").version == "1.2.3"

    def test_install_overwrites_existing_payload(self, tmp_path: Path):
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
        first = tmp_path / "v1"
        first.mkdir()
        (first / "marker").write_text("old")
        reg.install(_make_manifest("beta", version="1.0.0"), first)

        second = tmp_path / "v2"
        second.mkdir()
        (second / "marker").write_text("new")
        reg.install(_make_manifest("beta", version="2.0.0"), second)

        assert reg.get("beta").version == "2.0.0"
        assert (tmp_path / "plugins" / "beta" / "marker").read_text() == "new"

    def test_uninstall_removes_payload_and_entry(self, tmp_path: Path):
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
        src = tmp_path / "src"
        src.mkdir()
        reg.install(_make_manifest("gamma"), src)

        reg.uninstall("gamma")

        assert not reg.is_installed("gamma")
        assert reg.get("gamma") is None
        assert not (tmp_path / "plugins" / "gamma").exists()

    def test_uninstall_unknown_is_noop(self, tmp_path: Path):
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
        reg.uninstall("does-not-exist")  # must not raise
        assert reg.list_installed() == []

    def test_corrupt_index_is_tolerated(self, tmp_path: Path):
        plugins = tmp_path / "plugins"
        plugins.mkdir()
        (plugins / "index.json").write_text("{ this is not json")
        reg = PluginRegistry(plugins_dir=plugins)  # must not raise
        assert reg.list_installed() == []


class TestMarketplaceSourceDirectory:
    def test_fetch_directory_reads_manifests(self, tmp_path: Path):
        src = _seed_marketplace(tmp_path, [_make_manifest("a"), _make_manifest("b")])
        names = sorted(p.name for p in src.fetch_index())
        assert names == ["a", "b"]

    def test_fetch_directory_missing_path_returns_empty(self, tmp_path: Path):
        src = MarketplaceSource(name="x", url=str(tmp_path / "nope"), kind="directory")
        assert src.fetch_index() == []

    def test_fetch_directory_skips_bad_json(self, tmp_path: Path):
        _seed_marketplace(tmp_path, [_make_manifest("good")])
        bad = tmp_path / "bad"
        bad.mkdir()
        (bad / "plugin.json").write_text("{{ broken")
        names = [p.name for p in MarketplaceSource("x", str(tmp_path), "directory").fetch_index()]
        assert names == ["good"]

    def test_unknown_kind_returns_empty(self):
        assert MarketplaceSource(name="x", url="whatever", kind="mystery").fetch_index() == []

    def test_install_plugin_from_directory(self, tmp_path: Path):
        market = tmp_path / "market"
        src = _seed_marketplace(market, [_make_manifest("widget")])
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")

        src.install_plugin(_make_manifest("widget"), reg)

        assert reg.is_installed("widget")
        assert (tmp_path / "plugins" / "widget" / "SKILL.md").exists()

    def test_install_plugin_missing_directory_raises(self, tmp_path: Path):
        src = MarketplaceSource(name="x", url=str(tmp_path / "market"), kind="directory")
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
        with pytest.raises(RuntimeError, match="not found"):
            src.install_plugin(_make_manifest("ghost"), reg)


class TestMarketplaceApi:
    def test_search_matches_name_description_and_tags(self, tmp_path: Path):
        src = _seed_marketplace(
            tmp_path,
            [
                _make_manifest("search-tool", description="grep things", tags=["cli"]),
                _make_manifest("other", description="unrelated", tags=["misc"]),
            ],
        )
        by_name = [p.name for p in search_plugins("search", sources=[src])]
        assert by_name == ["search-tool"]
        by_tag = {p.name for p in search_plugins("cli", sources=[src])}
        assert by_tag == {"search-tool"}
        assert search_plugins("nothing-here", sources=[src]) == []

    def test_search_orders_verified_before_unknown(self, tmp_path: Path):
        src = _seed_marketplace(
            tmp_path,
            [
                _make_manifest("low", tags=["shared"], trust_level=TrustLevel.UNKNOWN),
                _make_manifest("high", tags=["shared"], trust_level=TrustLevel.VERIFIED),
            ],
        )
        ordered = [p.name for p in search_plugins("shared", sources=[src])]
        assert ordered == ["high", "low"]

    def test_list_plugins_returns_all(self, tmp_path: Path):
        src = _seed_marketplace(tmp_path, [_make_manifest("a"), _make_manifest("b")])
        assert len(list_plugins(sources=[src])) == 2

    def test_install_plugin_by_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        market = tmp_path / "market"
        src = _seed_marketplace(market, [_make_manifest("named")])
        monkeypatch.setattr("terry.plugin_market.DEFAULT_SOURCES", [src])
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")

        result = install_plugin("named", registry=reg)

        assert result.name == "named"
        assert reg.is_installed("named")

    def test_install_plugin_by_name_unknown_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        src = _seed_marketplace(tmp_path, [_make_manifest("present")])
        monkeypatch.setattr("terry.plugin_market.DEFAULT_SOURCES", [src])
        reg = PluginRegistry(plugins_dir=tmp_path / "plugins")
        with pytest.raises(ValueError, match="not found"):
            install_plugin("absent", registry=reg)


def test_default_sources_are_declared():
    # Two shipped sources: the official GitHub repo + a bundled local directory.
    kinds = {s.kind for s in DEFAULT_SOURCES}
    assert kinds == {"github", "directory"}
