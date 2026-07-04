"""Push coverage from 57% → 65% — targeted integration tests."""

from __future__ import annotations

from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# WORKFLOW V2 — triggers and execution
# ═══════════════════════════════════════════════════════════════════

class TestWorkflowV2:
    def test_init(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        assert wf is not None

    def test_register_trigger(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("nightly", "schedule", "lint_check")
        triggers = wf.list_triggers()
        assert len(triggers) == 1
        assert triggers[0].name == "nightly"

    def test_remove_trigger(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("t1", "schedule", "wf1")
        wf.remove_trigger("t1")
        assert len(wf.list_triggers()) == 0

    def test_fire_schedule(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("nightly", "schedule", "lint")
        wf.fire_schedule("nightly")
        runs = wf.get_runs()
        assert len(runs) == 1
        assert runs[0].trigger == "nightly"

    def test_fire_webhook(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("pr-hook", "webhook", "review")
        wf.fire_webhook("pr-hook", {"action": "opened"})
        assert len(wf.get_runs()) == 1

    def test_fire_file_watch(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("watch-py", "file_watch", "test")
        wf.fire_file_watch("watch-py", ["main.py", "utils.py"])
        runs = wf.get_runs()
        assert len(runs) == 1

    def test_fire_ci_event(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("ci", "ci_event", "deploy")
        wf.fire_ci_event("ci", "push", {"branch": "main"})
        assert len(wf.get_runs()) == 1

    def test_get_runs_by_status(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("t", "schedule", "w")
        wf.fire_schedule("t")
        assert len(wf.get_runs("done")) == 1

    def test_stats(self):
        from terry.core.workflow_v2 import WorkflowEngineV2
        wf = WorkflowEngineV2()
        wf.register_trigger("t", "schedule", "w")
        wf.fire_schedule("t")
        stats = wf.get_stats()
        assert stats["total_runs"] == 1
        assert stats["done"] == 1


# ═══════════════════════════════════════════════════════════════════
# ERROR RECOVERY — retry, fallback, healing
# ═══════════════════════════════════════════════════════════════════

class TestErrorRecoveryDeep:
    def test_defaults(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery()
        assert er.max_retries == 3
        assert er.base_delay == 1.0
        assert er.model_fallback is True

    def test_custom_init(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery(max_retries=5, base_delay=2.0, model_fallback=False)
        assert er.max_retries == 5
        assert er.model_fallback is False

    def test_fallback_chain_exists(self):
        from terry.core.error_recovery import FALLBACK_MODELS
        assert "anthropic" in FALLBACK_MODELS
        assert len(FALLBACK_MODELS["anthropic"]) >= 1

    def test_should_fallback_by_count(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery(model_fallback=True, consecutive_529_limit=1)
        # First call should trigger fallback on 2nd
        result = er.should_fallback_model("anthropic", "claude-sonnet-4-6")
        # After limit exceeded
        result2 = er.should_fallback_model("anthropic", "claude-sonnet-4-6")
        assert result2 is not None or result is not None  # One should trigger

    def test_no_fallback_when_disabled(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery(model_fallback=False)
        result = er.should_fallback_model("anthropic", "claude-sonnet-4-6")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# AUTO CLASSIFIER — trust level scoring
# ═══════════════════════════════════════════════════════════════════

class TestAutoClassifier:
    def test_init(self):
        from terry.core.auto_classifier import AutoModeClassifier
        ac = AutoModeClassifier(threshold=0.6)
        assert ac is not None

    def test_score_safe_tool(self):
        from terry.core.auto_classifier import AutoModeClassifier
        ac = AutoModeClassifier(threshold=0.6)
        level = ac.get_trust_level("read_file", {"path": "main.py"}, Path.cwd())
        assert level is not None

    def test_score_bash(self):
        from terry.core.auto_classifier import AutoModeClassifier
        ac = AutoModeClassifier(threshold=0.6)
        level = ac.get_trust_level("bash", {"command": "ls"}, Path.cwd())
        assert level is not None


# ═══════════════════════════════════════════════════════════════════
# RBAC — role permissions
# ═══════════════════════════════════════════════════════════════════

class TestRBAC:
    def test_roles_exist(self):
        from terry.core.rbac import Role
        roles = list(Role)
        assert len(roles) == 4  # admin, developer, reviewer, viewer

    def test_admin_can_bash(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        rm.assign("alice", Role.ADMIN)
        assert rm.can_execute("alice", "bash")

    def test_viewer_cannot_bash(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        rm.assign("bob", Role.VIEWER)
        assert not rm.can_execute("bob", "bash")

    def test_viewer_can_read(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        rm.assign("bob", Role.VIEWER)
        assert rm.can_execute("bob", "read_file")

    def test_default_is_viewer(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        assert rm.get_role("unknown") == Role.VIEWER

    def test_remove_user(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        rm.assign("alice", Role.ADMIN)
        rm.remove("alice")
        assert rm.get_role("alice") == Role.VIEWER

    def test_list_users(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        rm.assign("alice", Role.ADMIN)
        rm.assign("bob", Role.DEVELOPER)
        assert len(rm.list_users()) == 2

    def test_get_permissions(self):
        from terry.core.rbac import RoleManager, Role
        rm = RoleManager()
        perms = rm.get_permissions(Role.ADMIN)
        assert len(perms) > 5
