"""Terry SDK — Public API for embedding Terry in your own applications.

Usage:
    from terry.sdk import Agent, TerryConfig, BaseTool

    config = TerryConfig()
    config.model.api_key = "sk-ant-..."

    agent = Agent(config)
    agent.run("Find where authentication logic is implemented")
"""

from __future__ import annotations

# ── Configuration ───────────────────────────────────────────────────
from .core.config import TerryConfig, ModelConfig

# ── Agent ───────────────────────────────────────────────────────────
from .core.agent import Agent

# ── Tool System ─────────────────────────────────────────────────────
from .tools import BaseTool, ToolRegistry, discover_tools, tool_registry

# ── LLM ─────────────────────────────────────────────────────────────
from .core.llm import LLMClient

# ── Session ─────────────────────────────────────────────────────────
from .core.session import Session

# ── Memory ──────────────────────────────────────────────────────────
from .core.memory import Memory

# ── Checkpoints ─────────────────────────────────────────────────────
from .core.checkpoint import CheckpointManager

# ── Version ─────────────────────────────────────────────────────────
from . import __version__

__all__ = [
    # Config
    "TerryConfig",
    "ModelConfig",
    # Agent
    "Agent",
    # Tools
    "BaseTool",
    "ToolRegistry",
    "discover_tools",
    "tool_registry",
    # LLM
    "LLMClient",
    # Session
    "Session",
    # Memory
    "Memory",
    # Checkpoints
    "CheckpointManager",
    # Version
    "__version__",
]
