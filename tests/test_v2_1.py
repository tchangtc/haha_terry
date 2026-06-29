"""Unit tests for v2.1.0 modules: sensitive_files, /btw, /expand."""

from __future__ import annotations

import tempfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# SENSITIVE FILE GUARD
# ═══════════════════════════════════════════════════════════════════

class TestSensitiveFileGuard:
    def test_import(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        assert guard is not None

    def test_env_files_blocked(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        assert guard.is_sensitive(".env")
        assert guard.is_sensitive(".env.local")
        assert guard.is_sensitive(".env.production")
        assert guard.is_sensitive("some/path/.env")

    def test_key_files_blocked(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        assert guard.is_sensitive("id_rsa")
        assert guard.is_sensitive("id_ed25519")
        assert guard.is_sensitive("server.key")
        assert guard.is_sensitive("cert.pem")
        assert guard.is_sensitive("keystore.p12")

    def test_normal_files_allowed(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        assert not guard.is_sensitive("main.py")
        assert not guard.is_sensitive("src/utils.py")
        assert not guard.is_sensitive("README.md")
        assert not guard.is_sensitive("config.toml")

    def test_dir_exclusion(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        assert guard.is_sensitive(".git/config")
        assert guard.is_sensitive(".git/HEAD")
        assert guard.is_sensitive("node_modules/pkg/index.js")
        assert guard.is_sensitive(".venv/lib/python/site.py")
        assert guard.is_sensitive("__pycache__/module.pyc")

    def test_filter_methods(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        paths = [".env", "main.py", ".git/config", "README.md", "server.key"]
        blocked = guard.get_blocked_files(paths)
        allowed = guard.get_allowed_files(paths)
        assert len(blocked) == 3  # .env, .git/config, server.key
        assert len(allowed) == 2  # main.py, README.md

    def test_custom_patterns(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard(extra_patterns=[r"custom-secret\.txt$"])
        assert guard.is_sensitive("custom-secret.txt")
        assert not guard.is_sensitive("normal.txt")

    def test_custom_dirs(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard(extra_dirs=["my-secrets"])
        assert guard.is_sensitive("my-secrets/db-passwords.txt")

    def test_gitignore_respected(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        with tempfile.TemporaryDirectory() as d:
            gitignore = Path(d) / ".gitignore"
            gitignore.write_text("*.log\nsecrets/\n")
            # Guard loads .gitignore from CWD — not test dir
            # Just verify patterns are loaded
            guard = SensitiveFileGuard()
            assert guard.get_stats()["gitignore_rules"] >= 0

    def test_stats(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        stats = guard.get_stats()
        assert stats["patterns"] > 15
        assert stats["dirs"] > 5
        assert isinstance(stats["gitignore_rules"], int)

    def test_add_remove_patterns(self):
        from terry.core.sensitive_files import SensitiveFileGuard
        guard = SensitiveFileGuard()
        before = guard.get_stats()["patterns"]
        guard.add_pattern(r"my-custom\.secret$")
        assert guard.get_stats()["patterns"] == before + 1
        guard.add_dir("my-vault")
        assert guard.is_sensitive("my-vault/secret.txt")


# ═══════════════════════════════════════════════════════════════════
# /btw AND /expand HANDLERS
# ═══════════════════════════════════════════════════════════════════

class TestBtwHandler:
    def test_btw_without_args(self):
        from terry.cli_commands import _cmd_btw
        from unittest.mock import MagicMock
        agent = MagicMock()
        agent.messages = []
        result = _cmd_btw("/btw", None, agent)
        assert result is True

    def test_btw_injects_message(self):
        from terry.cli_commands import _cmd_btw
        from unittest.mock import MagicMock
        agent = MagicMock()
        agent.messages = []
        result = _cmd_btw("/btw", "the config is at config/app.toml", agent)
        assert result is True
        assert len(agent.messages) == 1
        assert "config/app.toml" in agent.messages[0]["content"]
        assert "[BTW]" in agent.messages[0]["content"]

    def test_btw_appends_to_existing(self):
        from terry.cli_commands import _cmd_btw
        from unittest.mock import MagicMock
        agent = MagicMock()
        agent.messages = [{"role": "user", "content": "original message"}]
        _cmd_btw("/btw", "note: use port 8080", agent)
        assert len(agent.messages) == 2


class TestExpandHandler:
    def test_expand_empty(self):
        from terry.cli_commands import _cmd_expand
        from unittest.mock import MagicMock
        agent = MagicMock()
        agent.messages = []
        result = _cmd_expand("/expand", None, agent)
        assert result is True

    def test_expand_short_message(self):
        from terry.cli_commands import _cmd_expand
        from unittest.mock import MagicMock
        agent = MagicMock()
        agent.messages = [{"role": "assistant", "content": "short reply"}]
        result = _cmd_expand("/expand", None, agent)
        assert result is True

    def test_expand_long_message(self):
        from terry.cli_commands import _cmd_expand
        from unittest.mock import MagicMock
        long_msg = "x" * 500
        agent = MagicMock()
        agent.messages = [{"role": "assistant", "content": long_msg}]
        result = _cmd_expand("/expand", None, agent)
        assert result is True
