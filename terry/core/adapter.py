"""Unified LLM adapter registry — add providers without code changes.

Usage:
  from terry.core.adapter import AdapterRegistry, ProviderAdapter
  reg = AdapterRegistry()
  reg.register(ProviderAdapter(name="openai", base_url="https://api.openai.com/v1", ...))
  client = reg.create_client("openai", api_key="sk-...")
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Provider Adapter dataclass ─────────────────────────────────────

@dataclass
class ProviderAdapter:
    """Declarative LLM provider definition — no code needed for new providers."""
    name: str                          # e.g. "anthropic", "openai", "deepseek"
    base_url: str                      # API endpoint
    default_model: str                 # e.g. "claude-sonnet-4-20250514"
    models: list[str] = field(default_factory=list)
    key_env: str = ""                  # env var for API key
    protocol: str = "anthropic"        # "anthropic" | "openai-compatible"
    key_help: str = ""                 # URL for obtaining API key
    description: str = ""              # human-readable


# ── Built-in provider registry ─────────────────────────────────────

PROVIDERS: dict[str, ProviderAdapter] = {
    "anthropic": ProviderAdapter(
        name="Anthropic",
        base_url="https://api.anthropic.com",
        default_model="claude-sonnet-4-20250514",
        models=[
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
        ],
        key_env="ANTHROPIC_API_KEY",
        protocol="anthropic",
        key_help="https://console.anthropic.com/settings/keys",
        description="Anthropic Claude models — best for complex coding and analysis",
    ),
    "openai": ProviderAdapter(
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        models=["gpt-4o", "gpt-4o-mini", "o1"],
        key_env="OPENAI_API_KEY",
        protocol="openai-compatible",
        key_help="https://platform.openai.com/api-keys",
        description="OpenAI GPT models — broad general-purpose capability",
    ),
    "deepseek": ProviderAdapter(
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=["deepseek-chat", "deepseek-reasoner"],
        key_env="DEEPSEEK_API_KEY",
        protocol="openai-compatible",
        key_help="https://platform.deepseek.com/api_keys",
        description="DeepSeek models — cost-effective for coding tasks",
    ),
    "zhipu": ProviderAdapter(
        name="Zhipu GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        models=["glm-4-flash", "glm-4-plus", "glm-4-long"],
        key_env="ZHIPU_API_KEY",
        protocol="openai-compatible",
        key_help="https://open.bigmodel.cn/usercenter/apikeys",
        description="Zhipu GLM models — strong Chinese language support",
    ),
    "qwen": ProviderAdapter(
        name="Qwen (Alibaba)",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        models=["qwen-plus", "qwen-max", "qwen-turbo"],
        key_env="DASHSCOPE_API_KEY",
        protocol="openai-compatible",
        key_help="https://dashscope.console.aliyun.com/apiKey",
        description="Alibaba Qwen models — competitive performance",
    ),
    "ollama": ProviderAdapter(
        name="Ollama (Local)",
        base_url="http://localhost:11434/v1",
        default_model="llama3",
        models=["llama3", "mistral", "codellama", "qwen2", "deepseek-coder"],
        key_env="",  # Ollama doesn't require an API key
        protocol="openai-compatible",
        key_help="https://ollama.com/download",
        description="Local LLMs via Ollama — fully offline, zero cost",
    ),
}

# ── Custom provider support ────────────────────────────────────────

_custom_providers: dict[str, ProviderAdapter] = {}


def register_provider(adapter: ProviderAdapter) -> None:
    """Register a custom provider at runtime."""
    _custom_providers[adapter.name.lower()] = adapter


def get_provider(name: str) -> ProviderAdapter | None:
    """Get provider by name (checks built-in then custom)."""
    key = name.lower()
    return PROVIDERS.get(key) or _custom_providers.get(key)


def list_providers() -> list[ProviderAdapter]:
    """List all available providers."""
    return list(PROVIDERS.values()) + list(_custom_providers.values())


def resolve_api_key(provider: ProviderAdapter) -> str:
    """Resolve API key from environment or .env."""
    import os
    if provider.key_env:
        return os.environ.get(provider.key_env, "")
    return ""
