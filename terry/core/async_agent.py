"""Async Agent loop with non-blocking ReAct execution.

The LLM I/O path (async_llm.AsyncLLMClient) is genuinely async via
httpx.AsyncClient. Tool execution, however, bridges synchronous tools through
loop.run_in_executor() — most built-in tools use blocking I/O, so true async
tool execution would require per-tool async rewrites. Streaming tool calls are
not yet supported (run_stream returns after the first response).
"""

from __future__ import annotations

import asyncio
from typing import Any

from .async_llm import AsyncLLMClient
from .text_utils import extract_text


class AsyncAgent:
    """Async agent with an asyncio-based ReAct loop.

    LLM calls are truly async (httpx.AsyncClient). Synchronous tools run via
    loop.run_in_executor() so they don't block the event loop, though they are
    not themselves async.
    """

    def __init__(
        self,
        config: Any,
        tools: list[dict[str, Any]],
        system_prompt: str,
        async_llm: AsyncLLMClient,
        tool_executor: Any,
        max_iterations: int = 50,
        max_tokens: int | None = None,
    ):
        self.config = config
        self.tools = tools
        self.system_prompt = system_prompt
        self.async_llm = async_llm
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens or config.max_tokens if hasattr(config, "max_tokens") else 4096

    async def run(self, messages: list[dict[str, Any]]) -> str:
        """Run the agent loop asynchronously.

        Args:
            messages: Conversation history

        Returns:
            Final assistant response
        """
        current_messages = list(messages)

        for iteration in range(self.max_iterations):
            # Call LLM asynchronously
            response = await self.async_llm.chat(
                messages=current_messages,
                system=self.system_prompt,
                tools=self.tools,
                max_tokens=self.max_tokens,
            )

            # Extract response content
            content = response.get("content", [])
            stop_reason = response.get("stop_reason", "end_turn")

            # Check if we're done
            if stop_reason == "end_turn" or not content:
                return extract_text(content)

            # Process tool calls
            tool_results = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_name = block.get("name")
                    tool_input = block.get("input", {})
                    tool_id = block.get("id")

                    # Execute tool asynchronously
                    try:
                        result = await self._execute_tool_async(tool_name, tool_input)
                    except Exception as e:
                        result = f"Error executing tool: {e}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    })

            # Add assistant message and tool results to conversation
            current_messages.append({"role": "assistant", "content": content})
            current_messages.append({"role": "user", "content": tool_results})

        # Max iterations reached
        return "Maximum iterations reached. Please break down your request into smaller steps."

    async def _execute_tool_async(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool asynchronously.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        # Run tool execution in thread pool to avoid blocking
        # This is necessary because most tools use synchronous I/O
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.tool_executor,
            tool_name,
            tool_input,
        )
        return result

    async def run_stream(self, messages: list[dict[str, Any]]) -> Any:
        """Run the agent loop with streaming output.

        Args:
            messages: Conversation history

        Yields:
            Text chunks as they arrive
        """
        current_messages = list(messages)

        for iteration in range(self.max_iterations):
            # Stream from LLM
            full_response = []
            async for chunk in self.async_llm.chat_stream(
                messages=current_messages,
                system=self.system_prompt,
                tools=self.tools,
                max_tokens=self.max_tokens,
            ):
                full_response.append(chunk)
                yield chunk

            # For now, streaming doesn't support tool calls
            # Just return after first response
            break

    async def close(self) -> None:
        """Clean up resources."""
        await self.async_llm.close()
