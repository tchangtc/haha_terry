"""Additional coverage tests: context_engine, workflow_v2, oauth, profile, mcp_config."""

from __future__ import annotations

import tempfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# CONTEXT ENGINE — project indexing and query
# ═══════════════════════════════════════════════════════════════════

class TestContextEngine:
    def test_init(self):
        from terry.core.context_engine import ProjectContextEngine
        with tempfile.TemporaryDirectory() as d:
            engine = ProjectContextEngine(workdir=Path(d))
            assert engine is not None

    def test_build_index(self):
        from terry.core.context_engine import ProjectContextEngine
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.py").write_text("def main():\n    pass\n")
            engine = ProjectContextEngine(workdir=Path(d))
            built = engine.build_index(force=True)
            assert built

    def test_build_index_no_force(self):
        from terry.core.context_engine import ProjectContextEngine
        with tempfile.TemporaryDirectory() as d:
            engine = ProjectContextEngine(workdir=Path(d))
            engine.build_index(force=True)
            rebuilt = engine.build_index(force=False)
            assert not rebuilt  # Already fresh

    def test_query_returns_results(self):
        from terry.core.context_engine import ProjectContextEngine
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.py").write_text("def login():\n    return 'token'\n")
            (Path(d) / "main.py").write_text("import auth\n\ndef main():\n    pass\n")
            engine = ProjectContextEngine(workdir=Path(d))
            engine.build_index(force=True)
            results = engine.query("auth login")
            assert len(results) > 0

    def test_get_context_prompt(self):
        from terry.core.context_engine import ProjectContextEngine
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.py").write_text("def main():\n    pass\n")
            engine = ProjectContextEngine(workdir=Path(d))
            engine.build_index(force=True)
            prompt = engine.get_context_prompt("main")
            assert len(prompt) > 0 or "main" in prompt

    def test_stats(self):
        from terry.core.context_engine import ProjectContextEngine
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.py").write_text("pass\n")
            engine = ProjectContextEngine(workdir=Path(d))
            engine.build_index(force=True)
            stats = engine.get_stats()
            assert stats["files_indexed"] >= 1


# ═══════════════════════════════════════════════════════════════════
# OAUTH — token lifecycle
# ═══════════════════════════════════════════════════════════════════

class TestOAuth:
    def test_providers_exist(self):
        from terry.oauth import PROVIDERS
        assert "anthropic" in PROVIDERS
        assert "moonshot" in PROVIDERS

    def test_token_save_load_delete(self):
        from terry.oauth import save_token, load_token, delete_token
        import time
        token = {"access_token": "tok", "refresh_token": "ref",
                 "expires_in": 3600, "obtained_at": time.time()}
        save_token("test-prov", token)
        loaded = load_token("test-prov")
        assert loaded is not None
        assert loaded["access_token"] == "tok"
        delete_token("test-prov")
        assert load_token("test-prov") is None

    def test_token_storage_dir(self):
        from terry.oauth import _get_token_dir
        d = _get_token_dir()
        assert d is not None


# ═══════════════════════════════════════════════════════════════════
# PROFILE — built-in profiles
# ═══════════════════════════════════════════════════════════════════

class TestProfile:
    def test_builtin_profiles_exist(self):
        from terry.profile import BUILTIN_PROFILES
        assert "coder" in BUILTIN_PROFILES
        assert "reviewer" in BUILTIN_PROFILES
        assert "architect" in BUILTIN_PROFILES
        assert "debugger" in BUILTIN_PROFILES
        assert "devops" in BUILTIN_PROFILES

    def test_profile_fields(self):
        from terry.profile import BUILTIN_PROFILES
        coder = BUILTIN_PROFILES["coder"]
        assert coder.name == "coder"
        assert len(coder.description) > 0
        assert len(coder.system_prompt) > 0

    def test_profile_manager_list(self):
        from terry.profile import ProfileManager
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pm = ProfileManager(profiles_dir=Path(d))
            profiles = pm.list_all()
            assert len(profiles) >= 5

    def test_profile_manager_get(self):
        from terry.profile import ProfileManager
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pm = ProfileManager(profiles_dir=Path(d))
            p = pm.get("coder")
            assert p is not None
            assert p.name == "coder"

    def test_profile_manager_get_nonexistent(self):
        from terry.profile import ProfileManager
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pm = ProfileManager(profiles_dir=Path(d))
            assert pm.get("nonexistent") is None


# ═══════════════════════════════════════════════════════════════════
# MCP CONFIG — CRUD operations
# ═══════════════════════════════════════════════════════════════════

class TestMCPConfig:
    def test_server_config_init(self):
        from terry.mcp_config import McpServerConfig
        cfg = McpServerConfig(name="srv", command="echo hello")
        assert cfg.name == "srv"
        assert cfg.command == "echo hello"

    def test_server_config_to_dict(self):
        from terry.mcp_config import McpServerConfig
        cfg = McpServerConfig(name="srv", command="echo", args=["-n"],
                              env={"KEY": "val"}, description="desc")
        d = cfg.to_dict()
        assert d["name"] == "srv"
        assert "args" in d
        assert "env" in d

    def test_server_config_from_dict(self):
        from terry.mcp_config import McpServerConfig
        data = {"name": "srv", "command": "echo", "description": "test"}
        cfg = McpServerConfig.from_dict(data)
        assert cfg.name == "srv"

    def test_config_manager_add_list(self):
        from terry.mcp_config import McpConfigManager, McpServerConfig
        with tempfile.TemporaryDirectory() as d:
            mgr = McpConfigManager(config_path=Path(d) / "mcp.json")
            mgr.add_server(McpServerConfig(name="srv1", command="echo"))
            servers = mgr.list_servers()
            assert len(servers) == 1

    def test_config_manager_get_remove(self):
        from terry.mcp_config import McpConfigManager, McpServerConfig
        with tempfile.TemporaryDirectory() as d:
            mgr = McpConfigManager(config_path=Path(d) / "mcp.json")
            mgr.add_server(McpServerConfig(name="srv1", command="echo"))
            assert mgr.get_server("srv1") is not None
            mgr.remove_server("srv1")
            assert len(mgr.list_servers()) == 0

    def test_config_manager_test_nonexistent(self):
        from terry.mcp_config import McpConfigManager
        with tempfile.TemporaryDirectory() as d:
            mgr = McpConfigManager(config_path=Path(d) / "mcp.json")
            result = mgr.test_server("nonexistent")
            assert result["status"] == "error"
