"""Tool execution subsystem — extracted from Agent to reduce class size.

The ToolExecutor handles the mechanics of dispatching tool calls from the
LLM response, including caching, hook triggers, auto-healing, output
truncation, metrics tracking, and auto-commit. The Agent delegates to
this class via composition.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .error_recovery import auto_commit_after_edit

logger = logging.getLogger(__name__)

# Maximum output size per tool (prevents context overflow from large files)
MAX_TOOL_OUTPUT = 100_000  # ~25K tokens


class ToolExecutor:
    """Executes tool calls from LLM response blocks.

    Handles the full tool execution lifecycle:
      1. Hook triggers (PreToolUse / PostToolUse)
      2. Tool result caching (read-only tools)
      3. Output truncation (prevents context overflow)
      4. Speculative prefetch
      5. Auto-commit after file edits (if enabled)
      6. Auto-healing on failure
      7. Metrics / session tracking

    Args:
        config: TerryConfig instance.
        tools: ToolRegistry instance.
        hooks: HookRegistry for PreToolUse/PostToolUse triggers.
        tool_cache: Optional tool result cache (LLMCache or compatible).
        checkpoint_manager: Optional CheckpointManager for undo support.
        spec_exec: Optional SpeculativeExecutor for prefetch.
        metrics: Optional Metrics collector.
        auto_healer: AutoHealer instance for error recovery.
        workdir: Working directory (default: cwd).
    """

    def __init__(
        self,
        config: Any,
        tools: Any,
        hooks: Any,
        tool_cache: Any = None,
        checkpoint_manager: Any = None,
        spec_exec: Any = None,
        metrics: Any = None,
        auto_healer: Any = None,
        session: Any = None,
        workdir: Any = None,
    ):
        self.config = config
        self.tools = tools
        self.hooks = hooks
        self.tool_cache = tool_cache
        self.checkpoint_manager = checkpoint_manager
        self.spec_exec = spec_exec
        self.metrics = metrics
        self.auto_healer = auto_healer
        self.session = session
        self.workdir = workdir

    def execute_tools(self, content: Any) -> tuple[list[dict[str, Any]], int]:
        """Execute tool calls from LLM response.

        Args:
            content: Response content blocks with tool_use entries.

        Returns:
            Tuple of (results_list, tool_call_count).
        """
        results = []
        tool_count = 0

        for block in content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input
            tool_id = block.id

            logger.info("Tool call: %s", tool_name)

            # Trigger PreToolUse hook
            blocked = self.hooks.trigger("PreToolUse", block)
            if blocked:
                logger.warning("Tool blocked by hook: %s — %s", tool_name, blocked)
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
                    logger.info("Cache hit for tool: %s", tool_name)
                    if self.metrics:
                        self.metrics.increment("tool_cache_hits")
                    output = cached_result
                else:
                    output = self._execute_one(tool_name, tool_input)
                    if tool_name in ("read_file", "ls", "find", "grep"):
                        self.tool_cache.set_result(tool_name, tool_input, output, ttl=300)
            else:
                output = self._execute_one(tool_name, tool_input)

            # Trigger PostToolUse hook
            self.hooks.trigger("PostToolUse", block, output)

            results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": output,
            })

            tool_count += 1

            if self.metrics:
                self.metrics.increment(f"tool_calls_{tool_name}")
                self.metrics.increment("total_tool_calls")

            if self.session:
                self.session.increment_tool_calls()

        return results, tool_count

    def _execute_one(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a single tool with timing, truncation, and auto-healing.

        Args:
            tool_name: Tool name.
            tool_input: Tool arguments.

        Returns:
            Tool output string (truncated if exceeds MAX_TOOL_OUTPUT).
        """
        start_time = time.time()

        # Auto-create checkpoint before destructive operations
        if self.checkpoint_manager:
            self.checkpoint_manager.create_pre_tool_snapshot(tool_name, tool_input)

        try:
            output = self.tools.execute(tool_name, **tool_input)
            duration = time.time() - start_time

            # Truncate large outputs to prevent context overflow
            output_str = str(output)
            if len(output_str) > MAX_TOOL_OUTPUT:
                omitted = len(output_str) - MAX_TOOL_OUTPUT
                output_str = (
                    output_str[:MAX_TOOL_OUTPUT]
                    + f"\n\n... (output truncated, {omitted} "
                    f"chars omitted. Use read_file with limit= to read specific portions.)"
                )

            logger.debug(
                "Tool executed: %s (%.2fs, %d chars)",
                tool_name, duration, len(output_str),
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
                    logger.info("Auto-committed change: %s", tool_input.get("path", ""))

            return output_str

        except Exception as e:
            logger.error("Tool execution failed: %s — %s", tool_name, e, exc_info=True)
            if self.metrics:
                self.metrics.increment("tool_errors")
            error_str = str(e)

            # Attempt auto-healing
            if self.auto_healer:
                healed = self.auto_healer.attempt_heal(
                    tool_name, tool_input, error_str
                )
                if healed:
                    logger.info("AutoHealer applied fix for %s", tool_name)
                    if self.metrics:
                        self.metrics.increment("auto_heals")
                    return healed

            return f"Error executing {tool_name}: {e}"
