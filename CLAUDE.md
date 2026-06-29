# CLAUDE.md — Terry AI Coding Agent

> **Agency comes from the model. Terry is the harness.**
>
> Terry is an AI coding agent supporting Terminal · Web · Desktop · Mobile interfaces.  
>   Version: **v2.7.0** | Python 3.11+ | MIT License | 155 modules | 28 tools | ~32,600 LOC | 47 CLI commands
>
> **v1.0.0**: GA release — stable API, documentation, community governance
> **v0.9.0**: design system, Textual TUI, voice mode, WebUI polish
> **v0.8.0**: Agentic Task Loop, session teleportation, skill marketplace
> **v0.7.0**: workflow scripts, multi-tier subagents, Agent View, ultrareview
> **v0.6.0**: 1M context window, effort levels, auto classifier, /doctor diagnostics
> **v0.5.0**: Interactive Rewind UI, settings hot-reload, background task management, `/goal` autonomous loop.
> **v0.4.0**: Self-evolving agent (SkillAutoCreator), typed tool errors (ToolError hierarchy), composable prompt chunks (PromptComposer), MiniMax provider, CJK-aware token estimation, dynamic provider registration.

---

## Philosophy

Terry is not the brain — it's the **body**. The LLM provides intelligence; Terry provides:

- **Tool execution** (bash, file I/O, web search, git, etc.)
- **Session management** (persist/restore conversation state)
- **Multi-agent orchestration** (subagents, pipelines, map-reduce)
- **Multi-interface delivery** (CLI, WebUI, Desktop, Mobile)
- **Safety guardrails** (permissions, rate limiting, input validation)

When making design decisions, ask: *"Does this make the harness better, or is it trying to out-think the model?"* The answer should guide you toward harness improvements.

---

## Project Architecture

```
haha_terry/
├── terry/                          # Main package
│   ├── __init__.py                  # v0.3.0
│   ├── cli.py                       # CLI entry point (689 lines)
│   ├── cli_commands.py              # CLI command handlers (36 commands in 6 categories)
│   ├── desktop.py                   # Desktop tray app (136 lines)
│   ├── i18n.py                      # Internationalization
│   │
│   ├── core/                        # 🧠 Core engine (98 modules)
│   │   ├── agent.py                 # Main Agent class — the central orchestrator
│   │   ├── harness.py               # HarnessEngine — multi-agent orchestration (8 patterns)
│   │   ├── llm.py                   # LLMClient — model abstraction layer
│   │   ├── config.py                # TerryConfig — configuration management
│   │   ├── session.py               # Session — conversation persistence
│   │   ├── memory.py                # Memory — persistent knowledge storage
│   │   ├── commands.py              # CommandRegistry — slash-command system
│   │   │
│   │   ├── async_llm.py             # AsyncLLMClient — httpx-based true async LLM
│   │   ├── async_agent.py           # AsyncAgent — asyncio event-loop agent
│   │   ├── async_harness.py         # AsyncHarness — async 8-pattern orchestration
│   │   ├── async_subagent.py        # AsyncSubAgentManager — async sub-agents (max 50 concurrent)
│   │   │
│   │   ├── subagent.py              # SubAgent + SubAgentManager + Orchestrator (threaded)
│   │   ├── workflow.py              # WorkflowEngine
│   │   ├── dynamic_workflow.py      # DynamicWorkflowEngine (6 orchestration patterns)
│   │   ├── task_dag.py              # TaskDAG — dependency graph execution
│   │   │
│   │   ├── context_compact.py       # ContextCompactor — 4-layer progressive compression
│   │   ├── agent_hooks.py           # Agent hooks — extension points
│   │   ├── error_recovery.py        # AutoHealer + ErrorRecovery
│   │   ├── permissions.py           # PermissionStore + PermissionLevel
│   │   ├── feedback.py              # Feedback collector (Claude Code-like rating)
│   │   ├── telemetry.py             # Usage telemetry
│   │   ├── metrics.py               # Token/cost tracking
│   │   ├── cache.py                  # LLMCache + ToolCache
│   │   ├── prompt_cache.py          # Anthropic prompt caching helper
│   │   ├── model_router.py          # Multi-model routing
│   │   ├── thinking.py              # Extended thinking support
│   │   │
│   │   ├── planner.py               # Task planning
│   │   ├── spec_exec.py             # Speculative execution
│   │   ├── code_index.py            # Code semantic index
│   │   ├── fts_search.py            # Full-text search
│   │   ├── repomap.py               # Repository map generation
│   │   ├── local_embed.py           # Local embedding
│   │   ├── rag.py                   # Project-level RAG
│   │   ├── knowledge_graph.py       # Code knowledge graph
│   │   │
│   │   ├── skill.py                 # Skill system — dynamic skill loading
│   │   ├── skill_market.py          # Skill marketplace
│   │   ├── curator.py               # SkillsCurator
│   │   ├── suggester.py             # ProactiveSuggester
│   │   ├── autonomous_agent.py      # AutonomousAgent + SkillAutoCreator
│   │   │
│   │   ├── scheduler.py             # CronScheduler
│   │   ├── store.py                 # TerryStore — persistent KV store
│   │   ├── checkpoint.py            # CheckpointManager — undo/redo support
│   │   ├── docker_sandbox.py        # DockerSandbox — container isolation
│   │   ├── memory_sync.py           # MemorySync
│   │   ├── platform_utils.py        # Cross-platform utilities
│   │   │
│   │   ├── security/                # 🔒 Runtime security middleware
│   │   │   └── __init__.py          # RateLimiter, RequestValidator, APIKeyAuth, CORSPolicy, SecurityMiddleware
│   │   ├── ai/                      # AI provider adapters
│   │   ├── infra/                   # Infrastructure utilities
│   │   ├── scheduling/              # Scheduling subsystem
│   │   └── storage/                 # Storage subsystem
│   │
│   ├── tools/                       # 🔧 28 built-in tools
│   │   ├── bash.py, read_file.py, write_file.py, edit_file.py
│   │   ├── grep_tool.py, glob_tool.py, find_tool.py, ls_tool.py
│   │   ├── web_search.py, web_fetch.py
│   │   ├── notebook.py, notes.py, todo_write.py, reminder.py, timer.py
│   │   ├── calculator.py, weather.py, read_image.py
│   │   ├── harness_tool.py          # Harness-as-a-tool for subagent orchestration
│   │   ├── git/                     # Git sub-tools
│   │   └── templates/               # Tool templates
│   │
│   ├── server/                      # 🌐 Server infrastructure
│   │   ├── async_server.py          # Async HTTP server (457 lines)
│   │   └── gateways/                # External platform gateways
│   │       ├── telegram_gateway.py  # Telegram Bot gateway (257 lines)
│   │       └── discord_gateway.py   # Discord Bot gateway (210 lines)
│   │
│   ├── webui/                       # 🖥️ Web interface
│   │   ├── server.py                # WebUI HTTP server (491 lines, SSE streaming)
│   │   └── static/                  # Frontend assets
│   │
│   ├── hooks/                       # 🪝 Hook system
│   │   ├── __init__.py              # HookRegistry (UserPromptSubmit, PreToolUse, PostToolUse, Stop)
│   │   ├── permission.py            # Permission hook
│   │   └── logging_hook.py          # Logging hook
│   │
│   ├── lsp/                         # Language Server Protocol client (227 lines)
│   ├── mcp/                         # Model Context Protocol client (192 lines)
│   └── locale/                      # i18n resources
│
├── skills/                          # 📦 Bundled skills (marketplace)
├── tests/                           # 🧪 26 test files, 926 tests
├── vscode-extension/                # VS Code extension (TypeScript)
├── mobile/                          # Mobile app (TWA + iOS WKWebView)
├── deploy/                          # Deployment guides (containerd, K8s)
├── docs/                            # Internal documentation
├── pyproject.toml                   # Build config (hatchling)
├── Dockerfile                       # Multi-stage container (amd64 + arm64)
├── docker-compose.yml               # Docker Compose (optional Ollama)
├── README.md                        # English README
├── README_zh-CN.md                  # Simplified Chinese README
└── README_zh-TW.md                  # Traditional Chinese README
```

### Six Functional Domains

| Domain | Modules | Responsibility |
|--------|---------|----------------|
| **Agent Core** | `agent.py`, `llm.py`, `config.py`, `session.py`, `memory.py` | Main agent loop, LLM abstraction, state management |
| **Orchestration** | `harness.py`, `subagent.py`, `workflow.py`, `task_dag.py`, async variants | Multi-agent coordination, parallel execution |
| **Intelligence** | `planner.py`, `code_index.py`, `rag.py`, `knowledge_graph.py`, `repomap.py` | Code understanding, planning, search |
| **Safety** | `permissions.py`, `security/`, `checkpoint.py`, `error_recovery.py`, `docker_sandbox.py` | Permission control, runtime security, error recovery |
| **Experience** | `cli.py`, `webui/`, `desktop.py`, `feedback.py`, `skill.py`, `ux.py` | Multi-interface delivery, user experience |
| **Integration** | `lsp/`, `mcp/`, `server/gateways/`, `tools/` | External protocol support, tool execution |

---

## Key Design Decisions

### 1. Async Architecture (v0.2.0)
True async via `httpx.AsyncClient` + `asyncio`, NOT `run_in_executor()` wrapping.  
**Files**: `async_llm.py`, `async_agent.py`, `async_harness.py`, `async_subagent.py`  
**Why**: Enables 100+ concurrent sub-agents with lower memory overhead vs threading.

### 2. CLI Refactoring (884 → 332 lines)
Split `cli.py` into command definition (`cli_commands.py`) + routing (`cli.py`).  
**Pattern**: CommandRegistry with 36 commands in 6 categories (basic, safety, planning, search, workflow, skills).  
**Why**: Single-file CLI was unmaintainable with 48 commands in elif chains.

### 3. Agent.run() Slimmed (→ 99 lines)
Extracted LLM call, compression, and budget logic into separate components.  
Integrated `agent_hooks` for extension points.  
**Why**: Keep the core loop readable and extensible.

### 4. 4-Layer Progressive Context Compression
`Budget → Snip → Micro → Auto`: only compresses as much as needed.  
**Why**: Saves 60%+ compression cost vs one-size-fits-all approaches in large codebases.

### 5. AutoHealer — Self-Healing Engine
Actively detects and fixes tool execution errors before surfacing to the model.  
**Why**: Reduces unnecessary LLM round-trips for common tool failures.

### 6. Security as Middleware, Not Afterthought
RateLimiter (token bucket), RequestValidator (injection detection), APIKeyAuth, CORSPolicy, SecurityMiddleware.  
All in `terry/core/security/__init__.py` (184 lines).  
**Why**: Production users need runtime protection against DDoS, injection, and unauthorized access.

---

## Development Conventions

### Code Style
- **Python 3.11+** — use modern syntax (`str \| None`, `list[dict]`, match/case)
- **Ruff** for linting (E, F, I, N, W, UP rules), line length **120**
- **0 Ruff issues** required before commit
- Type hints on all public APIs (`from __future__ import annotations`)
- Docstrings in Google style for public methods

### Naming
- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Private internals: `_prefix`
- Test files: `test_<feature>.py`
- Test classes: `Test<Feature>`
- Test methods: `test_<specific_behavior>`

### Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/) `<type>: <description>`:

| Prefix | Purpose | Example |
|:--|:--|:--|
| `feat:` | New feature | `feat: add ACP protocol support` |
| `fix:` | Bug fix | `fix: resolve race condition in subagent` |
| `docs:` | Documentation only | `docs: update CLAUDE.md line counts` |
| `style:` | Code style (no logic change) | `style: split multi-statement lines` |
| `refactor:` | Restructure (no fix/feature) | `refactor: extract ToolExecutor class` |
| `test:` | Tests only | `test: add error path assertions` |
| `chore:` | Maintenance / tooling | `chore: bump version to v1.0.3` |

**Rules:**
- Version number in description for version-bump commits (`bump version to vX.Y.Z`)
- `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer on every commit
- Never use generic messages like "Fix a bug" or "Update code"
- Patch version bumps use `chore:`, feature releases use `feat:`, bugfix releases use `fix:`

### Error Handling
- Use `try/except` with specific exception types (never bare `except:`)
- Log errors via `self.logger` (Agent) or `logging.getLogger(__name__)` (standalone modules)
- AutoHealer pattern for recoverable tool errors

### Imports
- `from __future__ import annotations` at top of every file
- Standard lib → third-party → internal (alphabetical within groups)
- Use relative imports within the `terry` package

---

## Common Commands

### Installation & Setup
```bash
pip install -r requirements.txt          # Install dependencies
export ANTHROPIC_API_KEY=sk-ant-...      # Set API key
```

### Running Terry
```bash
terry                                    # Interactive CLI mode
terry webui                              # Start WebUI on port 8670
terry webui --port 9000 --host 0.0.0.0  # WebUI with custom config
terry desktop                            # Desktop tray app
python -m terry.cli                      # Module invocation (alternative)
```

### Development
```bash
pip install -e ".[dev]"                  # Install with dev dependencies
python -m pytest tests/ -q               # Run all tests
python -m pytest tests/ -q --tb=short    # Run with short traceback
python -m pytest tests/test_core_full.py -v  # Run specific test file
ruff check terry/                        # Lint check
ruff check --fix terry/                  # Auto-fix lint issues
```

### Docker
```bash
docker build -t terry .                  # Build image
docker run -it -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -v $(pwd):/app terry  # Run
docker buildx build --platform linux/amd64,linux/arm64 -t terry .  # Multi-arch
```

### Building & Publishing
```bash
pip install hatchling && python -m hatchling build  # Build wheel
```

---

## Testing Strategy

### Test Structure
- **23 test files** under `tests/`, targeting 80%+ coverage
- `test_core_full.py` — Core agent functionality (44 tests)
- `test_comprehensive.py` — Broad integration tests (67 tests)
- `test_coverage.py` — Targeted coverage tests (78 tests)
- `test_80_target.py` — Coverage push tests (63 tests)
- `test_runtime_security.py` — Security component tests (33 tests)
- `test_async.py` — Async module tests (15 tests)
- `test_e2e.py` — End-to-end tests with mock LLM (6 tests)

### Running Tests
```bash
# Full suite
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=terry --cov-report=term-missing

# Specific modules
python -m pytest tests/test_core_full.py -v

# Skip slow tests
python -m pytest tests/ -k "not e2e"
```

### Coverage Blind Spots (needing attention)
| Module | Lines | Status |
|--------|-------|--------|
| `webui/server.py` | 491 | ⚠️ Untested |
| `server/async_server.py` | 457 | ⚠️ Untested |
| `server/gateways/` | 481 | ⚠️ Untested |
| `lsp/__init__.py` | 227 | ⚠️ Untested |
| `mcp/__init__.py` | 192 | ⚠️ Untested |
| `desktop.py` | 136 | ⚠️ Untested |

---

## Key Integration Points

### Adding a New Tool
1. Create `terry/tools/<tool_name>.py`
2. Subclass `BaseTool` with `name`, `description`, `input_schema`, `execute()`
3. Register in `terry/tools/__init__.py`'s `discover_tools()`
4. Add tests in `tests/test_tools_full.py`

### Adding a CLI Command
1. Add handler in `terry/cli_commands.py`
2. Register via `register_cli_command(name, handler, description, category)`
3. Categories: `basic`, `safety`, `planning`, `search`, `workflow`, `skills`

### Adding a Subagent Pattern
1. Add pattern enum to `HarnessPattern` in `harness.py`
2. Implement execution logic in `HarnessEngine.execute()`
3. Add test in `tests/test_core_low_coverage.py`

### Integrating Security Middleware
1. `SecurityMiddleware` is in `terry/core/security/__init__.py`
2. Mounted on all three server request chains (webui/server.py, server/__init__.py, server/async_server.py)

---

## Current Focus (v1.0.0)

- **GA Release**: stable API, `pip install terry`, community governance model, CI/CD pipeline
- **Documentation**: full documentation suite, 3-language README sync, CHANGELOG versioning policy
- **Code Quality**: 0 hardcoded versions (single-source from `__version__`), semver validation in tests
- **Test Suite**: 26 test files, 926 tests, validate.py format checks
- **Security**: runtime security middleware (RateLimiter, RequestValidator, SecurityMiddleware)
- **CLI**: 47 commands across 6 categories

---

## Resources

- **Internal docs**: `docs/` (keep these out of public distribution)
- **Runtime security**: `RUNTIME_SECURITY.md`
- **Install guide**: `INSTALL.md`
- **Changelog**: `CHANGELOG.md`
- **Contributing**: `CONTRIBUTING.md`
- **Build guides**: `deploy/CONTAINERD_GUIDE.md`, `mobile/BUILD_GUIDE.md`
