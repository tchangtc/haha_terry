"""Response handling subsystem — extracted from Agent to reduce class size.

The ResponseHandler processes the final LLM response after tool execution
completes, handling session persistence, hook post-processing, and metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .text_utils import extract_text

logger = logging.getLogger(__name__)


class ResponseHandler:
    """Handles final LLM response processing after tool execution completes.

    Responsibilities:
      - Extract text from the LLM response content blocks
      - Persist the assistant message to session history
      - Run post-processing hooks on the response text
      - Track timing and metrics for the agent loop

    Args:
        hooks: HookRegistry for Stop + post-processing triggers.
        session: Optional Session for persistence.
        metrics: Optional Metrics collector.
        logger: Parent agent's logger for structured logging.
    """

    def __init__(
        self,
        hooks: Any,
        session: Any = None,
        metrics: Any = None,
        parent_logger: logging.Logger | None = None,
    ):
        self.hooks = hooks
        self.session = session
        self.metrics = metrics
        self._log = parent_logger or logger

    def handle_final_response(
        self,
        agent: Any,
        user_message: str,
        response: Any,
        start_time: float,
        messages: list[dict[str, Any]],
    ) -> str:
        """Handle the final assistant response (no more tool calls).

        Args:
            agent: The Agent instance (needed by post_process hooks that
                   access fts_search, suggester, knowledge_graph, etc.).
            user_message: Original user input.
            response: Raw LLM response object with 'content' key.
            start_time: Agent loop start time (for duration calc).
            messages: Full conversation messages list.

        Returns:
            Extracted and post-processed response text.
        """
        self.hooks.trigger("Stop", messages)
        response_text = extract_text(response["content"])

        if self.session:
            self.session.add_message("assistant", response_text)
            self.session.save()

        from . import agent_hooks

        response_text = agent_hooks.post_process(agent, user_message, response_text, start_time)

        duration = time.time() - start_time
        self._log.info(
            "Agent loop completed",
            duration=f"{duration:.2f}s",
            message_count=len(messages),
        )

        if self.metrics:
            self.metrics.timer_stop("agent_loop", start_time)
            self.metrics.increment("completed_turns")

        return response_text
