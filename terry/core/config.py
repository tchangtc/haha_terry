"""Configuration system with multi-provider support."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .platform_utils import get_config_dir, get_data_dir
from .adapter import PROVIDERS as _ADAPTER_PROVIDERS, get_provider, list_providers


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
    model: str = "claude-sonnet-4-20250514"
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
    skills_paths: list[str] = field(default_factory=lambda: [
        "./skills",
        str(get_config_dir() / "skills")
    ])
    memory_enabled: bool = True
    memory_path: str = str(get_data_dir() / "memory")

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
        import stat
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
            "skills_paths": self.skills_paths,
            "memory_enabled": self.memory_enabled,
            "memory_path": self.memory_path,
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
            skills_paths=data.get("skills_paths", [
                "./skills",
                str(get_config_dir() / "skills")
            ]),
            memory_enabled=data.get("memory_enabled", True),
            memory_path=data.get("memory_path", str(get_data_dir() / "memory")),
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
