"""Advanced subsystem initialization extracted from Agent.__init__().

Reduces agent.py by ~50 lines by grouping 20+ advanced subsystems
into a single holder class that Agent delegates to.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .autonomous_agent import AutonomousAgent, SkillAutoCreator
from .code_index import CodeSemanticIndex
from .curator import SkillsCurator
from .docker_sandbox import DockerSandbox
from .dynamic_workflow import DynamicWorkflowEngine
from .fts_search import FTSSearch
from .knowledge_graph import KnowledgeGraph
from .local_embed import LocalEmbedder
from .memory_sync import MemorySync
from .model_router import ModelRouter
from .prompt_cache import PromptCache
from .rag import ProjectRAG
from .scheduler import CronScheduler
from .skill_market import SkillMarket
from .spec_exec import SpeculativeExecutor
from .suggester import ProactiveSuggester
from .task_dag import TaskDAG
from .thinking import ExtendedThinking
from .workflow import WorkflowEngine

logger = logging.getLogger(__name__)


@dataclass
class AgentSubsystems:
    """Holds advanced/optional subsystems to keep Agent.__init__ slim.

    Each field is lazily evaluated — subsystems that fail to initialize
    don't prevent the rest from working.
    """

    workdir: Path = field(default_factory=Path.cwd)
    agent_factory: Any = None

    # ── Intelligence ──
    extended_thinking: ExtendedThinking | None = None
    task_dag: TaskDAG | None = None
    knowledge_graph: KnowledgeGraph | None = None
    code_index: CodeSemanticIndex | None = None
    project_rag: ProjectRAG | None = None
    local_embedder: LocalEmbedder | None = None

    # ── Automation ──
    scheduler: CronScheduler | None = None
    skills_curator: SkillsCurator | None = None
    spec_exec: SpeculativeExecutor | None = None
    suggester: ProactiveSuggester | None = None
    workflow_engine: WorkflowEngine | None = None
    dynamic_workflow: DynamicWorkflowEngine | None = None

    # ── Tools ──
    prompt_cache: PromptCache | None = None
    fts_search: FTSSearch | None = None
    skill_market: SkillMarket | None = None
    model_router: ModelRouter | None = None
    docker_sandbox: DockerSandbox | None = None

    # ── Agent-of-agents ──
    autonomous_agent: AutonomousAgent | None = None
    skill_auto_creator: SkillAutoCreator | None = None

    @classmethod
    def create(cls, workdir: Path, model: str, agent_factory: Any = None) -> AgentSubsystems:
        """Factory: initialize all subsystems with graceful degradation."""
        subsystems = cls(workdir=workdir, agent_factory=agent_factory)

        try:
            subsystems.extended_thinking = ExtendedThinking(model=model)
        except Exception:
            logger.warning("extended_thinking init failed", exc_info=True)
            pass

        try:
            subsystems.task_dag = TaskDAG()
        except Exception:
            logger.warning("task_dag init failed", exc_info=True)
            pass

        try:
            subsystems.knowledge_graph = KnowledgeGraph()
        except Exception:
            logger.warning("knowledge_graph init failed", exc_info=True)
            pass

        try:
            subsystems.scheduler = CronScheduler()
        except Exception:
            logger.warning("scheduler init failed", exc_info=True)
            pass

        try:
            subsystems.skills_curator = SkillsCurator()
        except Exception:
            logger.warning("skills_curator init failed", exc_info=True)
            pass

        try:
            subsystems.workflow_engine = WorkflowEngine(agent=agent_factory() if agent_factory else None)
        except Exception:
            logger.warning("workflow_engine init failed", exc_info=True)
            pass

        try:
            subsystems.prompt_cache = PromptCache(model=model)
        except Exception:
            logger.warning("prompt_cache init failed", exc_info=True)
            pass

        try:
            subsystems.spec_exec = SpeculativeExecutor()
        except Exception:
            logger.warning("spec_exec init failed", exc_info=True)
            pass

        try:
            subsystems.suggester = ProactiveSuggester()
        except Exception:
            logger.warning("suggester init failed", exc_info=True)
            pass

        try:
            subsystems.fts_search = FTSSearch()
        except Exception:
            logger.warning("fts_search init failed", exc_info=True)
            pass

        try:
            subsystems.skill_market = SkillMarket()
        except Exception:
            logger.warning("skill_market init failed", exc_info=True)
            pass

        try:
            subsystems.local_embedder = LocalEmbedder()
        except Exception:
            logger.warning("local_embedder init failed", exc_info=True)
            pass

        try:
            subsystems.code_index = CodeSemanticIndex(workdir=workdir)
        except Exception:
            logger.warning("code_index init failed", exc_info=True)
            pass

        try:
            subsystems.project_rag = ProjectRAG(workdir=workdir)
        except Exception:
            logger.warning("project_rag init failed", exc_info=True)
            pass

        try:
            subsystems.docker_sandbox = DockerSandbox(workdir=workdir)
        except Exception:
            logger.warning("docker_sandbox init failed", exc_info=True)
            pass

        try:
            subsystems.model_router = ModelRouter(complex_client=None)
        except Exception:
            logger.warning("model_router init failed", exc_info=True)
            pass

        try:
            subsystems.dynamic_workflow = DynamicWorkflowEngine(
                agent_factory=agent_factory
            )
        except Exception:
            logger.warning("dynamic_workflow init failed", exc_info=True)
            pass

        try:
            subsystems.memory_sync = MemorySync()
        except Exception:
            logger.warning("memory_sync init failed", exc_info=True)
            pass

        # Agent-of-agents (needs agent_factory + fresh minimal Agent per task)
        if agent_factory:
            def _make_minimal_agent():
                from .agent import Agent
                return Agent(
                    config=None, workdir=workdir,
                    enable_subagents=False, enable_skills=False,
                    enable_memory=False, enable_session=False,
                    enable_metrics=False, enable_cache=False,
                    enable_checkpoint=False, enable_planner=False,
                )
            try:
                subsystems.autonomous_agent = AutonomousAgent(
                    agent_factory=_make_minimal_agent, workdir=workdir
                )
            except Exception:
                logger.warning("autonomous_agent init failed", exc_info=True)
                pass
            try:
                subsystems.skill_auto_creator = SkillAutoCreator()
            except Exception:
                logger.warning("skill_auto_creator init failed", exc_info=True)
                pass

        return subsystems
