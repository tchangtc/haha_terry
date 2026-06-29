"""Unit tests for v2.2.0: auto_backup, search_providers, vim toggle."""

from __future__ import annotations

import tempfile
from pathlib import Path


class TestAutoBackup:
    def test_import(self):
        from terry.core.auto_backup import AutoBackup
        assert AutoBackup is not None

    def test_create_and_list(self):
        from terry.core.auto_backup import AutoBackup
        with tempfile.TemporaryDirectory() as d:
            backup = AutoBackup(backup_dir=Path(d) / "backups",
                                source_dir=Path(d) / "data",
                                max_backups=5)
            (Path(d) / "data").mkdir(exist_ok=True)
            (Path(d) / "data" / "config.json").write_text('{"key": "val"}')

            name = backup.run()
            assert name is not None
            backups = backup.list_backups()
            assert len(backups) == 1
            assert backups[0]["name"] == name

    def test_delete_and_rotation(self):
        from terry.core.auto_backup import AutoBackup
        with tempfile.TemporaryDirectory() as d:
            backup = AutoBackup(backup_dir=Path(d) / "backups",
                                source_dir=Path(d) / "data",
                                max_backups=3)
            (Path(d) / "data").mkdir(exist_ok=True)

            for _ in range(5):
                backup.run()

            backups = backup.list_backups()
            assert len(backups) <= 3  # Rotation should cap at max

    def test_stats(self):
        from terry.core.auto_backup import AutoBackup
        with tempfile.TemporaryDirectory() as d:
            backup = AutoBackup(backup_dir=Path(d) / "backups",
                                source_dir=Path(d) / "data")
            (Path(d) / "data").mkdir(exist_ok=True)
            backup.run()
            stats = backup.get_stats()
            assert stats["total_backups"] >= 1
            assert stats["total_size_mb"] >= 0
            assert stats["max_backups"] == 10


class TestSearchProviders:
    def test_default_providers(self):
        from terry.core.search_providers import SearchProviderRegistry
        reg = SearchProviderRegistry()
        providers = reg.list_all()
        assert len(providers) >= 3  # duckduckgo, google, searxng
        assert reg.get_default().name == "duckduckgo"

    def test_register_and_switch(self):
        from terry.core.search_providers import SearchProviderRegistry
        reg = SearchProviderRegistry()
        reg.register("test-search", "https://example.com/search?q={query}")
        assert reg.get("test-search") is not None
        reg.set_default("test-search")
        assert reg.get_default().name == "test-search"
        # Reset to avoid polluting other tests
        reg.set_default("duckduckgo")

    def test_search_url(self):
        from terry.core.search_providers import SearchProviderRegistry
        reg = SearchProviderRegistry()
        url = reg.search_url("hello world")
        assert "hello+world" in url or "hello%20world" in url

    def test_stats(self):
        from terry.core.search_providers import SearchProviderRegistry
        reg = SearchProviderRegistry()
        stats = reg.get_stats()
        assert stats["total_providers"] >= 3
        assert stats["default"] == "duckduckgo"


class TestVimToggle:
    def test_vim_toggle_exists(self):
        from terry.cli_commands import _cmd_vim
        from unittest.mock import MagicMock
        agent = MagicMock()
        result = _cmd_vim("/vim", None, agent)
        assert result is True


class TestBackupSlashCmd:
    def test_backup_slash(self):
        from terry.cli_commands import _cmd_backup
        from unittest.mock import MagicMock
        agent = MagicMock()
        result = _cmd_backup("/backup", None, agent)
        assert result is True
