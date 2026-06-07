"""True async LLM client with multi-provider support."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .adapter import ProviderAdapter, get_provider
from .config import ModelConfig


class AsyncLLMClient:
    """True async LLM client — uses httpx.AsyncClient for non-blocking I/O.

    Unlike AsyncAgentLoop.run_in_executor(), this uses real async HTTP calls
    for true concurrency without thread overhead.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.adapter = self._resolve_adapter()
        self.provider_type = self._detect_provider_type()
        # Don't create client here - create per-request async client
        self._client: httpx.AsyncClient | None = None

    def _resolve_adapter(self) -> ProviderAdapter | None:
        """Find the matching provider adapter from the registry."""
        return get_provider(self.config.provider)

    def _detect_provider_type(self) -> str:
        """Detect if we should use Anthropic or OpenAI protocol."""
        if self.adapter and self.adapter.protocol == "anthropic":
            return "anthropic"
        return "openai"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            base_url = self.config.base_url
            if not base_url and self.adapter:
                base_url = self.adapter.base_url

            api_key = self.config.api_key
            if not api_key and self.adapter:
                api_key = os.environ.get(self.adapter.key_env, "")

            headers = {}
            if self.provider_type == "anthropic":
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {api_key}"

            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send an async chat request and return the response."""
        max_tokens = max_tokens or self.config.max_tokens

        if self.provider_type == "anthropic":
            return await self._chat_anthropic(messages, system, tools, max_tokens)
        else:
            return await self._chat_openai(messages, system, tools, max_tokens)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Send an async streaming chat request and yield text chunks."""
        max_tokens = max_tokens or self.config.max_tokens

        try:
            if self.provider_type == "anthropic":
                async for chunk in self._chat_anthropic_stream(messages, system, tools, max_tokens):
                    yield chunk
            else:
                async for chunk in self._chat_openai_stream(messages, system, tools, max_tokens):
                    yield chunk
        except Exception:
            # Fallback: non-streaming
            response = await self.chat(messages, system, tools, max_tokens)
            from .text_utils import extract_text
            yield extract_text(response["content"])

    async def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Async Anthropic API call."""
        client = await self._get_client()

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        response = await client.post("/v1/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        # Normalize response format
        return {
            "content": data.get("content", []),
            "stop_reason": data.get("stop_reason", "end_turn"),
            "usage": {
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
        }

    async def _chat_anthropic_stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Async streaming Anthropic API call."""
        client = await self._get_client()

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        async with client.stream("POST", "/v1/messages", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue

    async def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Async OpenAI-compatible API call."""
        client = await self._get_client()

        # Convert messages format
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle tool results
            if role == "user" and isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        })
                    elif isinstance(block, dict) and block.get("type") == "text":
                        openai_messages.append({
                            "role": role,
                            "content": block.get("text", ""),
                        })
            elif role == "assistant" and isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            text_parts.append(block.text)
                        elif block.type == "tool_use":
                            tool_calls.append({
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": str(block.input),
                                },
                            })

                msg_dict = {"role": role}
                if text_parts:
                    msg_dict["content"] = "\n".join(text_parts)
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
                openai_messages.append(msg_dict)
            else:
                openai_messages.append({"role": role, "content": content})

        payload = {
            "model": self.config.model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
        }

        # Convert tools to OpenAI format
        if tools:
            openai_tools = []
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                })
            payload["tools"] = openai_tools

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]

        # Normalize response format
        content_blocks = []
        if choice["message"].get("content"):
            content_blocks.append({"type": "text", "text": choice["message"]["content"]})

        if choice["message"].get("tool_calls"):
            for tc in choice["message"]["tool_calls"]:
                try:
                    parsed_input = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except (json.JSONDecodeError, TypeError):
                    parsed_input = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": parsed_input,
                })

        stop_reason = "tool_use" if choice["message"].get("tool_calls") else "end_turn"

        usage = data.get("usage", {})
        return {
            "content": content_blocks,
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }

    async def _chat_openai_stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Async streaming OpenAI-compatible API call."""
        client = await self._get_client()

        # Convert messages (same as _chat_openai)
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                continue
            openai_messages.append({"role": role, "content": str(content)})

        payload = {
            "model": self.config.model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("choices"):
                            delta = data["choices"][0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue


def create_async_llm(config: ModelConfig) -> AsyncLLMClient:
    """Factory function to create async LLM client."""
    return AsyncLLMClient(config)
