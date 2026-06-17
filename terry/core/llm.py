"""LLM client wrapper with multi-provider support via adapter registry."""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from .adapter import ProviderAdapter, get_provider
from .config import ModelConfig


class LLMClient:
    """Unified LLM client — uses adapter registry for provider discovery."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.adapter = self._resolve_adapter()
        self.provider_type = self._detect_provider_type()
        self.client = self._create_client()

    def reconfigure(self, new_config: ModelConfig) -> None:
        """Reconfigure the LLM client with new model settings at runtime.

        Recreates the internal SDK client and adapter so changes to
        provider, model, temperature, or base_url take effect immediately.

        Args:
            new_config: New ModelConfig to apply.
        """
        self.config = new_config
        self.adapter = self._resolve_adapter()
        self.provider_type = self._detect_provider_type()
        self.client = self._create_client()

    def _resolve_adapter(self) -> ProviderAdapter | None:
        """Find the matching provider adapter from the registry."""
        return get_provider(self.config.provider)

    def _detect_provider_type(self) -> str:
        """Detect if we should use Anthropic or OpenAI SDK."""
        if self.adapter and self.adapter.protocol == "anthropic":
            return "anthropic"
        # All other providers use OpenAI-compatible protocol
        return "openai"

    def _create_client(self) -> Anthropic | OpenAI:
        """Create the appropriate SDK client."""
        base_url = self.config.base_url
        if not base_url and self.adapter:
            base_url = self.adapter.base_url

        api_key = self.config.api_key
        if not api_key and self.adapter:
            api_key = os.environ.get(self.adapter.key_env, "")

        if self.provider_type == "anthropic":
            return Anthropic(api_key=api_key, base_url=base_url)
        else:
            return OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat request and return the response."""
        max_tokens = max_tokens or self.config.max_tokens

        if self.provider_type == "anthropic":
            return self._chat_anthropic(messages, system, tools, max_tokens)
        else:
            return self._chat_openai(messages, system, tools, max_tokens)

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ):
        """Send a chat request and yield text chunks as they arrive (streaming).

        Yields text chunks. Tool calls not supported in streaming mode.
        Falls back to non-streaming on error.
        """
        max_tokens = max_tokens or self.config.max_tokens

        try:
            if self.provider_type == "anthropic":
                kwargs = {
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                }
                if system:
                    kwargs["system"] = system
                if tools:
                    kwargs["tools"] = tools

                with self.client.messages.stream(**kwargs) as stream:
                    yield from stream.text_stream
            else:
                # OpenAI-compatible streaming
                openai_messages = []
                if system:
                    openai_messages.append({"role": "system", "content": system})
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        continue  # Skip tool messages in stream mode
                    openai_messages.append({"role": role, "content": str(content)})

                stream = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=openai_messages,
                    max_tokens=max_tokens,
                    stream=True,
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
        except Exception:
            pass  # pass  # llm.py  # FIXME: add module-level logger
            # Fallback: non-streaming
            response = self.chat(messages, system, tools, max_tokens)
            from .text_utils import extract_text
            yield extract_text(response["content"])

    def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Anthropic API call."""
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        # Normalize response format
        return {
            "content": response.content,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        """OpenAI-compatible API call."""
        # Convert messages format
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle tool results
            if role == "user" and isinstance(content, list):
                # Anthropic format: list of blocks
                # Convert to OpenAI format
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
                # Handle assistant with tool calls
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

        kwargs = {
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
            kwargs["tools"] = openai_tools

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        # Normalize response format to match Anthropic
        content_blocks = []
        if choice.message.content:
            content_blocks.append({"type": "text", "text": choice.message.content})

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    parsed_input = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except (json.JSONDecodeError, TypeError):
                    parsed_input = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": parsed_input,
                })

        stop_reason = "tool_use" if choice.message.tool_calls else "end_turn"

        return {
            "content": content_blocks,
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        }
