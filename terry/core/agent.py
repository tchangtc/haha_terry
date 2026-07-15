"""Core agent loop - production-grade implementation with full feature set."""

from __future__ import annotations

import copy
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..hooks import hook_registry
from ..hooks.logging_hook import log_hook
from ..hooks.permission import SandboxMode, permission_hook
from ..tools import discover_tools, tool_registry
from . import agent_hooks
from .cache import LLMCache, ToolCache
from .checkpoint import CheckpointManager, get_checkpoint_manager
from .commands import CommandRegistry
from .config import TerryConfig
from .context_compact import ContextCompactor
from .error_recovery import (
    AutoHealer,
    ErrorRecovery,
    wrap_llm_call_with_recovery,
)
from .harness import HarnessEngine
from .llm import LLMClient
from .logger import get_logger
from .memory import Memory, get_memory
from .metrics import Metrics, estimate_cost, get_metrics
from .permissions import PermissionLevel, PermissionStore, get_permission_store
from .planner import Planner
from .platform_utils import get_terry_dir
from .security import RequestValidator
from .session import Session, get_session
from .skill import SkillExecutor, SkillManager, get_skill_manager
from .response_handler import ResponseHandler
from .store import TerryStore
from .subagent import SubAgentManager
from .telemetry import Telemetry
from .text_utils import extract_text
from .tool_executor import ToolExecutor


def _format_tool_detail(name: str, inp: dict) -> str:
    """Build a concise, human-readable description of a tool call.

    Examples:
        bash ls -la /tmp
        read_file src/main.py
        grep "def run" terry/core/
        write_file terry/core/new.py
    """
    if name == "bash":
        cmd = str(inp.get("command", ""))
        # Truncate long commands
        return f"$ {cmd}" if len(cmd) <= 60 else f"$ {cmd[:57]}..."
    if name in ("read_file", "write_file", "edit_file"):
        path = str(inp.get("file_path", inp.get("path", "")))
        return f"{name} {path}" if len(path) <= 50 else f"{name} ...{path[-47:]}"
    if name == "grep":
        pattern = str(inp.get("pattern", ""))
        path = str(inp.get("path", "."))
        return f'grep "{pattern}" {path}' if len(pattern) <= 30 else f'grep "{pattern[:27]}..." {path}'
    if name in ("glob", "find_tool", "ls_tool", "ls"):
        path = str(inp.get("path", inp.get("directory", ".")))
        return f"{name} {path}"
    if name == "web_search":
        query = str(inp.get("query", ""))
        return f"web_search {query}" if len(query) <= 40 else f"web_search {query[:37]}..."
    if name == "web_fetch":
        url = str(inp.get("url", ""))
        return f"web_fetch {url}" if len(url) <= 50 else f"web_fetch {url[:47]}..."
    if name == "todo_write":
        return "update task list"
    if name == "notebook":
        return "edit notebook"
    # Generic fallback
    return f"{name}"


class Agent:
    """Production-grade agent with memory, sessions, metrics, and caching."""

    def __init__(
        self,
        config: TerryConfig,
        workdir: Path | None = None,
        enable_memory: bool = True,
        enable_session: bool = True,
        enable_metrics: bool = True,
        enable_cache: bool = True,
        enable_subagents: bool = True,
        enable_skills: bool = True,
        enable_checkpoint: bool = True,
        enable_planner: bool = True,
        log_level: str = "INFO",
    ):
        """Initialize production-grade agent.

        Args:
            config: Agent configuration
            workdir: Working directory
            enable_memory: Enable persistent memory
            enable_session: Enable session management
            enable_metrics: Enable metrics collection
            enable_cache: Enable response caching
            enable_subagents: Enable subagent spawning
            enable_skills: Enable skill system
            log_level: Logging level
        """
        self.config = config
        self.workdir = workdir or Path.cwd()

        # Initialize logger
        self.logger = get_logger(level=getattr(__import__("logging"), log_level))

        self.logger.info("Initializing agent", workdir=str(self.workdir))

        # Initialize LLM client
        self.llm = LLMClient(config.model)

        # Discover and register tools
        discover_tools()

        # Register task_update tool (needs agent reference for TaskManager access)
        from ..tools.task_update import register as register_task_update
        register_task_update(agent=self)
        from ..tools.slash_command import register as register_slash_command
        register_slash_command(agent=self)

        self.tools = tool_registry
        self.logger.info(f"Registered {len(self.tools.list_tools())} tools")

        # Initialize hooks (permission_hook uses config's sandbox_mode + permission level)
        self._mode: SandboxMode = SandboxMode(self.config.sandbox_mode)
        hook_registry.register("PreToolUse", log_hook)
        hook_registry.register(
            "PreToolUse",
            lambda block: permission_hook(
                block, self.workdir, self._mode,
                permission_store=self.permission_store,
                permission_level=self.permission_level,
            ),
        )
        self.hooks = hook_registry

        # Initialize context management
        self.compactor = ContextCompactor(
            config=config,
            max_tokens=config.max_input_tokens,
            compression_threshold=config.compression_threshold,
        )

        # Initialize error recovery (cross-provider fallback on overload)
        self.error_recovery = ErrorRecovery(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
            user_fallbacks=config.model.fallback_models or None,
        )

        # Initialize auto-healer
        self.auto_healer = AutoHealer(workdir=self.workdir, max_attempts=config.auto_healer_max_attempts)
        self.logger.info("AutoHealer enabled")

        # Initialize optional features
        self.memory: Memory | None = None
        if enable_memory:
            self.memory = get_memory()
            self.logger.info("Memory system enabled")

        self.session: Session | None = None
        if enable_session:
            self.session = get_session()
            self.session.new()
            self.logger.info("Session management enabled", session_id=self.session.session_id)

        self.metrics: Metrics | None = None
        if enable_metrics:
            self.metrics = get_metrics()
            self.logger.info("Metrics collection enabled")

        self.llm_cache: LLMCache | None = None
        self.tool_cache: ToolCache | None = None
        if enable_cache:
            from .cache import Cache as _Cache
            from .cache import set_cache as _set_cache
            from .cache import set_llm_cache as _set_llm_cache
            from .cache import set_tool_cache as _set_tool_cache
            _cache_instance = _Cache(config=config)
            _set_cache(_cache_instance)
            _llm_cache_instance = LLMCache(cache=_cache_instance, config=config)
            _set_llm_cache(_llm_cache_instance)
            _tool_cache_instance = ToolCache(cache=_cache_instance, config=config)
            _set_tool_cache(_tool_cache_instance)
            self.llm_cache = _llm_cache_instance
            self.tool_cache = _tool_cache_instance
            self.logger.info("Caching enabled")

        self.subagent_manager: SubAgentManager | None = None
        if enable_subagents:
            self.subagent_manager = SubAgentManager(config, self.workdir, self.tools)
            self.logger.info("Subagent system enabled")

        # Initialize permission store
        self.permission_store: PermissionStore = get_permission_store()
        self.permission_level: PermissionLevel = PermissionLevel.from_sandbox_mode(
            config.sandbox_mode
        )
        self.logger.info(f"Permission system enabled (level: {self.permission_level.value})")

        # Initialize checkpoint manager
        self.checkpoint_manager: CheckpointManager | None = None
        if enable_checkpoint:
            self.checkpoint_manager = get_checkpoint_manager(
                workdir=self.workdir,
            )
            self.logger.info(
                f"Checkpoint system enabled "
                f"({len(self.checkpoint_manager.list_checkpoints())} existing)"
            )

        # Initialize planner
        self.planner: Planner | None = None
        self.plan: dict | None = None  # Active execution plan
        if enable_planner:
            self.planner = Planner(llm_client=self.llm)
            self.logger.info("Planner enabled")

        # ── Advanced subsystems (delegated to AgentSubsystems) ──
        from .agent_subsystems import AgentSubsystems
        self.subsystems = AgentSubsystems.create(
            workdir=self.workdir, model=config.model.model, agent_factory=lambda: self
        )
        # Flatten hot-path refs for backward compatibility
        self.extended_thinking = self.subsystems.extended_thinking
        self.task_dag = self.subsystems.task_dag
        self.knowledge_graph = self.subsystems.knowledge_graph
        self.scheduler = self.subsystems.scheduler
        self.skills_curator = self.subsystems.skills_curator
        self.workflow_engine = self.subsystems.workflow_engine
        self.prompt_cache = self.subsystems.prompt_cache
        self.spec_exec = self.subsystems.spec_exec
        self.suggester = self.subsystems.suggester
        self.fts_search = self.subsystems.fts_search
        self.skill_market = self.subsystems.skill_market
        self.local_embedder = self.subsystems.local_embedder
        self.code_index = self.subsystems.code_index
        self.project_rag = self.subsystems.project_rag
        self.docker_sandbox = self.subsystems.docker_sandbox
        self.model_router = self.subsystems.model_router
        self.dynamic_workflow = self.subsystems.dynamic_workflow
        self.memory_sync = self.subsystems.memory_sync
        self.autonomous_agent = self.subsystems.autonomous_agent
        self.skill_auto_creator = self.subsystems.skill_auto_creator
        if self.skill_auto_creator is not None:
            self.skill_auto_creator.llm_client = self.llm
        self.logger.info("Advanced subsystems initialized via AgentSubsystems")

        # Unified task manager — bridges Planner + TodoWrite + TaskDAG
        from .task_manager import TaskManager
        self.task_manager = TaskManager()
        self.task_manager.load()  # Restore from disk if available

        # Feedback + Store + Telemetry (small, keep inline)
        from .feedback import FeedbackCollector
        from .feedback import set_feedback_collector as _set_fc
        _fc_instance = FeedbackCollector(config=config)
        _set_fc(_fc_instance)
        self.feedback = _fc_instance
        self.store = TerryStore()
        self.telemetry = Telemetry()

        # Command registry
        self.commands = CommandRegistry()

        # Harness engine — unified orchestration layer
        self.harness = HarnessEngine(
            agent_factory=lambda: Agent(
                config=self.config, workdir=self.workdir,
                enable_subagents=False, enable_skills=False,
                enable_memory=False, enable_session=False,
                enable_metrics=True, enable_cache=False,
                enable_checkpoint=False, enable_planner=False,
            ),
        )
        self.logger.info("Harness engine initialized")

        # Bind the harness tool to this factory-backed engine so the 8
        # orchestration patterns can spawn real sub-agents from the LLM.
        from ..tools.harness_tool import register as register_harness_tool
        register_harness_tool(agent=self)

        # Initialize skill system
        self.skill_manager: SkillManager | None = None
        self.skill_executor: SkillExecutor | None = None
        self.active_skill: str | None = None
        if enable_skills:
            skills_dirs = [
                self.workdir / "skills",
                get_terry_dir("skills"),
            ]
            self.skill_manager = get_skill_manager(skills_dirs)
            self.skill_executor = SkillExecutor(self.skill_manager, self)
            skill_count = len(self.skill_manager.list_skills())
            self.logger.info(f"Skill system enabled ({skill_count} skills loaded)")

        # ── Extracted subsystems (composition over inheritance) ──
        self._tool_executor = ToolExecutor(
            config=self.config,
            tools=self.tools,
            hooks=self.hooks,
            tool_cache=self.tool_cache,
            checkpoint_manager=self.checkpoint_manager,
            spec_exec=self.spec_exec,
            metrics=self.metrics,
            auto_healer=self.auto_healer,
            session=self.session,
            workdir=self.workdir,
        )
        self._response_handler = ResponseHandler(
            hooks=self.hooks,
            session=self.session,
            metrics=self.metrics,
            parent_logger=self.logger,
        )

        # Conversation history
        self.messages: list[dict[str, Any]] = []
        self.tool_call_count = 0

        # Performance tracking
        self.session_start_time = time.time()


    def set_effort(self, level: str) -> bool:
        valid = ("low", "medium", "high", "xhigh")
        if level not in valid:
            self.logger.warning("Invalid effort level", value=level)
            return False
        self.config.effort_level = level
        from .config import EFFORT_CONFIG
        ec = EFFORT_CONFIG.get(level, {})
        if ec.get("model"):
            self.config.model.model = ec["model"]
        if ec.get("max_tokens"):
            self.config.model.max_tokens = ec["max_tokens"]
        try:
            self.llm.reconfigure(self.config.model)
        except Exception:
            self.logger.warning("LLM reconfigure failed")
        self.logger.info("Effort level changed", level=level)
        return True

    def get_mode(self) -> str:
        """Get current sandbox mode."""
        return self._mode.value

    def set_mode(self, new_mode: str) -> bool:
        """Set sandbox mode. Returns True on success."""
        try:
            self._mode = SandboxMode(new_mode)
            self.logger.info(f"Sandbox mode changed to {self._mode.value}")
            return True
        except ValueError:
            self.logger.warning(f"Invalid sandbox mode: {new_mode}")
            return False

    def cycle_mode(self) -> str:
        """Cycle to the next sandbox mode (Shift+Tab handler)."""
        self._mode = SandboxMode.cycle(self._mode)
        self.logger.info(f"Sandbox mode cycled to {self._mode.value}")
        return self._mode.value

    def build_system_prompt(self) -> str:
        """Build comprehensive system prompt with context."""
        from .agent_prompts import build_system_prompt
        prompt = build_system_prompt(
            workdir=str(self.workdir),
            tools=self.tools.list_tools(),
            active_skill=self.active_skill,
            skill_manager=self.skill_manager,
            memory=self.memory,
            session=self.session,
        )
        # Inject active task plan if present
        if self.task_manager and self.task_manager.is_active():
            task_context = self.task_manager.to_tool_format()
            if task_context:
                prompt += "\n\n" + task_context

        # Re-inject compacted session context from Memory
        if self.memory:
            try:
                compacts = self.memory.get_by_type("session_compact")[:3]
                if compacts:
                    ctx = "\n".join(m.get("content", "")[:500] for m in compacts[:3])
                    if ctx.strip():
                        prompt += "\n\n## Recent Context (recovered from compaction)\n" + ctx
            except Exception:
                pass

        return prompt

    def run(self, user_message: str, use_cache: bool = True,
            on_progress: Callable[[str, dict], None] | None = None) -> str:
        """Run the agent loop with full feature integration.

        Args:
            user_message: User's input message
            use_cache: Whether to use caching
            on_progress: Optional callback for real-time progress updates.
                Called with (event_name, data_dict) where event_name is one of:
                "llm_call", "llm_done", "tool_executed", "done".

        Returns:
            Agent's response
        """
        # Validate prompt input
        is_valid, error_msg = RequestValidator.validate_prompt(user_message)
        if not is_valid:
            return f"Error: {error_msg}"

        start_time = time.time()
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        llm_calls = 0

        # Helper to build progress data snapshot
        def _progress(event: str, **extra) -> None:
            if on_progress is None:
                return
            on_progress(event, {
                "elapsed": time.time() - start_time,
                "tool_calls": self.tool_call_count,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost": total_cost,
                "llm_calls": llm_calls,
                **extra,
            })

        # Log user message
        self.logger.info("User message", length=len(user_message))

        # Pre-process: FTS index, @mention, skill matching (agent_hooks)
        enriched_message = agent_hooks.pre_process(self, user_message)

        # Add to session
        if self.session:
            self.session.add_message("user", enriched_message)

        # Add to conversation history
        self.messages.append({"role": "user", "content": enriched_message})

        # Trigger hooks
        self.hooks.trigger("UserPromptSubmit", user_message)

        # Build system prompt and tools
        system = self.build_system_prompt()
        tools_def = self.tools.get_definitions()

        # Track metrics
        if self.metrics:
            self.metrics.increment("user_messages")

        # Agent loop
        iteration = 0
        while True:
            iteration += 1
            # Check tool call budget
            if self.tool_call_count >= self.config.max_tool_calls:
                self.logger.warning("Tool call budget exceeded", count=self.tool_call_count)
                _progress("done")
                return self._wrap_up()

            # Check if context needs compaction
            if self.compactor.needs_compaction(self.messages):
                self.logger.info("Compacting context", message_count=len(self.messages))
                if self.metrics:
                    self.metrics.increment("context_compactions")
                self.messages = self.compactor.compact(
                    self.messages, self.llm, memory=self.memory,
                    on_warning=lambda msg: _progress("compaction", message=msg) if on_progress else None,
                )

            # LLM call — clear tool context so display shows "thinking" phase
            _progress("llm_call", iteration=iteration, tool_name="", tool_detail="")
            response = self._get_llm_response(system, tools_def, use_cache)
            if not response:
                _progress("done")
                return "Error: Failed to get LLM response"

            llm_calls += 1
            self.messages.append({"role": "assistant", "content": response["content"]})
            self._track_llm_metrics(response)

            # Update accumulated counters for progress display
            usage = response.get("usage", {})
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)
            total_cost += estimate_cost(
                self.config.model.model,
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0),
            )

            # Check if we're done (no tool calls)
            if response["stop_reason"] != "tool_use":
                _progress("almost_done", iteration=iteration)
                result = self._handle_final_response(user_message, response, start_time)
                _progress("done")
                # ── Skill auto-creation: learn from complex tasks ──
                if self.skill_auto_creator is not None:
                    try:
                        self.skill_auto_creator.maybe_create(
                            user_message=user_message,
                            messages=self.messages,
                            tool_call_count=self.tool_call_count,
                            agent_response=result,
                        )
                    except Exception:
                        pass  # Non-critical error
                        self.logger.debug(
                            "Skill auto-creation skipped", exc_info=True
                        )
                return result

            # Extract tool details for progress display
            tool_details = self._extract_tool_details(response["content"])
            for td in tool_details:
                _progress("tool_executed", tool_name=td["name"], tool_detail=td["detail"])

            # Execute tool calls
            results = self._execute_tools(response["content"])

            # Auto-advance task plan if task_manager is active
            if self.task_manager and self.task_manager.is_active():
                current_task = self.task_manager.get_next_ready()
                if current_task:
                    # Mark as in_progress on first tool call
                    if current_task.status == "pending":
                        self.task_manager.mark(current_task.id, "in_progress")

            # Add tool results to history
            self.messages.append({"role": "user", "content": results})

            # Save session periodically
            if self.session and len(self.messages) % 10 == 0:
                self.session.save()

    def _get_llm_response(
        self, system: str, tools_def: list, use_cache: bool = True
    ) -> dict | None:
        """Get LLM response with caching support."""
        if use_cache and self.llm_cache:
            cached = self.llm_cache.get_response(
                self.messages, system=system, tools=tools_def, model=self.config.model.model
            )
            if cached:
                self.logger.info("Cache hit for LLM response")
                if self.metrics:
                    self.metrics.increment("llm_cache_hits")
                return cached

        response = self._call_llm(system, tools_def)
        if response and use_cache and self.llm_cache:
            self.llm_cache.set_response(
                self.messages, response, system=system, tools=tools_def, model=self.config.model.model
            )
        return response

    def _track_llm_metrics(self, response: dict) -> None:
        """Track token usage and cost from LLM response."""
        if not self.metrics or "usage" not in response:
            return
        usage = response["usage"]
        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)
        self.metrics.increment("input_tokens", inp)
        self.metrics.increment("output_tokens", out)
        self.metrics.increment("llm_calls")
        cost = estimate_cost(self.config.model.model, inp, out)
        self.metrics.add_cost(self.config.model.provider, cost)

    def _call_llm(
        self,
        system: str,
        tools_def: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Call LLM with error recovery.

        Args:
            system: System prompt
            tools_def: Tool definitions

        Returns:
            LLM response or None on error
        """
        switched = {"active": False}

        def _on_fallback(prov: str, mdl: str) -> None:
            """Switch the live client to a fallback provider/model on overload."""
            from dataclasses import replace

            # Set the flag first so a mid-reconfigure failure still triggers the
            # `finally` restore instead of leaking the half-applied fallback.
            switched["active"] = True
            if prov == self.config.model.provider:
                # Same provider: keep the user's base_url/api_key (proxy/gateway,
                # programmatic key) — only the model changes.
                fb_config = replace(self.config.model, model=mdl)
            else:
                # Cross-provider: clear so resolve() re-derives base_url/key for `prov`.
                fb_config = replace(
                    self.config.model, provider=prov, model=mdl, api_key=None, base_url=None
                )
                fb_config.resolve()
            self.llm.reconfigure(fb_config)
            self.logger.warning("LLM fallback active", provider=prov, model=mdl)

        try:
            wrapped_call = wrap_llm_call_with_recovery(
                self.llm.chat,
                self.error_recovery,
                self.compactor,
                provider=self.config.model.provider,
                model=self.config.model.model,
                on_fallback=_on_fallback,
            )
            return wrapped_call(
                messages=self.messages,
                system=system,
                tools=tools_def,
                max_tokens=self.config.model.max_tokens,
            )
        except Exception as e:
            self.logger.error("LLM call failed", error=str(e), exc_info=True)
            if self.metrics:
                self.metrics.increment("llm_errors")
            return None
        finally:
            # Restore the primary model so the next turn retries it — a transient
            # 529 must not permanently pin the session to a fallback model.
            if switched["active"]:
                self.llm.reconfigure(self.config.model)

    def _handle_final_response(self, user_message: str, response: Any, start_time: float) -> str:
        """Handle the final assistant response — delegates to ResponseHandler."""
        return self._response_handler.handle_final_response(
            agent=self,
            user_message=user_message,
            response=response,
            start_time=start_time,
            messages=self.messages,
        )

    def _execute_tools(self, content: Any) -> list[dict[str, Any]]:
        """Execute tool calls — delegates to ToolExecutor (extracted module)."""
        results, count = self._tool_executor.execute_tools(content)
        self.tool_call_count += count
        return results

    def _extract_tool_details(self, content: Any) -> list[dict[str, str]]:
        """Extract tool calls with human-readable detail for progress display.

        Returns list of {name, detail} where detail is e.g. "bash ls -la" or
        "read_file src/main.py".
        """
        details = []
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                name, inp = "", {}
                if block.get("type") == "tool_use":
                    name = block.get("name", "unknown")
                    inp = block.get("input", {})
                elif block.get("type") == "tool_calls":
                    for tc in block.get("tool_calls", []):
                        if isinstance(tc, dict):
                            name = tc.get("function", {}).get("name", "unknown")
                            try:
                                import json
                                inp = json.loads(tc.get("function", {}).get("arguments", "{}"))
                            except Exception:
                                pass  # Non-critical error
                                inp = {}
                if not name:
                    continue
                # Build human-readable detail based on tool type
                detail = _format_tool_detail(name, inp)
                details.append({"name": name, "detail": detail})
        return details or [{"name": "unknown", "detail": "processing"}]

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a single tool — delegates to ToolExecutor (extracted module)."""
        return self._tool_executor._execute_one(tool_name, tool_input)

    def _wrap_up(self) -> str:
        """Force the agent to stop using tools and provide a final response.

        Returns:
            Final response text
        """
        wrap_message = {
            "role": "user",
            "content": "You've reached the maximum number of tool calls. "
                      "Please provide a final summary without using any more tools.",
        }
        self.messages.append(wrap_message)

        try:
            response = self.llm.chat(
                messages=self.messages,
                system=self.build_system_prompt(),
                tools=None,
                max_tokens=self.config.model.max_tokens,
            )
            return extract_text(response["content"])
        except Exception as e:
            self.logger.error("Wrap-up failed", error=str(e), exc_info=True)
            return f"Error in wrap-up: {e}"

    def _extract_text(self, content: Any) -> str:
        """Extract text from response content (delegates to shared utility).

        Args:
            content: Response content

        Returns:
            Extracted text
        """
        return extract_text(content)

    def _track_knowledge(self, user_msg: str, assistant_msg: str) -> None:
        """Extract entities from conversation and add to knowledge graph."""
        if not self.knowledge_graph:
            return

        # Simple entity extraction: file paths, function names, error types

        # File paths
        files = set(re.findall(r"['\"]?([\w./-]+\.(?:py|js|ts|md|yaml|json))['\"]?", user_msg + " " + assistant_msg))
        for f in files:
            self.knowledge_graph.add_node(f"file:{f}", "file", name=f)

        # Error types
        errors = set(re.findall(r"(?:Error|Exception):\s*(\w+)", assistant_msg))
        for e in errors:
            self.knowledge_graph.add_node(f"error:{e}", "error", name=e)
            for f in files:
                self.knowledge_graph.add_edge(f"file:{f}", f"error:{e}", "had_error")

    def fork(self) -> Agent:
        """Fork the agent state, creating a new conversation branch.

        The current agent's messages are cloned into the fork.
        Returns the forked agent for chaining.
        """
        forked = Agent(
            config=self.config,
            workdir=self.workdir,
            enable_memory=False,
            enable_session=False,
            enable_metrics=False,
            enable_cache=False,
            enable_subagents=False,
            enable_skills=False,
            enable_checkpoint=False,
            enable_planner=False,
        )
        # Clone current messages
        forked.messages = copy.deepcopy(self.messages)
        self.logger.info("Agent forked", message_count=len(forked.messages))
        return forked

    def parse_mentions(self, text: str) -> str:
        """Parse @-mention syntax and inject relevant context.

        Supports:
          @file:path/to/file.py  — inject file contents (first 100 lines)
          @symbol:ClassName      — search repo map for class/function definition
          @git:branch-name       — show git log for branch

        Returns the input text with injected context appended.
        """

        mentions = re.findall(r"@(file|symbol|git):(\S+)", text)
        if not mentions:
            return text

        context_parts = ["\n\n---\n## Injected Context\n"]

        for mtype, mvalue in mentions:
            if mtype == "file":
                file_path = self.workdir / mvalue
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        preview = "\n".join(content.split("\n")[:100])
                        context_parts.append(
                            f"\n### @file:{mvalue}\n```\n{preview}\n```\n"
                        )
                    except Exception:
                        pass  # Non-critical error
                        context_parts.append(f"\n*(Could not read @file:{mvalue})*\n")

            elif mtype == "symbol":
                try:
                    from .repomap import RepoMapGenerator
                    gen = RepoMapGenerator(self.workdir)
                    symbols = gen.find_symbol(mvalue)
                    if symbols:
                        context_parts.append(f"\n### @symbol:{mvalue}\n")
                        for s in symbols[:5]:
                            context_parts.append(
                                f"- `{s['type']}` **{s['name']}** → "
                                f"`{s['file']}:{s['line']}`\n"
                            )
                            if s.get("signature"):
                                context_parts.append(f"  ```{s['signature']}```\n")
                except Exception:
                    pass  # Non-critical error
                    context_parts.append(f"\n*(Could not resolve @symbol:{mvalue})*\n")

            elif mtype == "git":
                try:
                    result = subprocess.run(
                        ["git", "log", "--oneline", "-n", "5", mvalue],
                        cwd=self.workdir,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.stdout:
                        context_parts.append(
                            f"\n### @git:{mvalue}\n```\n{result.stdout.strip()}\n```\n"
                        )
                except Exception:
                    pass  # Non-critical error
                    pass

        if len(context_parts) > 1:
            return text + "\n".join(context_parts)
        return text

    def reset(self) -> None:
        """Reset the agent state."""
        self.messages = []
        self.tool_call_count = 0

        if self.session:
            self.session.new()

        self.logger.info("Agent reset")

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive agent status.

        Returns:
            Status dictionary
        """
        status = {
            "workdir": str(self.workdir),
            "message_count": len(self.messages),
            "tool_call_count": self.tool_call_count,
            "tool_call_budget": self.config.max_tool_calls,
            "tools_available": len(self.tools.list_tools()),
        }

        if self.session:
            status["session_id"] = self.session.session_id

        if self.memory:
            status["memory_count"] = len(self.memory.list_memories())

        if self.metrics:
            status["metrics"] = self.metrics.get_summary()

        if self.llm_cache:
            status["cache_stats"] = self.llm_cache.cache.get_stats()

        return status

    def save_session(self, filename: str | None = None) -> Path | None:
        """Save current session to disk.

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved file or None
        """
        if self.session:
            return self.session.save(filename)
        return None

    def load_session(self, session_id: str) -> bool:
        """Load a session from disk.

        Args:
            session_id: Session ID to load

        Returns:
            True if loaded successfully
        """
        if self.session:
            if self.session.load(session_id):
                self.messages = self.session.get_messages()
                self.logger.info("Session loaded", session_id=session_id)
                return True
        return False

    def get_metrics_summary(self) -> dict[str, Any] | None:
        """Get metrics summary.

        Returns:
            Metrics summary or None
        """
        if self.metrics:
            return self.metrics.get_summary()
        return None

    def reconfigure(self, new_config: Any, changed_fields: list[str]) -> list[str]:
        """Push config changes to subsystems that support hot-reconfigure.

        Some subsystems can accept config changes at runtime (model settings,
        compression thresholds, sandbox mode). Others require a restart
        (SubAgentManager, cache, RAG) — these produce warnings.

        Args:
            new_config: The reloaded TerryConfig with updated values.
            changed_fields: List of field names that changed (from TerryConfig.reload).

        Returns:
            List of field names that were successfully applied.
        """
        applied: list[str] = []
        for field in changed_fields:
            if field.startswith("model."):
                try:
                    self.llm.reconfigure(new_config.model)
                    applied.append(field)
                except Exception:
                    pass  # Non-critical error
                    self.logger.warning("Failed to reconfigure LLM", field=field)
            elif field in ("compression_threshold", "max_input_tokens"):
                try:
                    threshold = new_config.compression_threshold if field == "compression_threshold" else None
                    max_tok = new_config.max_input_tokens if field == "max_input_tokens" else None
                    if self.compactor:
                        self.compactor.reconfigure(threshold=threshold, max_tokens=max_tok)
                    applied.append(field)
                except Exception:
                    pass  # Non-critical error
                    self.logger.warning("Failed to reconfigure compactor", field=field)
            elif field == "sandbox_mode":
                self.set_mode(new_config.sandbox_mode)
                applied.append(field)
            elif field == "auto_healer_max_attempts":
                from .error_recovery import AutoHealer
                self.auto_healer = AutoHealer(workdir=self.workdir, max_attempts=new_config.auto_healer_max_attempts)
                applied.append(field)
            elif field in ("llm_timeout",):
                applied.append(field)
            else:
                self.logger.info("Config change requires restart: %s", field)

        self.config = new_config
        return applied

    def run_goal(self, goal: str) -> dict:
        """Execute a goal-driven autonomous loop that iterates until the goal is met.

        Uses a dual-model architecture: the main agent generates/refines,
        a configurable evaluator model scores progress. The loop continues
        until the quality threshold is reached or max iterations (10) expire.

        Args:
            goal: Natural language description of the goal.
                  Examples: "all tests pass", "implement login module".

        Returns:
            GoalResult dict with keys: met, iterations, final_score, feedback,
            final_output, history.
        """
        from .goal_loop import GoalLoop
        from .llm import LLMClient
        from .config import ModelConfig

        evaluator = None
        if self.config.evaluator_model:
            eval_config = ModelConfig(
                provider=self.config.model.provider,
                model=self.config.evaluator_model,
                api_key=self.config.model.api_key,
                base_url=self.config.model.base_url,
            )
            eval_config.resolve()
            evaluator = LLMClient(eval_config)

        loop = GoalLoop(
            agent=self,
            evaluator_model=evaluator,
            max_iterations=GoalLoop.DEFAULT_MAX_ITERATIONS,
            quality_threshold=GoalLoop.DEFAULT_QUALITY_THRESHOLD,
        )
        result = loop.run(goal)
        return result.to_dict()

    def clear_cache(self) -> int:
        """Clear all caches.

        Returns:
            Number of entries cleared
        """
        count = 0
        if self.llm_cache:
            count += self.llm_cache.cache.clear()
        if self.tool_cache:
            count += self.tool_cache.cache.clear()

        self.logger.info("Cache cleared", entries=count)
        return count

    # Skill management methods

    def list_skills(self) -> list[dict[str, str]]:
        """List all available skills.

        Returns:
            List of skill information dictionaries
        """
        if not self.skill_manager:
            return []

        skills = self.skill_manager.list_skills()
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "active": skill.name == self.active_skill,
            }
            for skill in skills
        ]

    def get_skill_info(self, skill_name: str) -> dict[str, Any] | None:
        """Get detailed information about a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill information dictionary or None if not found
        """
        if not self.skill_manager:
            return None

        skill = self.skill_manager.get_skill(skill_name)
        if not skill:
            return None

        return {
            "name": skill.name,
            "description": skill.description,
            "content": skill.content,
            "metadata": skill.metadata,
            "active": skill.name == self.active_skill,
        }

    def activate_skill(self, skill_name: str) -> bool:
        """Manually activate a skill.

        Args:
            skill_name: Name of the skill to activate

        Returns:
            True if activated successfully
        """
        if not self.skill_manager:
            self.logger.warning("Skill system not enabled")
            return False

        skill = self.skill_manager.get_skill(skill_name)
        if not skill:
            self.logger.warning(f"Skill not found: {skill_name}")
            return False

        self.active_skill = skill.name
        self.logger.info(f"Skill activated: {skill.name}")
        return True

    def deactivate_skill(self) -> None:
        """Deactivate the current skill."""
        if self.active_skill:
            self.logger.info(f"Skill deactivated: {self.active_skill}")
            self.active_skill = None

    def reload_skills(self) -> int:
        """Reload all skills from disk.

        Returns:
            Number of skills loaded
        """
        if not self.skill_manager:
            return 0

        self.skill_manager.reload_skills()
        skill_count = len(self.skill_manager.list_skills())
        self.logger.info(f"Skills reloaded ({skill_count} skills)")
        return skill_count

