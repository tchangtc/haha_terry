"""Agent Team 2.0 — role-based multi-agent collaboration.

Teams consist of agents with defined roles (architect, developer, reviewer, QA)
that collaborate on complex tasks. The team lead coordinates, delegates, and
synthesizes results.

Usage:
    from terry.core.agent_team import AgentTeam, TeamRole
    team = AgentTeam("Build REST API")
    team.add_member("architect", TeamRole.ARCHITECT, agent_factory)
    result = team.execute()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class TeamRole(StrEnum):
    LEAD = "lead"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    QA = "qa"


ROLE_PROMPTS: dict[TeamRole, str] = {
    TeamRole.LEAD: (
        "You are the team lead. Coordinate the team, break down tasks, "
        "delegate to specialists, and synthesize results. Do NOT write "
        "code — direct others to do it."
    ),
    TeamRole.ARCHITECT: (
        "You are the system architect. Design scalable systems, APIs, "
        "and data models. Consider tradeoffs and document decisions. "
        "Output: architecture diagrams (Mermaid), API specs, data schemas."
    ),
    TeamRole.DEVELOPER: (
        "You are a senior developer. Write clean, well-documented, "
        "well-tested code. Follow the architect's design. Add type hints, "
        "error handling, and inline comments."
    ),
    TeamRole.REVIEWER: (
        "You are a code reviewer. Find bugs, logic errors, security "
        "vulnerabilities, and style violations. Be specific: what is "
        "wrong, how to fix it, severity level."
    ),
    TeamRole.QA: (
        "You are a QA engineer. Verify that the implementation meets "
        "the requirements, edge cases are handled, and the code is "
        "well-tested. Report any gaps between spec and implementation."
    ),
}


@dataclass
class TeamMember:
    """An agent with a team role."""

    name: str
    role: TeamRole
    agent_factory: object = None  # Callable that returns an Agent
    status: str = "idle"  # idle, working, done, blocked
    current_task: str = ""


@dataclass
class TaskAssignment:
    """A task assigned to a team member."""

    id: str
    description: str
    assigned_to: str
    role: TeamRole
    status: str = "pending"  # pending, in_progress, done, failed
    result: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0


class AgentTeam:
    """Role-based multi-agent team for complex development tasks."""

    def __init__(self, mission: str, max_rounds: int = 3):
        self.mission = mission
        self.max_rounds = max_rounds
        self._members: dict[str, TeamMember] = {}
        self._tasks: list[TaskAssignment] = []
        self._task_counter = 0
        self._round = 0
        self._log: list[str] = []

    def add_member(self, name: str, role: TeamRole, agent_factory=None):
        """Add a team member with a role."""
        self._members[name] = TeamMember(
            name=name, role=role, agent_factory=agent_factory,
        )

    def remove_member(self, name: str):
        self._members.pop(name, None)

    def get_members(self) -> list[TeamMember]:
        return list(self._members.values())

    # ── Task Management ────────────────────────────────────────

    def assign_task(self, description: str, member: str, role: TeamRole) -> str:
        """Assign a task to a team member. Returns task ID."""
        self._task_counter += 1
        tid = f"task-{self._task_counter}"
        self._tasks.append(TaskAssignment(
            id=tid, description=description,
            assigned_to=member, role=role,
        ))
        if member in self._members:
            self._members[member].status = "working"
            self._members[member].current_task = description
        self._log.append(f"[assign] {tid}: {description} → {member}({role})")
        return tid

    # ── Execution ──────────────────────────────────────────────

    def execute_round(self, task_id: str) -> str:
        """Execute a single task round on its assigned agent."""
        task = self._get_task(task_id)
        if not task:
            return f"Task {task_id} not found"

        member = self._members.get(task.assigned_to)
        if not member or not member.agent_factory:
            result = f"[passthrough] {task.description} → {task.assigned_to}({task.role})"
            task.result = result
            task.status = "done"
            task.finished_at = time.time()
            member.status = "done" if member else "idle"
            return result

        try:
            agent = member.agent_factory()
            role_prompt = ROLE_PROMPTS.get(member.role, "")
            prompt = f"{role_prompt}\n\nTask: {task.description}"
            result = agent.run(prompt)
            task.result = str(result)[:2000]
            task.status = "done"
            member.status = "done"
        except Exception as e:
            task.result = f"Error: {e}"
            task.status = "failed"
            member.status = "blocked"

        task.finished_at = time.time()
        self._log.append(f"[done] {task.id}: status={task.status}")
        return task.result

    def execute(self) -> dict:
        """Orchestrate the full team workflow.

        Default pipeline: Architect → Developer → Reviewer → QA
        """
        results: dict[str, str] = {}

        # Phase 1: Architect designs
        if self._has_role(TeamRole.ARCHITECT):
            tid = self.assign_task(
                f"Design architecture for: {self.mission}",
                self._get_by_role(TeamRole.ARCHITECT), TeamRole.ARCHITECT,
            )
            results["architecture"] = self.execute_round(tid)

        # Phase 2: Developer implements
        if self._has_role(TeamRole.DEVELOPER):
            arch = results.get("architecture", "")
            tid = self.assign_task(
                f"Implement based on architecture:\n{arch[:500]}\n\nMission: {self.mission}",
                self._get_by_role(TeamRole.DEVELOPER), TeamRole.DEVELOPER,
            )
            results["implementation"] = self.execute_round(tid)

        # Phase 3: Reviewer checks
        if self._has_role(TeamRole.REVIEWER):
            impl = results.get("implementation", "")
            tid = self.assign_task(
                f"Review this implementation for bugs, security, and style:\n{impl[:500]}",
                self._get_by_role(TeamRole.REVIEWER), TeamRole.REVIEWER,
            )
            results["review"] = self.execute_round(tid)

        # Phase 4: QA verifies
        if self._has_role(TeamRole.QA):
            tid = self.assign_task(
                f"Verify implementation meets requirements: {self.mission}",
                self._get_by_role(TeamRole.QA), TeamRole.QA,
            )
            results["qa"] = self.execute_round(tid)

        return results

    # ── Helpers ────────────────────────────────────────────────

    def _has_role(self, role: TeamRole) -> bool:
        return any(m.role == role for m in self._members.values())

    def _get_by_role(self, role: TeamRole) -> str:
        for m in self._members.values():
            if m.role == role:
                return m.name
        return ""

    def _get_task(self, tid: str) -> TaskAssignment | None:
        for t in self._tasks:
            if t.id == tid:
                return t
        return None

    def get_tasks(self, status: str | None = None) -> list[TaskAssignment]:
        if status:
            return [t for t in self._tasks if t.status == status]
        return list(self._tasks)

    def get_log(self) -> list[str]:
        return list(self._log)

    def get_stats(self) -> dict:
        return {
            "mission": self.mission,
            "members": len(self._members),
            "tasks": len(self._tasks),
            "rounds": self._round,
        }
