"""Diagnostic system — checks across all agent subsystems."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    status: str
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class Doctor:
    def __init__(self, agent: Any): self.agent = agent

    def run_all(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        results.extend(self._check_config())
        results.extend(self._check_llm())
        results.extend(self._check_context())
        results.extend(self._check_permissions())
        results.extend(self._check_filesystem())
        results.extend(self._check_environment())
        results.extend(self._check_git())
        return results

    def _check_config(self) -> list[CheckResult]:
        try:
            issues = self.agent.config.validate()
            if not issues:
                return [CheckResult("config", "pass", "Configuration is valid")]
            return [CheckResult("config", "warn", f"{len(issues)} issue(s): {'; '.join(issues[:3])}")]
        except Exception as e:
            return [CheckResult("config", "fail", str(e))]

    def _check_llm(self) -> list[CheckResult]:
        try:
            if self.agent.llm:
                cfg = self.agent.config.model
                return [CheckResult("llm", "pass", f"{cfg.provider}/{cfg.model} (temp={cfg.temperature}, max_tok={cfg.max_tokens})")]
            return [CheckResult("llm", "fail", "LLM client not initialized")]
        except Exception as e:
            return [CheckResult("llm", "fail", str(e))]

    def _check_context(self) -> list[CheckResult]:
        try:
            compactor = self.agent.compactor
            if compactor and self.agent.messages:
                tokens = compactor.estimate_tokens(self.agent.messages)
                max_tok = compactor.max_tokens
                usage_pct = (tokens / max_tok * 100) if max_tok > 0 else 0
                needs = compactor.needs_compaction(self.agent.messages)
                return [CheckResult("context", "warn" if needs else "pass", f"{tokens:,}/{max_tok:,} tokens ({usage_pct:.1f}%), threshold={compactor.compression_threshold:.0%}, {len(self.agent.messages)} msgs")]
            return [CheckResult("context", "pass", "No context yet")]
        except Exception as e:
            return [CheckResult("context", "fail", str(e))]

    def _check_permissions(self) -> list[CheckResult]:
        try:
            mode = self.agent.get_mode()
            if self.agent.permission_store:
                rules = self.agent.permission_store.list_rules()
                return [CheckResult("permissions", "pass" if rules else "warn", f"Mode: {mode}, {len(rules)} rule(s)")]
            return [CheckResult("permissions", "warn", f"Mode: {mode}, no permission store")]
        except Exception as e:
            return [CheckResult("permissions", "fail", str(e))]

    def _check_filesystem(self) -> list[CheckResult]:
        results = []
        for sp in self.agent.config.skills_paths:
            p = Path(sp)
            if p.exists():
                skill_count = len(list(p.rglob("SKILL.md")))
                results.append(CheckResult("skills-dir", "pass" if skill_count > 0 else "warn", f"{sp} ({skill_count} skills)"))
            else:
                results.append(CheckResult("skills-dir", "warn", f"Missing: {sp}"))
        if self.agent.workdir and self.agent.workdir.exists():
            results.append(CheckResult("workdir", "pass", str(self.agent.workdir)))
        else:
            results.append(CheckResult("workdir", "fail", "Workdir not found"))
        if self.agent.checkpoint_manager:
            cps = self.agent.checkpoint_manager.list_checkpoints()
            results.append(CheckResult("checkpoints", "pass" if cps else "warn", f"{len(cps)} checkpoint(s)"))
        return results

    def _check_environment(self) -> list[CheckResult]:
        results = []
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        results.append(CheckResult("python", "pass" if sys.version_info >= (3, 11) else "warn", f"Python {py_ver} on {platform.system()}"))
        found = False
        for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
            if os.environ.get(var):
                results.append(CheckResult("api-key", "pass", f"{var} is set"))
                found = True
                break
        if not found:
            results.append(CheckResult("api-key", "warn", "No API key env var found"))
        from terry import __version__
        results.append(CheckResult("version", "pass", f"Terry v{__version__}"))
        return results

    def _check_git(self) -> list[CheckResult]:
        try:
            r = subprocess.run(["git", "status", "--porcelain"], cwd=self.agent.workdir, capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                changes = [line for line in r.stdout.strip().split("\n") if line]
                return [CheckResult("git", "warn" if changes else "pass", "Clean" if not changes else f"{len(changes)} uncommitted change(s)")]
            return [CheckResult("git", "warn", "Not a git repository")]
        except FileNotFoundError:
            return [CheckResult("git", "warn", "Git not installed")]
        except Exception as e:
            return [CheckResult("git", "warn", f"Git check failed: {e}")]
