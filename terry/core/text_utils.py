"""Text extraction utilities shared across agent modules."""

from __future__ import annotations

from typing import Any


def extract_text(content: Any) -> str:
    """Extract text from LLM response content.

    Handles both Anthropic (object-based) and OpenAI (dict-based) content formats.

    Args:
        content: Response content - can be a string, list of blocks, or list of dicts.

    Returns:
        Extracted text string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if hasattr(block, "type") and block.type == "text":
                text_parts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)
    return str(content)
