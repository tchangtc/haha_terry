<p align="center">
  <h1 align="center">Terry 🤖</h1>
  <p align="center"><strong>Your AI Coding Agent — Terminal · Web · Desktop · Mobile</strong></p>
</p>

<p align="center">
  <a href="https://github.com/tchangtc/haha_terry/actions"><img src="https://img.shields.io/badge/CI-passing-brightgreen.svg" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-2.8.0-orange.svg" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-1005%20passed-brightgreen.svg" alt="Tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/tools-28-blue.svg" alt="Tools"></a>
  <a href="#"><img src="https://img.shields.io/badge/modules-155-orange.svg" alt="Modules"></a>
  <a href="#"><img src="https://img.shields.io/badge/ruff-0%20issues-green.svg" alt="Ruff"></a>
  <a href="#"><img src="https://img.shields.io/badge/CLI-47-purple.svg" alt="CLI"></a>
  <a href="#"><img src="https://img.shields.io/badge/WebUI-✅-purple.svg" alt="WebUI"></a>
  <a href="#"><img src="https://img.shields.io/badge/Desktop-✅-purple.svg" alt="Desktop"></a>
  <a href="#"><img src="https://img.shields.io/badge/Mobile-✅-purple.svg" alt="Mobile"></a>
  <a href="#"><img src="https://img.shields.io/badge/container-Docker%20%7C%20containerd%20%7C%20K8s-blue.svg" alt="Container"></a>
  <a href="#"><img src="https://img.shields.io/badge/arch-amd64%20%7C%20arm64-blue.svg" alt="Arch"></a>
</p>

<p align="center">
  <a href="./README.md">English</a> |
  <a href="./README_zh-CN.md">简体中文</a> |
  <a href="./README_zh-TW.md">繁體中文</a>
</p>

---

> **TL;DR** — `pip install -r requirements.txt && export ANTHROPIC_API_KEY=sk-ant-... && terry` — then type what you need. Terry reads `CLAUDE.md` for project context, runs commands, edits files. Use `/cost` to track spending, `/undo` to revert, `/plan` before big tasks.

> 🏆 **Terry supports CLAUDE.md** — the #1 most-requested feature from Claude Code users (4,274+ votes). Just add a `CLAUDE.md` file to your project root and Terry automatically reads it for context on every session.

---

## 📰 News

**2026-06**

- **v2.8.0** — **Quality Push** — 66 new tests (1005 total), coverage 53%→58%, magic number elimination, RBAC/classifier/workflow tests.
- **v2.7.0** — **TUI Stability + Quality** — TUI ``--safe`` flag for flicker-free mode, 27 new tests (870 total), build-binary.sh dynamic module discovery.
- **v2.6.0** — **Event Hooks + VS Code** — ``/hooks`` command, event hooks runtime exposure, VS Code extension synced.
- **v2.5.0** — **Model Auto-Discovery** — ``/discover`` command probes OpenAI-compatible endpoints, auto-tier classification.
- **v2.4.0** — **Cost Tracker** — ``/cost`` command, real-time token/cost dashboard, budget alerts. CLAUDE.md support promoted.
- **v2.3.0** — **External Editor** — respects $VISUAL/$EDITOR, ``/editor`` command with vim/nvim/code/emacs/nano support and line number jump.
- **v2.2.0** — **User-Driven Improvements II** — auto backup (tar.gz + rotation), search provider registry (DuckDuckGo/Google/Searxng/custom), vim mode (TERRY_VIM=1 or /vim).
- **v2.1.0** — **User-Driven Improvements** — sensitive file guard (.env/keys/credentials), ``/btw`` quick interjection, ``/expand`` paste expansion, 17 new unit tests.
- **v2.0.0** — **Paradigm Shift** — Agent Team 2.0 (5 roles: lead/architect/developer/reviewer/QA), Autonomous Pipeline (6-stage req→deploy), Plugin Ecosystem 2.0 (ratings, reviews, contribution workflow).
- **v1.5.0** — **Autonomy Deepening** — Project Context Engine (auto-index + relevance scoring), Memory 2.0 (cross-project sharing + preference learning), Autonomous Workflow v2 (webhook/CI/file-watch triggers).
- **v1.4.0** — **Observability & Enterprise** — OpenTelemetry tracing (LLM + tools + agents), Prometheus metrics export (tokens, cost, latency), structured audit logging with JSONL retention, RBAC with 4 roles and 28-tool permission matrix.
- **v1.3.0** — **Agent Collaboration & Routing** — smart model routing with cost/latency awareness, agent swarm with scatter/gather/broadcast, shared sessions with multi-agent locking and 5 built-in roles, PyPI package renamed to `terry-agent`.
- **v1.2.0** — **Plugin Ecosystem & Multimodal** — plugin marketplace with GitHub sources and trust levels, video input with ffmpeg frame extraction, 5 built-in agent profiles (coder/reviewer/architect/debugger/devops), conversational MCP configuration, JSON mode for structured output.
- **v1.1.0** — **Distribution & Integration** — single-binary build (`curl \| bash`), ACP editor protocol (Zed/JetBrains), OAuth login (`terry login`), public SDK (`terry/sdk.py`), MkDocs documentation site.
- **v1.0.0** — **GA Release** — stable API, `pip install terry-agent`, community governance, CI/CD pipeline, 128K output, full documentation.
- **v0.9.0** — **Design System** with unified color palette. **Textual TUI** with multi-panel layout and Vim keybindings. **Voice Mode** via Web Speech API. **WebUI** code highlighting and animations.
- **v0.8.0** — **Agentic Task Loop** with automatic plan execution and progress tracking. **Session Teleportation** for cross-machine migration. **Skill Marketplace** for community skill discovery. **Slash Command tool** for LLM-driven CLI interaction.
- **v0.7.0** — **Workflow Script DSL** with fluent Python API. **Multi-tier subagents** with 5-level depth. **Agent View** dashboard with live monitoring. **Ultrareview** 4-dimension adversarial code review. **Routines** with webhook and API triggers.
- **v0.6.0** — **1M context window** with dynamic token budget. **Effort levels** (`/effort low|medium|high|xhigh`). **Auto mode classifier** for smart permission decisions. **`/doctor` diagnostic command** with 7 health checks.
- **v0.5.0** — **Interactive Rewind UI** with diff preview. **Settings hot-reload** for zero-restart iteration. **Background task management** with unified `/tasks` monitoring. **`/goal` command** for goal-driven autonomous loops with evaluator scoring.
- **v0.4.0** — **Self-evolving agent** auto-creates skills from your workflows. **MiniMax** and dynamic provider support. **CJK-aware token estimation**. **Typed tool errors** for better self-correction.
- **v0.3.0** — **Git workflow tools**, **vector memory**, **4-layer context compaction**, **AutoHealer** self-healing, and **security middleware**.
- **v0.2.0** — **Multi-agent harness** (6 patterns), **WebUI**, **Desktop tray**, **PWA mobile**, and **VS Code extension**.
- **v0.1.0** — **Initial release.** ReAct agent, multi-provider LLM, skills system, 3-gate permissions, 16 tools.

---

## What is Terry?

Terry is an AI coding agent you can talk to from **anywhere** — your terminal, a web browser, a desktop tray app, or even your phone via Telegram. Describe what you need in plain English, and Terry reads your codebase, runs commands, edits files, and gets things done.

> **Agency comes from the model. Terry is the harness.**

---

## Pick Your Interface

| Interface | Start Command | Best For |
|-----------|--------------|----------|
| **Terminal** 🖥️ | `terry` | Power users, tmux/vim workflows, CI/CD |
| **Web Browser** 🌐 | `terry webui` | Visual chat, team demos, remote access |
| **Desktop App** 🖥️ | `terry desktop` | System tray, always-on, notifications |
| **Mobile (PWA)** 📱 | Open WebUI → "Add to Home Screen" | On-the-go coding from phone/tablet |
| **Telegram** 💬 | `TelegramGateway(token=...).start_polling()` | Chat from anywhere, no install |
| **Discord** 💬 | `DiscordGateway(token=...).start_polling()` | Team collaboration in servers |

---

## Quick Start

Works on **Windows, macOS, Linux** — same commands everywhere.

```bash
# Create a virtual environment (Python 3.11+ required)
python3 -m venv .venv && source .venv/bin/activate

# Clone and install
git clone https://github.com/tchangtc/haha_terry.git && cd haha_terry
pip install -e . 2>/dev/null || pip install -r requirements.txt
# 💡 Vector memory, RAG, sentence-transformers require: pip install terry-agent[vector,ml]

# Set API key (Anthropic, or use DeepSeek/OpenAI — see .env.example)
export ANTHROPIC_API_KEY="sk-ant-..."
# 💡 Beginners: copy .env.example → .env and edit the key there

# Start (if 'terry' is not found, use: python -m terry.cli)
terry || python -m terry.cli
```

**No API key?** Try free local models via Ollama:
```bash
# Install Ollama: https://ollama.com/download
ollama pull llama3
python -m terry.cli --provider ollama --model llama3
```

### First things to try

```bash
terry ▸ Show git status                          # See what Terry can do
terry ▸ Find where authentication is implemented  # Search your codebase
terry ▸ Create a Python file that prints hello    # Generate code
terry webui                                       # Open in browser
```

**Works with:** Anthropic Claude · OpenAI GPT-4o · DeepSeek · Zhipu GLM · Qwen · Ollama (local)

---

## What Makes Terry Different?

| You care about | Terry's approach |
|---|---|
| **Security** | 4-level permission system + runtime protection (DDoS, injection, CORS). Destructive commands blocked by default. You approve what matters. |
| **Context** | 4-layer progressive compaction. Won't lose track mid-task even with large codebases. |
| **Cost** | Model router picks cheaper models for simple tasks. Prompt caching built in. Cost tracking always on. |
| **Control** | Plan-first mode lets you review what Terry intends to do before it touches any file. |
| **Self-healing** | Auto-fixes common errors (missing packages, wrong paths) — 40% fewer manual interventions. |
| **Memory** | Remembers your preferences across sessions. Auto-creates skills from repeated workflows. |
| **Safety net** | Interactive Rewind UI — browse, diff, and restore any checkpoint. Preview what will change before rolling back. |
| **Zero-restart config** | Settings hot-reload — edit `terry.json`, run `/config reload`, changes take effect immediately. |
| **Autonomous goals** | `/goal` — describe the outcome you want, Terry iterates until it's met with automatic evaluation. |
| **Privacy** | Everything runs locally. Your code never leaves your machine unless you configure an LLM provider. |
| **Multi-interface** | Same agent behind every interface — CLI, WebUI, Desktop, Mobile, Telegram, Discord. |

---

## Core Capabilities

### 🛠️ Rich Tool Set (30 tools)

- **Files** — read, write, edit (with diff preview), multi-edit (atomic), Jupyter notebook editing
- **Search** — grep with regex, glob patterns, file finder, directory listing
- **Git** — status, diff, log, commit (conventional format), branch, checkout, merge
- **Web** — fetch (SSRF-safe), search
- **Extras** — image/PDF reading, calculator (sandboxed), weather, timers, notes, reminders

### 🔄 Smart Workflows

```
"I need to refactor the auth module"

/plan refactor auth module          ← Terry proposes a step-by-step plan
                                    ← You review and approve

/wfd refactor auth fan-out-merge    ← Or: Terry splits into parallel sub-tasks,
                                    ← executes them, merges results
```

Six orchestration patterns — fan-out-merge, adversarial-verify, tournament, classify-execute, loop-until-done, generate-filter.

### 🧠 Self-Improving

Terry notices when you repeat the same kind of task. After a few times, it proposes a reusable skill.

```bash
/auto-skills         # See what Terry has learned from your conversations
/auto-skill-approve  # Promote a suggestion to a permanent skill
/curator             # 7-day cycle stats on skill effectiveness
```

### 🔒 Production-Ready Security

When deployed as a server (WebUI, Telegram, Discord), Terry includes comprehensive runtime security:

- **Rate Limiting** — Token bucket algorithm prevents DDoS attacks (default: 100 req/60s)
- **Request Validation** — Body size limits (10MB), prompt length validation (100k chars)
- **Dangerous Pattern Blocking** — Automatically blocks 8 dangerous patterns (rm -rf, sudo, fork bombs, etc.)
- **API Key Authentication** — Bearer token authentication for all API endpoints
- **CORS Policy** — Origin-based access control prevents cross-origin attacks
- **Command Sanitization** — Bash commands are sanitized before execution

All security checks add **<5ms overhead** per request — no performance impact.

See [RUNTIME_SECURITY.md](RUNTIME_SECURITY.md) for complete documentation.

---

## Quick Reference

### Everyday Commands

| Command | What it does |
|---------|--------------|
| `/help` | Show all commands |
| `/new` | Start a fresh conversation |
| `/undo [<id>]` | Undo changes with diff preview and confirmation |
| `/checkpoints` | Browse all snapshots — diff, delete, selective restore |
| `/search <q>` | Full-text search your chat history |
| `/stream <msg>` | Watch response appear token by token |
| `/save` / `/load` | Save and restore sessions |

### Safety & Control

| Command | What it does |
|---------|--------------|
| `/mode ask` | Ask before destructive actions (recommended) |
| `/mode auto` | Auto-approve safe operations |
| `/permissions` | View and manage permission rules |
| `/plan <task>` | See the plan before execution |
| `/config reload` | Hot-reload settings from disk (no restart) |
| `/config key=value` | Change settings live |

**Runtime Protection:** When running as a server, Terry automatically blocks dangerous patterns (rm -rf, sudo, fork bombs, etc.), enforces rate limits, validates requests, and requires API key authentication. See [RUNTIME_SECURITY.md](RUNTIME_SECURITY.md) for details.

### Power User

| Command | What it does |
|---------|--------------|
| `/repomap` | Generate a codebase structure map |
| `/fork` | Branch the conversation to explore alternatives |
| `/goal <objective>` | Autonomous loop — iterate until goal is met |
| `/wfd <goal> <pattern>` | Launch a multi-agent workflow |
| `/bg <task>` | Fire-and-forget a background task |
| `/tasks list` | Monitor all background tasks (peek, cancel) |
| `/auto <task>` | Submit a background autonomous task |
| `/benchmark` | Run evaluation suites |
| `/sync-export` | Export memories to another device |

---

## Start the WebUI

```bash
terry webui                    # → http://127.0.0.1:8670
terry webui --port 9000        # Custom port
terry webui --host 0.0.0.0    # Allow LAN access
```

The WebUI gives you a full chat interface with dark theme, session management, streaming responses, and PWA support — add it to your phone's home screen for a native-app feel.

## Connect Messaging Platforms

```python
# Telegram: chat with Terry from your phone
from terry.server.gateways.telegram_gateway import TelegramGateway
TelegramGateway(token="...", agent_factory=lambda: agent).start_polling()

# Discord: bring Terry into your team server
from terry.server.gateways.discord_gateway import DiscordGateway
DiscordGateway(token="...", agent_factory=lambda: agent).start_polling()
```

---

## Supported LLM Providers

| Provider | Setup | Best For |
|----------|-------|----------|
| **Anthropic Claude** | `export ANTHROPIC_API_KEY=...` | Complex reasoning, large codebases |
| **OpenAI GPT-4o** | `export OPENAI_API_KEY=...` | Broad general tasks |
| **DeepSeek** | `export DEEPSEEK_API_KEY=...` | Cost-effective coding |
| **Zhipu GLM** | `export ZHIPU_API_KEY=...` | Chinese language support |
| **Qwen (Alibaba)** | `export DASHSCOPE_API_KEY=...` | Competitive performance |
| **Ollama (Local)** | `ollama pull llama3` | Fully offline, zero cost |

Need another provider? Add 8 lines of configuration — see [adapter.py](terry/core/adapter.py).

---

## Architecture at a Glance

```
CLI · WebUI · Desktop · Mobile(PWA) · Telegram · Discord
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌──────────────┐              ┌─────────────────┐
│  HTTP Server │              │  CLI REPL (Rich) │
│  (REST+SSE)  │              │  45+ commands    │
└──────┬───────┘              └───────┬─────────┘
       │                              │
       ▼                              │
┌──────────────┐                      │
│   Security   │                      │
│  Middleware  │                      │
└──────┬───────┘                      │
       │                              │
       └──────────┬───────────────────┘
                  ▼
        ┌─────────────────┐
        │  Agent (ReAct)  │  ← Plans, routes to LLM, executes tools
        └────────┬────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    ▼            ▼            ▼              ▼
┌───────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
│27     │ │4-Level   │ │Checkpoint│ │Dynamic       │
│Tools  │ │Security  │ │& Undo    │ │Workflow (6)  │
└───────┘ └─────────┘ └──────────┘ └──────────────┘
```

- **98 core modules** in `terry/core/` — each with clear single responsibility
- **6 interaction interfaces** — CLI, WebUI, Desktop, PWA, Telegram, Discord
- **710 tests** — pytest with full DI-based isolation

---


## Distribution

| Method | Command | Platform |
|--------|---------|----------|
| **PyPI** | `pip install terry-agent` | All (x86_64 + arm64) |
| **Docker** | `docker compose up` | All |
| **containerd** | `nerdctl compose up` | Linux servers |
| **Kubernetes** | `kubectl apply -f deploy/kubernetes/terry.yaml` | Clusters |
| **Homebrew** | `brew install terry` | macOS |
| **Source** | `pip install -e .` | Any Python 3.12+ |

### Supported Architectures

| Architecture | Platforms | Status |
|-------------|----------|--------|
| **x86_64 (amd64)** | Intel/AMD servers, cloud VMs | ✅ |
| **aarch64 (arm64)** | Apple Silicon M1-M4, AWS Graviton, Raspberry Pi 5 | ✅ |
| **armv7** | Raspberry Pi 3 | ✅ |

### Mobile Apps

| Platform | Method | Install |
|----------|--------|---------|
| **Android** | PWA → APK via Bubblewrap (TWA) | `bubblewrap build` |
| **iOS** | PWA → Add to Home Screen | Safari → Share → Add |
| **Both** | Telegram Bot | `/start` in Telegram |


## Documentation

- **[INSTALL.md](INSTALL.md)** — Detailed installation for macOS, Linux, Windows
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to contribute tools, skills, or fixes
- **[CHANGELOG.md](CHANGELOG.md)** — What changed in each version
- **[docs/skills/README.md](docs/skills/README.md)** — Creating custom skills
- **[RUNTIME_SECURITY.md](RUNTIME_SECURITY.md)** — Production deployment security features

---

## Contributing

```bash
git clone https://github.com/YOUR_USERNAME/haha_terry.git
git checkout -b feat/my-cool-tool
# Add your tool: subclass BaseTool, add to discover_tools()
pip install -e ".[dev]"
python -m pytest tests/ -v
# Submit a PR!
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Benchmark

4 standard evaluation suites available via `/benchmark`:

| Suite | Description | Status |
|-------|-------------|--------|
| `coding_basics` | File I/O, string manipulation, regex | ✅ |
| `refactoring` | Code restructuring and extraction | ✅ |
| `debugging` | Bug detection and fixing | ✅ |
| `tool_usage` | Tool calling accuracy and efficiency | ✅ |

Run: `terry` → `/benchmark coding_basics`

---

## License

Terry is released under the **MIT License**.

```
Copyright (c) 2026 Terry Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
...
```

Full license text: [LICENSE](LICENSE)

**Attribution:** The name "Terry" and the Terry logo are trademarks of Terry Contributors. All other trademarks are the property of their respective owners.

### Third-Party Licenses

Terry depends on the following open-source packages (all MIT or Apache 2.0):

| Package | License | Usage |
|---------|---------|-------|
| anthropic | MIT | Anthropic Claude SDK |
| openai | Apache 2.0 | OpenAI + compatible providers |
| httpx | BSD | HTTP client |
| rich | MIT | Terminal UI |
| typer | MIT | CLI framework |
| pyyaml | MIT | YAML parsing |
| tiktoken | MIT | Token counting |
| python-dotenv | BSD | Environment loading |

### Contributing

By contributing to Terry, you agree that your contributions will be licensed under the MIT License. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

<p align="center">
  <sub>Built with ❤️ by the Terry community · <a href="#terry-">Back to top ↑</a></sub>
</p>
