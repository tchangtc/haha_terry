"""Core agent loop - production-grade implementation with full feature set."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..hooks import hook_registry
from ..hooks.logging_hook import log_hook
from ..hooks.permission import SandboxMode, permission_hook
from ..tools import discover_tools, tool_registry
from . import agent_hooks
from .autonomous_agent import AutonomousAgent, SkillAutoCreator
from .cache import LLMCache, ToolCache, get_llm_cache, get_tool_cache
from .checkpoint import CheckpointManager, get_checkpoint_manager
from .code_index import CodeSemanticIndex
from .commands import CommandRegistry
from .config import TerryConfig
from .context_compact import ContextCompactor
from .curator import SkillsCurator
from .docker_sandbox import DockerSandbox
from .dynamic_workflow import DynamicWorkflowEngine
from .error_recovery import (
    AutoHealer,
    ErrorRecovery,
    auto_commit_after_edit,
    wrap_llm_call_with_recovery,
)
from .feedback import get_feedback_collector
from .fts_search import FTSSearch
from .harness import HarnessEngine
from .knowledge_graph import KnowledgeGraph
from .llm import LLMClient
from .local_embed import LocalEmbedder
from .logger import get_logger
from .memory import Memory, get_memory
from .memory_sync import MemorySync
from .metrics import Metrics, estimate_cost, get_metrics
from .model_router import ModelRouter
from .permissions import PermissionLevel, PermissionStore, get_permission_store
from .planner import Planner
from .prompt_cache import PromptCache
from .rag import ProjectRAG
from .scheduler import CronScheduler
from .security import RequestValidator
from .session import Session, get_session
from .skill import SkillExecutor, SkillManager, get_skill_manager
from .skill_market import SkillMarket
from .spec_exec import SpeculativeExecutor
from .store import TerryStore
from .subagent import SubAgentManager
from .suggester import ProactiveSuggester
from .task_dag import TaskDAG
from .telemetry import Telemetry
from .text_utils import extract_text
from .thinking import ExtendedThinking
from .workflow import WorkflowEngine


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
            max_tokens=config.max_input_tokens,
            compression_threshold=config.compression_threshold,
        )

        # Initialize error recovery
        self.error_recovery = ErrorRecovery(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
        )

        # Initialize auto-healer
        self.auto_healer = AutoHealer(workdir=self.workdir, max_attempts=2)
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
            self.llm_cache = get_llm_cache()
            self.tool_cache = get_tool_cache()
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
        self.logger.info("Advanced subsystems initialized via AgentSubsystems")

        # Feedback + Store + Telemetry (small, keep inline)
        self.feedback = get_feedback_collector()
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

        # Initialize skill system
        self.skill_manager: SkillManager | None = None
        self.skill_executor: SkillExecutor | None = None
        self.active_skill: str | None = None
        if enable_skills:
            skills_dirs = [
                self.workdir / "skills",
                Path.home() / ".terry" / "skills",
            ]
            self.skill_manager = get_skill_manager(skills_dirs)
            self.skill_executor = SkillExecutor(self.skill_manager, self)
            skill_count = len(self.skill_manager.list_skills())
            self.logger.info(f"Skill system enabled ({skill_count} skills loaded)")

        # Conversation history
        self.messages: list[dict[str, Any]] = []
        self.tool_call_count = 0

        # Performance tracking
        self.session_start_time = time.time()

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
        return build_system_prompt(
            workdir=str(self.workdir),
            tools=self.tools.list_tools(),
            active_skill=self.active_skill,
            skill_manager=self.skill_manager,
            memory=self.memory,
            session=self.session,
        )

    def run(self, user_message: str, use_cache: bool = True) -> str:
        """Run the agent loop with full feature integration.

        Args:
            user_message: User's input message
            use_cache: Whether to use caching

        Returns:
            Agent's response
        """
        # Validate prompt input
        is_valid, error_msg = RequestValidator.validate_prompt(user_message)
        if not is_valid:
            return f"Error: {error_msg}"

        start_time = time.time()

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
        while True:
            # Check tool call budget
            if self.tool_call_count >= self.config.max_tool_calls:
                self.logger.warning("Tool call budget exceeded", count=self.tool_call_count)
                return self._wrap_up()

            # Check if context needs compaction
            if self.compactor.needs_compaction(self.messages):
                self.logger.info("Compacting context", message_count=len(self.messages))
                if self.metrics:
                    self.metrics.increment("context_compactions")
                self.messages = self.compactor.compact(self.messages, self.llm)

            # LLM call with caching and metrics (extracted)
            response = self._get_llm_response(system, tools_def, use_cache)
            if not response:
                return "Error: Failed to get LLM response"

            self.messages.append({"role": "assistant", "content": response["content"]})
            self._track_llm_metrics(response)

            # Check if we're done (no tool calls)
            if response["stop_reason"] != "tool_use":
                return self._handle_final_response(user_message, response, start_time)

            # Execute tool calls
            results = self._execute_tools(response["content"])

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
        try:
            wrapped_call = wrap_llm_call_with_recovery(
                self.llm.chat,
                self.error_recovery,
                self.compactor,
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

    def _handle_final_response(self, user_message: str, response: Any, start_time: float) -> str:
        """Handle the final assistant response (no more tool calls)."""
        self.hooks.trigger("Stop", self.messages)
        response_text = extract_text(response["content"])

        if self.session:
            self.session.add_message("assistant", response_text)
            self.session.save()

        response_text = agent_hooks.post_process(self, user_message, response_text, start_time)

        duration = time.time() - start_time
        self.logger.info(
            "Agent loop completed",
            duration=duration,
            tool_calls=self.tool_call_count,
            message_count=len(self.messages),
        )

        if self.metrics:
            self.metrics.timer_stop("agent_loop", start_time)
            self.metrics.increment("completed_turns")

        return response_text

    def _execute_tools(self, content: Any) -> list[dict[str, Any]]:
        """Execute tool calls from LLM response.

        Args:
            content: Response content with tool calls

        Returns:
            List of tool results
        """
        results = []

        for block in content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input
            tool_id = block.id

            self.logger.info("Tool call", tool=tool_name, arguments=tool_input)

            # Trigger PreToolUse hook
            blocked = self.hooks.trigger("PreToolUse", block)
            if blocked:
                self.logger.warning("Tool blocked by hook", tool=tool_name, reason=blocked)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(blocked),
                })
                continue

            # Check cache for tool result
            if self.tool_cache:
                cached_result = self.tool_cache.get_result(tool_name, tool_input)
                if cached_result is not None:
                    self.logger.info("Cache hit for tool", tool=tool_name)
                    if self.metrics:
                        self.metrics.increment("tool_cache_hits")
                    output = cached_result
                else:
                    output = self._execute_tool(tool_name, tool_input)
                    # Cache read-only tools
                    if tool_name in ["read_file", "ls", "find", "grep"]:
                        self.tool_cache.set_result(tool_name, tool_input, output, ttl=300)
            else:
                output = self._execute_tool(tool_name, tool_input)

            # Trigger PostToolUse hook
            self.hooks.trigger("PostToolUse", block, output)

            results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": output,
            })

            self.tool_call_count += 1

            if self.metrics:
                self.metrics.increment(f"tool_calls_{tool_name}")
                self.metrics.increment("total_tool_calls")

            if self.session:
                self.session.increment_tool_calls()

        return results

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a single tool with timing and auto-checkpoint.

        Args:
            tool_name: Tool name
            tool_input: Tool arguments

        Returns:
            Tool output
        """
        # Maximum output size per tool (prevents context overflow from large files)
        max_tool_output = 100_000  # ~25K tokens

        start_time = time.time()

        # Auto-create checkpoint before destructive operations
        if self.checkpoint_manager:
            self.checkpoint_manager.create_pre_tool_snapshot(tool_name, tool_input)

        try:
            output = self.tools.execute(tool_name, **tool_input)
            duration = time.time() - start_time

            # Truncate large outputs to prevent context overflow
            output_str = str(output)
            if len(output_str) > max_tool_output:
                omitted = len(output_str) - max_tool_output
                output_str = (
                    output_str[:max_tool_output]
                    + f"\n\n... (output truncated, {omitted} "
                    f"chars omitted. Use read_file with limit= to read specific portions.)"
                )

            self.logger.debug(
                "Tool executed",
                tool=tool_name,
                duration=duration,
                output_length=len(output_str),
            )

            # Speculative prefetch for likely next reads
            if self.spec_exec:
                predicted = self.spec_exec.analyze_tool_call(
                    tool_name, tool_input, output_str
                )
                if predicted:
                    self.spec_exec.prefetch_files(self.workdir, predicted)

            if self.metrics:
                self.metrics.timer_stop(f"tool_{tool_name}", start_time)

            # Auto-commit after successful file edits (disabled by default)
            if self.config.auto_commit_enabled:
                commit_msg = auto_commit_after_edit(
                    self.workdir, tool_name, tool_input, output_str
                )
                if commit_msg:
                    self.logger.info("Auto-committed change", path=tool_input.get("path", ""))

            return output_str
        except Exception as e:
            self.logger.error("Tool execution failed", tool=tool_name, error=str(e), exc_info=True)
            if self.metrics:
                self.metrics.increment("tool_errors")
            error_str = str(e)

            # Attempt auto-healing
            healed = self.auto_healer.attempt_heal(
                tool_name, tool_input, error_str
            )
            if healed:
                self.logger.info("AutoHealer applied fix", tool=tool_name)
                if self.metrics:
                    self.metrics.increment("auto_heals")
                return healed

            return f"Error executing {tool_name}: {e}"

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
        import re

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
        import copy
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
        import re

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
                    context_parts.append(f"\n*(Could not resolve @symbol:{mvalue})*\n")

            elif mtype == "git":
                import subprocess
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

