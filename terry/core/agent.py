"""Core agent loop - production-grade implementation with full feature set."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .config import TerryConfig
from .llm import LLMClient
from .context_compact import ContextCompactor
from .error_recovery import ErrorRecovery, wrap_llm_call_with_recovery
from .memory import Memory, get_memory
from .session import Session, get_session
from .subagent import SubAgentManager
from .logger import Logger, get_logger
from .metrics import Metrics, get_metrics, estimate_cost
from .cache import LLMCache, ToolCache, get_llm_cache, get_tool_cache
from .skill import SkillManager, SkillExecutor, get_skill_manager
from .text_utils import extract_text
from ..tools import ToolRegistry, discover_tools, tool_registry
from ..hooks import HookRegistry, hook_registry
from ..hooks.permission import permission_hook, SandboxMode
from ..hooks.logging_hook import log_hook


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

        # Initialize hooks (permission_hook uses config's sandbox_mode)
        self._mode: SandboxMode = SandboxMode(self.config.sandbox_mode)
        hook_registry.register("PreToolUse", log_hook)
        hook_registry.register(
            "PreToolUse",
            lambda block: permission_hook(block, self.workdir, self._mode),
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
        """Build comprehensive system prompt with context.

        Returns:
            System prompt string
        """
        parts = [
            f"You are Terry, a production-grade AI coding agent working in {self.workdir}.",
            "You have access to powerful tools for file operations, code search, and system commands.",
            "",
            "## Guidelines",
            "- Use tools to solve tasks efficiently",
            "- Be concise and helpful in your responses",
            "- Explain your reasoning when appropriate",
            "- Ask for clarification if the task is unclear",
            "",
            "## Available Tools",
        ]

        # Add tool descriptions
        for tool in self.tools.list_tools():
            parts.append(f"- **{tool.name}**: {tool.description}")

        # Add active skill context if available
        if self.active_skill and self.skill_manager:
            skill = self.skill_manager.get_skill(self.active_skill)
            if skill:
                skill_context = self.skill_manager.get_skill_context(skill)
                parts.extend([
                    "",
                    "## Active Skill",
                    skill_context,
                ])

        # Add available skills list
        if self.skill_manager:
            skills = self.skill_manager.list_skills()
            if skills:
                parts.extend([
                    "",
                    "## Available Skills",
                    "You have access to the following specialized skills:",
                ])
                for skill in skills:
                    parts.append(f"- **{skill.name}**: {skill.description}")
                parts.append("")
                parts.append("When a user request matches a skill's purpose, follow the skill's instructions.")

        # Add memory context if available
        if self.memory:
            memory_list = self.memory.list_memories()
            if memory_list:
                parts.extend([
                    "",
                    "## Your Memories",
                    "You have persistent memories from previous sessions:",
                ])
                for mem in memory_list[:10]:  # Limit to 10 memories
                    parts.append(f"- **{mem['name']}**: {mem['description']}")

        # Add current session info
        if self.session:
            parts.extend([
                "",
                "## Current Session",
                f"Session ID: {self.session.session_id}",
                f"Messages in session: {len(self.session.get_messages())}",
            ])

        return "\n".join(parts)

    def run(self, user_message: str, use_cache: bool = True) -> str:
        """Run the agent loop with full feature integration.

        Args:
            user_message: User's input message
            use_cache: Whether to use caching

        Returns:
            Agent's response
        """
        start_time = time.time()

        # Log user message
        self.logger.info("User message", length=len(user_message))

        # Match and activate skill if applicable
        if self.skill_manager:
            matched_skill = self.skill_manager.match_skill(user_message)
            if matched_skill:
                self.active_skill = matched_skill.name
                self.logger.info(f"Activated skill: {matched_skill.name}")

        # Add to session
        if self.session:
            self.session.add_message("user", user_message)

        # Add to conversation history
        self.messages.append({"role": "user", "content": user_message})

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

            # Check cache for response
            if use_cache and self.llm_cache:
                cached_response = self.llm_cache.get_response(
                    self.messages,
                    system=system,
                    tools=tools_def,
                    model=self.config.model.model,
                )
                if cached_response:
                    self.logger.info("Cache hit for LLM response")
                    if self.metrics:
                        self.metrics.increment("llm_cache_hits")
                    response = cached_response
                else:
                    response = self._call_llm(system, tools_def)
                    if response:
                        # Cache the response
                        self.llm_cache.set_response(
                            self.messages,
                            response,
                            system=system,
                            tools=tools_def,
                            model=self.config.model.model,
                        )
            else:
                response = self._call_llm(system, tools_def)

            if not response:
                return "Error: Failed to get LLM response"

            # Add assistant response to history
            self.messages.append({"role": "assistant", "content": response["content"]})

            # Track metrics
            if self.metrics and "usage" in response:
                usage = response["usage"]
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

                self.metrics.increment("input_tokens", input_tokens)
                self.metrics.increment("output_tokens", output_tokens)
                self.metrics.increment("llm_calls")

                # Estimate cost
                cost = estimate_cost(
                    self.config.model.name,
                    input_tokens,
                    output_tokens,
                )
                self.metrics.add_cost(self.config.model.provider, cost)

            # Check if we're done (no tool calls)
            if response["stop_reason"] != "tool_use":
                # Trigger Stop hook
                self.hooks.trigger("Stop", self.messages)

                # Extract response text
                response_text = extract_text(response["content"])

                # Add to session
                if self.session:
                    self.session.add_message("assistant", response_text)
                    self.session.save()

                # Log completion
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

            # Execute tool calls
            results = self._execute_tools(response["content"])

            # Add tool results to history
            self.messages.append({"role": "user", "content": results})

            # Save session periodically
            if self.session and len(self.messages) % 10 == 0:
                self.session.save()

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
        """Execute a single tool with timing.

        Args:
            tool_name: Tool name
            tool_input: Tool arguments

        Returns:
            Tool output
        """
        # Maximum output size per tool (prevents context overflow from large files)
        MAX_TOOL_OUTPUT = 100_000  # ~25K tokens

        start_time = time.time()

        try:
            output = self.tools.execute(tool_name, **tool_input)
            duration = time.time() - start_time

            # Truncate large outputs to prevent context overflow
            output_str = str(output)
            if len(output_str) > MAX_TOOL_OUTPUT:
                output_str = (
                    output_str[:MAX_TOOL_OUTPUT]
                    + f"\n\n... (output truncated, {len(output_str) - MAX_TOOL_OUTPUT} "
                    f"chars omitted. Use read_file with limit= to read specific portions.)"
                )

            self.logger.debug(
                "Tool executed",
                tool=tool_name,
                duration=duration,
                output_length=len(output_str),
            )

            if self.metrics:
                self.metrics.timer_stop(f"tool_{tool_name}", start_time)

            return output_str
        except Exception as e:
            self.logger.error("Tool execution failed", tool=tool_name, error=str(e), exc_info=True)
            if self.metrics:
                self.metrics.increment("tool_errors")
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

