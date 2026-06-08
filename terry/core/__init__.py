from __future__ import annotations

"""Terry Core — the brain of the harness.

This package contains the central agent loop, LLM abstraction,
multi-agent orchestration, memory, configuration, and all
intelligence subsystems that power Terry.

Key modules:
  - agent.py       — Main Agent class, the central orchestrator
  - harness.py     — HarnessEngine, multi-agent orchestration (8 patterns)
  - llm.py         — LLMClient, model abstraction layer
  - config.py      — TerryConfig, configuration management
  - session.py     — Session, conversation persistence
  - memory.py      — Memory, persistent knowledge storage
  - permissions.py — PermissionStore, access control

Sub-packages:
  - ai/            — Planning, thinking, skills, model intelligence
  - infra/         — Storage, telemetry, logging, platform utilities
  - scheduling/    — Cron, task DAG, autonomous execution
  - security/      — Rate limiting, input validation, auth, CORS
  - storage/       — Memory sync, knowledge graphs
"""
