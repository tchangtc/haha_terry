"""Configuration system with multi-provider support."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .adapter import PROVIDERS as _ADAPTER_PROVIDERS
from .platform_utils import get_config_dir, get_data_dir


@dataclass
class ProviderInfo:
    """LLM provider metadata."""
    key: str
    name: str
    base_url: str
    key_env: str
    default_model: str
    models: list[str]
    key_help: str


# Backward-compatible PROVIDER_REGISTRY — now powered by adapter.py
# Add new providers in adapter.py, not here.
PROVIDER_REGISTRY: dict[str, ProviderInfo] = {
    key: ProviderInfo(
        key=key,
        name=a.name,
        base_url=a.base_url,
        key_env=a.key_env,
        default_model=a.default_model,
        models=a.models,
        key_help=a.key_help,
    )
    for key, a in _ADAPTER_PROVIDERS.items()
}


@dataclass
class ModelConfig:
    """Model configuration."""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6-20250922"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 8000

    def resolve(self):
        """Fill in missing fields from provider registry."""
        entry = PROVIDER_REGISTRY.get(self.provider)
        if entry:
            if not self.base_url:
                self.base_url = entry.base_url
            if not self.api_key:
                self.api_key = os.environ.get(entry.key_env, "")


@dataclass
class TerryConfig:
    """Main configuration."""
    model: ModelConfig = field(default_factory=ModelConfig)
    max_tool_calls: int = 50
    max_input_tokens: int = 200000
    compression_threshold: float = 0.75
    sandbox_mode: str = "ask"  # ask | auto | deny
    permission_level: str = "medium"  # low | medium | high | critical
    skills_paths: list[str] = field(default_factory=lambda: [
        "./skills",
        str(get_config_dir() / "skills")
    ])
    memory_enabled: bool = True
    memory_path: str = str(get_data_dir() / "memory")
    auto_commit_enabled: bool = False  # OFF by default — auto-commit after file edits

    # Timeouts (seconds)
    llm_timeout: float = 60.0
    web_fetch_timeout: float = 30.0
    web_search_timeout: float = 30.0
    weather_timeout: float = 10.0

    # Rate limiting
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Security
    max_body_size: int = 10 * 1024 * 1024  # 10 MB
    max_prompt_length: int = 100_000

    # Auto-healer
    auto_healer_max_attempts: int = 2

    # Feedback
    feedback_sample_rate: float = 0.15
    feedback_min_interval: int = 30
    feedback_auto_dismiss: int = 6

    # RAG
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 100
    rag_max_documents: int = 200
    rag_min_score: float = 0.05
    rag_top_k: int = 5
    rag_max_files: int = 100
    rag_exclude_dirs: set[str] = field(
        default_factory=lambda: {".git", "__pycache__", "node_modules", ".venv"}
    )
    rag_include_extensions: set[str] = field(
        default_factory=lambda: {".py", ".md", ".yaml", ".json", ".toml", ".txt"}
    )

    # Cache
    cache_default_ttl: int = 3600
    cache_llm_ttl: int = 3600
    cache_tool_ttl: int = 300

    def validate(self) -> list[str]:
        """Validate configuration and return a list of warnings/errors.

        Returns:
            List of validation messages (empty = valid).
        """
        issues = []

        if self.model.temperature < 0 or self.model.temperature > 2:
            issues.append(f"model.temperature ({self.model.temperature}) should be between 0 and 2")
        if self.model.max_tokens < 1:
            issues.append(f"model.max_tokens ({self.model.max_tokens}) must be positive")
        if self.model.max_tokens > 2000000:
            issues.append(f"model.max_tokens ({self.model.max_tokens}) is unusually large")
        if self.max_tool_calls < 1:
            issues.append(f"max_tool_calls ({self.max_tool_calls}) must be positive")
        if self.max_tool_calls > 1000:
            issues.append(f"max_tool_calls ({self.max_tool_calls}) is unusually large")
        if self.max_input_tokens < 1000:
            issues.append(f"max_input_tokens ({self.max_input_tokens}) is too low")
        if self.compression_threshold < 0.1 or self.compression_threshold > 0.95:
            issues.append(
                f"compression_threshold ({self.compression_threshold}) "
                f"should be between 0.1 and 0.95"
            )
        if self.sandbox_mode not in ("ask", "auto", "deny"):
            issues.append(f"sandbox_mode '{self.sandbox_mode}' should be ask/auto/deny")
        if self.model.provider not in PROVIDER_REGISTRY:
            issues.append(
                f"Unknown provider '{self.model.provider}'. "
                f"Known: {', '.join(PROVIDER_REGISTRY.keys())}"
            )

        return issues

    @classmethod
    def load(cls, config_path: str | None = None) -> TerryConfig:
        """Load config from file or defaults."""
        if config_path is None:
            config_path = cls._find_config()

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                data = json.load(f)
            cfg = cls._from_dict(data)
        else:
            cfg = cls()

        cfg.model.resolve()
        return cfg

    def save(self, config_path: str):
        """Save config to file (api_key excluded from output)."""
        with open(config_path, "w") as f:
            json.dump(self._to_dict(), f, indent=2)
        # Set file permissions to 600 (owner read/write only) to protect config
        try:
            os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # best effort

    def _to_dict(self) -> dict:
        return {
            "model": {
                "provider": self.model.provider,
                "model": self.model.model,
                # api_key intentionally excluded — always read from env vars
                "base_url": self.model.base_url,
                "temperature": self.model.temperature,
                "max_tokens": self.model.max_tokens,
            },
            "max_tool_calls": self.max_tool_calls,
            "max_input_tokens": self.max_input_tokens,
            "compression_threshold": self.compression_threshold,
            "sandbox_mode": self.sandbox_mode,
            "permission_level": self.permission_level,
            "skills_paths": self.skills_paths,
            "memory_enabled": self.memory_enabled,
            "memory_path": self.memory_path,
            # Timeouts
            "llm_timeout": self.llm_timeout,
            "web_fetch_timeout": self.web_fetch_timeout,
            "web_search_timeout": self.web_search_timeout,
            "weather_timeout": self.weather_timeout,
            # Rate limiting
            "rate_limit_max_requests": self.rate_limit_max_requests,
            "rate_limit_window_seconds": self.rate_limit_window_seconds,
            # Security
            "max_body_size": self.max_body_size,
            "max_prompt_length": self.max_prompt_length,
            # Auto-healer
            "auto_healer_max_attempts": self.auto_healer_max_attempts,
            # Feedback
            "feedback_sample_rate": self.feedback_sample_rate,
            "feedback_min_interval": self.feedback_min_interval,
            "feedback_auto_dismiss": self.feedback_auto_dismiss,
            # RAG
            "rag_chunk_size": self.rag_chunk_size,
            "rag_chunk_overlap": self.rag_chunk_overlap,
            "rag_max_documents": self.rag_max_documents,
            "rag_min_score": self.rag_min_score,
            "rag_top_k": self.rag_top_k,
            "rag_max_files": self.rag_max_files,
            "rag_exclude_dirs": list(self.rag_exclude_dirs),
            "rag_include_extensions": list(self.rag_include_extensions),
            # Cache
            "cache_default_ttl": self.cache_default_ttl,
            "cache_llm_ttl": self.cache_llm_ttl,
            "cache_tool_ttl": self.cache_tool_ttl,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> TerryConfig:
        model_data = data.get("model", {})
        model = ModelConfig(
            provider=model_data.get("provider", "anthropic"),
            model=model_data.get("model", "claude-sonnet-4-20250514"),
            api_key=model_data.get("api_key"),
            base_url=model_data.get("base_url"),
            temperature=model_data.get("temperature", 0.7),
            max_tokens=model_data.get("max_tokens", 8000),
        )
        return cls(
            model=model,
            max_tool_calls=data.get("max_tool_calls", 50),
            max_input_tokens=data.get("max_input_tokens", 200000),
            compression_threshold=data.get("compression_threshold", 0.75),
            sandbox_mode=data.get("sandbox_mode", "ask"),
            permission_level=data.get("permission_level", "medium"),
            skills_paths=data.get("skills_paths", [
                "./skills",
                str(get_config_dir() / "skills")
            ]),
            memory_enabled=data.get("memory_enabled", True),
            memory_path=data.get("memory_path", str(get_data_dir() / "memory")),
            # Timeouts
            llm_timeout=data.get("llm_timeout", 60.0),
            web_fetch_timeout=data.get("web_fetch_timeout", 30.0),
            web_search_timeout=data.get("web_search_timeout", 30.0),
            weather_timeout=data.get("weather_timeout", 10.0),
            # Rate limiting
            rate_limit_max_requests=data.get("rate_limit_max_requests", 100),
            rate_limit_window_seconds=data.get("rate_limit_window_seconds", 60),
            # Security
            max_body_size=data.get("max_body_size", 10 * 1024 * 1024),
            max_prompt_length=data.get("max_prompt_length", 100_000),
            # Auto-healer
            auto_healer_max_attempts=data.get("auto_healer_max_attempts", 2),
            # Feedback
            feedback_sample_rate=data.get("feedback_sample_rate", 0.15),
            feedback_min_interval=data.get("feedback_min_interval", 30),
            feedback_auto_dismiss=data.get("feedback_auto_dismiss", 6),
            # RAG
            rag_chunk_size=data.get("rag_chunk_size", 500),
            rag_chunk_overlap=data.get("rag_chunk_overlap", 100),
            rag_max_documents=data.get("rag_max_documents", 200),
            rag_min_score=data.get("rag_min_score", 0.05),
            rag_top_k=data.get("rag_top_k", 5),
            rag_max_files=data.get("rag_max_files", 100),
            rag_exclude_dirs=set(
                data.get("rag_exclude_dirs", [".git", "__pycache__", "node_modules", ".venv"])
            ),
            rag_include_extensions=set(
                data.get("rag_include_extensions", [".py", ".md", ".yaml", ".json", ".toml", ".txt"])
            ),
            # Cache
            cache_default_ttl=data.get("cache_default_ttl", 3600),
            cache_llm_ttl=data.get("cache_llm_ttl", 3600),
            cache_tool_ttl=data.get("cache_tool_ttl", 300),
        )

    @staticmethod
    def _find_config() -> str | None:
        """Find config file in standard locations."""
        candidates = [
            "./terry.json",
            "./.terry/terry.json",
            str(get_config_dir() / "config.json"),
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        return None
