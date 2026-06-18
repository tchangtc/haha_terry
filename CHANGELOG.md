# Changelog

All notable changes to Terry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-06-18

### Fixed
- 22 silent `pass` FIXMEs resolved — all except blocks now log warnings via `logging.getLogger(__name__)`
  - `checkpoint.py` (7), `dynamic_workflow.py` (5), `memory.py` (2), `error_recovery.py` (3), `subagent.py` (3), `async_subagent.py` (1), `llm.py` (1)
- `error_recovery.py`: removed dangerous "Retry with sudo" healing pattern
- `config.py`: `_from_dict()` fallback `max_tokens` corrected 8000→128000 (matched dataclass default)
- `tools/__init__.py`: registered 2 unregistered tools (`slash_command`, `task_update`)
- `requirements.txt`: added missing `textual>=0.52.0` dependency
- `pyproject.toml`: added `[project.optional-dependencies] server = ["fastapi", "uvicorn"]`

### Documentation
- `CLAUDE.md`: corrected stale line counts (cli.py 332→689, webui/server.py 360→491, async_server.py 382→457, mcp 180→191)
- `CLAUDE.md`: fixed Python version claim (3.12+→3.11+), tool count in tree (26→29)
- `CLAUDE.md`: updated coverage blind spot line counts
- `requirements.txt`: version comment v1.0.0→v1.0.1

## [1.0.1] - 2026-06-18

### Fixed
- 4 hardcoded version references eliminated, unified to single-source `__version__`
  - `terry/tui/app.py`: `v0.9.0` → `import terry; terry.__version__`
  - `tests/test_coverage.py`: `"0.5.0"` → `__version__`
  - `tests/test_new_modules.py`: `== "0.9.0"` → semver regex
  - `terry/core/swe_bench.py`: `"v0.5.0"` → `f"v{__version__}"`
- `test_version()`: semver regex supporting pre-release/build suffixes (was `isdigit()`)
- `validate.py`: added `__version__` format validation
- `pyproject.toml`: Development Status classifier 3 (Alpha) → 5 (Production/Stable)
- `terry/tui/__init__.py`: added missing `from __future__ import annotations`

### Documentation
- `CHANGELOG.md`: added missing `[1.0.0]` section, filled empty `[0.6.0]` (30 lines), corrected v0.1.0/v0.9.0 dates to match git tags
- `CLAUDE.md`: corrected stale statistics (tools 27→29, CLI 32→36, tests 22→23, updated Current Focus)
- `CHANGELOG.md`: codified commit message convention (version number in every commit)

## [1.0.0] - 2026-06-18

### Added

#### GA Release
- Stable public API with semantic versioning policy (Major.Minor.Patch)
- `pip install terry` distribution via PyPI
- CI/CD pipeline (GitHub Actions): lint, test (3.11/3.12), security scan, build
- Community governance model (CONTRIBUTING.md, Code of Conduct)
- PyPI classifier: Production/Stable (upgraded from Alpha)

#### Single-Source Version
- All version references unified to single `__version__` in `terry/__init__.py`
- Zero hardcoded version strings in codebase (eliminated 4 instances: TUI, tests, SWE-bench)
- Semver validation in `test_version()` with regex supporting pre-release/build suffixes
- `validate.py` now asserts `__version__` format is valid semver

#### Documentation
- Full three-language README sync (EN, 简体中文, 繁體中文)
- CHANGELOG.md versioning policy codified (Major/Minor/Patch per semver.org)
- RUNTIME_SECURITY.md updated for v1.0.0
- CLAUDE.md stats updated: 29 tools, 36 CLI commands, 23 test files

### Changed
- Modules: 124 → 127 | CLI: 32 → 36 | Tools: 27 → 29 | Tests: 22 → 23
- `pyproject.toml`: Development Status classifier 3 (Alpha) → 5 (Production/Stable)
- `terry/tui/app.py`: hardcoded `v0.9.0` → `import terry; terry.__version__`
- Model limits: `max_tokens` 8K → 128K, `max_input_tokens` 200K → 1M

### Fixed
- 4 hardcoded version strings eliminated (TUI header, test_coverage, test_new_modules, swe_bench)
- Test assertions made version-independent (semantic check instead of exact match)
- All Python files now have `from __future__ import annotations` (127/127)
- VSCode extension settings: version constraints updated for v1.0.0
- CI test matrix: Python 3.11 + 3.12 compatibility verified

## [0.9.0] - 2026-06-17

### Added
- Terry Design System: unified color palette across CLI, TUI, and WebUI
- Textual TUI: multi-panel terminal interface with Vim keybindings
- Voice Mode: Web Speech API integration with microphone button
- WebUI: code syntax highlighting, message animations, unified theme

## [0.8.0] - 2026-06-16

### Added

#### Agentic Task Loop
- TaskManager: unified plan execution with automatic progress tracking
- task_update tool: LLM can mark tasks as completed/in_progress/failed
- System prompt injection shows active plan progress
- ProgressDisplay shows task completion bar in CLI
- /plan auto-creates structured task lists from Planner output

#### Session Teleportation
- teleport.py: export sessions to portable .tar.gz archives
- /teleport export|import commands for cross-machine session migration
- api_key excluded from exports for security

#### Skill Marketplace
- skill_registry.py: community skill discovery from remote index
- /skill-market search|install|update|list commands

#### Slash Command Tool
- slash_command.py: LLM can invoke registered CLI commands
- Safety filter blocks /exit, /mode, /bash from LLM access

#### Routines — Conditional Triggers
- TriggerType enum: cron, webhook, api, conditional
- handle_webhook() and schedule_conditional() methods

### Changed
- Modules: 119 → 124 | CLI: 32 → 36 | LOC: ~25.3K → ~26.4K

## [0.7.0] - 2026-06-12

### Added

#### Dynamic Workflow Script Engine (inspired by Claude Code v2.1.154)
- WorkflowScript Python DSL: fluent chainable API (fan_out, verify, tournament, etc.)
- Wraps 6 existing DynamicWorkflowEngine patterns
- /workflow CLI: load and execute user-written orchestration scripts

#### Multi-tier Subagents (inspired by Claude Code v2.1.172)
- SubAgent and AsyncSubAgent: depth, parent_id, children tracking
- spawn_child(): recursive sub-agent spawning with max_depth=5 guard
- BackgroundTask: parent_id and depth fields for tree visualization
- /agents --tree CLI: hierarchical agent tree view

#### Agent View Dashboard (inspired by Claude Code v2.1.139)
- agents.html: dark-themed dashboard with 3s polling
- /api/agents REST endpoint: structured agent list with status
- /agents CLI: table view of all running agents

#### Ultrareview — Adversarial Code Review (inspired by Claude Code v2.1.113)
- ultrareview.py: 4-dimension review (correctness, security, performance, maintainability)
- 3-vote adversarial verification per finding (2/3 majority required)
- Auto-fix loop: fix → re-review until all dimensions pass
- /ultrareview CLI command

#### Routines — Webhook + API Triggers
- CronScheduler.trigger_api(): programmatic routine triggering
- /api/routines REST endpoint: list configured routines
- /routine CLI: list, add, trigger, remove routines

### Changed
- Version: 0.6.0 → 0.7.0
- Modules: 117 → 119 | LOC: ~25K → ~25.3K | CLI: 28 → 32

## [0.6.0] - 2026-06-11

### Added

#### Context Window Expansion (inspired by Claude Code v2.1.x)
- `max_input_tokens`: 200K → 1M (5x improvement)
- `compression_threshold`: 0.75 → 0.85, delays compaction on large codebases
- `model.max_tokens`: 8K → 64K (8x improvement)
- Fallback values updated across config, context_compact, thinking

#### Effort Level System
- `EFFORT_CONFIG` mapping: low / medium / high / xhigh with model + thinking + max_tokens per level
- `Agent.set_effort()`: runtime effort changes without config reload
- `/effort` CLI command with validation and rich output

#### Auto Mode Smart Classifier
- `auto_classifier.py` (158 lines): heuristic trust scoring for permission decisions
- Dimensions: tool risk weight, danger keywords, path safety, session memory
- Integrated into permission_hook between deny list and destructive gate

#### /doctor Diagnostic Command
- `doctor.py` (217 lines): 7-dimension health check
- Rich table output with pass / warn / fail color coding
- `/doctor` CLI command
- Dimensions: API key, Python version, dependencies, config, tools, disk, network

#### Skill System Upgrade
- `SkillWatcher`: polling-based hot reload (3s interval)
- `reload_skills` alias fix (was broken in v0.5.0)
- `/reload-skills` CLI command

### Changed
- Version: 0.5.0 → 0.6.0
- Modules: 115 → 117 | LOC: ~24.5K → ~25K | CLI: 25 → 28

## [0.5.0] - 2026-06-11

### Added

#### Interactive Rewind UI (inspired by Claude Code v2.0.0 Checkpoints)
- **Checkpoint browser**: `/checkpoints` renders a rich table with colored method indicators (git=green, tar=yellow)
- **Selective restore**: `/undo [<id>]` restores specific checkpoints with diff preview + confirmation prompt
- **New CheckpointManager methods**: `get_checkpoint()`, `delete_checkpoint()`, `diff_preview()` (git `--stat` dry-run)
- **Subcommands**: `/checkpoints diff <id>`, `/checkpoints delete <id>`

#### Settings Hot-Reload (inspired by Claude Code v1.0.90)
- **ConfigWatcher**: Polling-based file monitor (2s interval, zero dependencies), detects mtime changes
- **TerryConfig.reload()**: Reads config from disk, deep-compares fields, validates before applying, returns changed field list
- **Agent.reconfigure()**: Pushes config changes to subsystems — LLMClient (model/temperature), ContextCompactor (thresholds), sandbox mode — via per-class `reconfigure()` methods
- **`/config reload` CLI**: Shows diff table (Setting | Status), flags fields needing restart
- **evaluator_model field**: New config field for GoalLoop evaluator model (empty = reuse main model)

#### Background Task Management (inspired by Claude Code v1.0.71 + v2.1.139)
- **BackgroundTaskRegistry**: Thread-safe singleton (RLock) tracking all parallel execution across SubAgentManager, AsyncSubAgentManager, HarnessEngine, DynamicWorkflowEngine
- **Integrated registration**: `background_registry.register()` called automatically in `SubAgentManager.spawn()` and `AsyncSubAgentManager.spawn()`
- **`/bg <description>`**: Fire-and-forget a background task via AutonomousAgent
- **`/tasks list [status]`**: Rich table showing ID, description, system, status (color-coded), creation time
- **`/tasks peek <id>`**: Panel display of task result/error for running tasks
- **`/tasks cancel <id>`**: Mark task as cancelled
- **`/tasks dag`**: Legacy TaskDAG view preserved
- **WebUI endpoint**: `GET /api/tasks[?status=running]` returns JSON array via `BackgroundTask.to_dict()`

#### /goal — Goal-Driven Autonomous Loop (inspired by Claude Code v2.1.139)
- **GoalLoop class**: Dual-model architecture — main agent generates/refines, configurable evaluator model scores progress
- **Loop pattern**: parse_criteria → generate → evaluate → refine → repeat until score ≥ 0.85 or max 10 iterations
- **Evaluator prompt**: Structured JSON output (`{met, score, feedback, missing}`) with detailed scoring guide
- **Agent.run_goal()**: Creates GoalLoop with optional evaluator model from `config.evaluator_model`
- **`/goal <description>`**: CLI entry point with usage examples, status spinner, result Panel (iterations/score/feedback)

### Changed
- CLI commands: 23 → 26 (added `/bg`, `/goal`; upgraded `/undo`, `/checkpoints`, `/tasks`, `/config reload`)
- `_cmd_tasks` redirected to BackgroundTaskRegistry; old TaskDAG preserved under `/tasks dag`

## [0.4.0] - 2026-06-09

### Added

#### Self-Evolving Agent (inspired by hermes-agent)
- **SkillAutoCreator**: Analyzes complex conversation trajectories and auto-generates reusable `SKILL.md` files with YAML frontmatter. Triggers when tool calls exceed threshold (default: 5). Includes LLM-powered extraction with heuristic fallback.
- **Prompt Composer**: Refactored monolithic `build_system_prompt()` into 7 composable `PromptChunk` classes with chain-of-use API. Supports runtime enable/disable via `composer.disable("MemoryChunk")`.
- **Nudge mechanism**: System prompt reminds agent to persist useful knowledge to memory across sessions.

#### Tool System Upgrade (inspired by opencode)
- **Typed tool errors**: New `ToolError` hierarchy (`InvalidArgumentsError`, `ExecutionError`, `PermissionDeniedError`, `RateLimitError`, `TimeoutError`) that auto-generates LLM-friendly messages for self-correction.
- **Tool metadata**: `BaseTool` now has `category`, `risk_level`, and `requires_approval` attributes for permission auto-decision.

#### Provider Flexibility (inspired by merco)
- **MiniMax provider**: Added built-in support for MiniMax models (SWE-bench #1).
- **Dynamic provider registration**: `~/.terry/config.json` now supports user-defined providers via `load_providers_from_config()`. Existing `register_provider()` API for runtime registration.
- **CJK-aware token estimation**: `get_token_count()` applies correction factor (up to 1.5×) for Chinese/Japanese/Korean text.

#### Code Quality
- **Annotation coverage**: 106/106 files now have `from __future__ import annotations` (100%).
- **Print→logging migration**: 6 non-CLI modules converted from `print()` to proper `logging.getLogger(__name__)`.
- **Agent decomposition**: `ToolExecutor` (212 lines) and `ResponseHandler` (89 lines) extracted from `agent.py` (928→798 lines).

### Changed
- Default model: `claude-sonnet-4-20250514` → `claude-sonnet-4-6-20250922`
- `core/__init__.py`: populated from 0 bytes with package documentation
- `git_branch` + `git_merge`: registered in `tools/git/__init__.py`
- Agent loop: `SkillAutoCreator.maybe_create()` fires after task completion

### Fixed
- `anthropic` SDK installed (v0.107.1) — was missing in development environment
- 2 git tools (branch/merge) were unregistered despite having implementation files
- Empty `core/__init__.py` (0 bytes) now properly documents the core package
- Memory nudge: agent now periodically reminded to persist knowledge

## [0.3.0] - 2026-06-07

### Fixed
- Version consistency: all version strings updated to 0.3.0 across 15 locations
- Ruff lint: 43 lint errors resolved (0 remaining in terry/ package)
- Documentation: accurate module counts, line counts, security middleware status
- Dockerfile: added missing tiktoken to fallback install, removed unused uv.lock copy
- Python requirement: lowered from >=3.12 to >=3.11 (matches actual StrEnum usage)
- Code bugs: missing Callable import, deprecated asyncio.TimeoutError, unused variable
- VSCode extension: version bump to 0.3.0
- Environment: added missing environment variables to .env.example

## [0.2.0] - 2026-06-06

### Added

#### Multi-Interface Support
- **WebUI**: Full chat interface with dark theme, SSE streaming, session management, PWA support
- **Desktop**: System tray app (macOS/Windows/Linux) with browser auto-launch
- **Mobile**: PWA manifest + service worker for offline access
- **Telegram Gateway**: HTTP long-polling bot with command support
- **Discord Gateway**: REST API polling bot with @mention trigger

#### Tools (24 total, +8 from v0.1.0)
- **Git Workflow (5)**: git_diff, git_commit, git_log, git_status, git_checkout
- **MultiEdit**: Atomic multi-location file editing with rollback
- **NotebookEdit**: Jupyter .ipynb cell-level editing (replace/insert/delete)
- **ReadImage**: PNG/JPG/GIF/WebP/PDF reading with base64 encoding
- **Harness Tool**: 8-pattern multi-agent orchestration exposed as a tool

#### Security
- **4-Level Permission System**: low/medium/high/critical with persistent rule store
- **Checkpoint System**: File snapshots (git-aware + tar-based) with `/undo` support
- **Enhanced Permission Hook**: Integration with PermissionStore for allow/deny/ask rules

#### Orchestration & Autonomy
- **Dynamic Workflow Engine**: 6 patterns (fan-out-merge, adversarial-verify, tournament, classify-execute, loop-until-done, generate-filter)
- **Harness Engine**: Unified orchestration layer with 8 patterns, token budget tracking, checkpoint/resume
- **Autonomous Agent**: Background clone→analyze→fix→test→commit→PR pipeline
- **Skill Auto-Creator**: Pattern detection from conversations → auto-generate SKILL.md files
- **Skills Curator**: 7-day autonomous skill library assessment and pruning

#### Core Engine Improvements
- **AutoHealer**: Automatic detection and fixing of common tool errors (command not found, missing modules)
- **Precise Token Counting**: tiktoken integration replacing heuristic chars//4 estimation
- **Structured Memory**: 5 memory types (user/feedback/project/reference/note) with [[wiki-link]] cross-references
- **Plan-First Mode**: LLM-generated structured execution plans with user approval
- **Model Router**: Task complexity-based routing to cheap/powerful models
- **Feedback Collector**: Non-blocking user rating (thumbs up/down) with 15% sampling

#### Integration & Platform
- **MCP Client**: Model Context Protocol support (stdio + SSE transports)
- **LSP Client**: Language Server Protocol (diagnostics, hover, go-to-definition)
- **Cross-Platform Memory Sync**: JSON export/import + cloud sync stubs
- **FTS5 Conversation Search**: SQLite full-text search across all sessions
- **Benchmark Framework**: 4 evaluation suites + SWE-bench-style scoring system
- **VS Code Extension**: 6 commands (chat, explain, fix, review, generate tests, start server)

#### Developer Experience
- **@mention Syntax**: @file, @symbol, @git context injection
- **Conversation Fork**: Branch conversations to explore alternatives
- **Streaming Response**: Real-time token-by-token output in CLI and WebUI
- **Tab Completion**: readline-based command completion for all 45+ commands
- **Proactive Suggestions**: Context-aware next-action recommendations
- **Speculative Execution**: Background file pre-fetching during tool execution

### Changed
- Tools: 16 → 24 (+8)
- Core modules: 12 → 45 (+33)
- CLI commands: 19 → 48+
- Tests: 13 → 118
- Security levels: 3 (deny/ask/auto) → 4 (low/medium/high/critical)
- LLM providers: 4 → 6+ (added Zhipu GLM, Qwen, custom adapters)
- README: Three-language support (EN/zh-CN/zh-TW)

## [0.1.0] - 2026-06-06

### Added

#### Core Features
- **Agent Loop**: ReAct pattern implementation with tool budget and hallucination filtering
- **Multi-Provider Support**: Anthropic, OpenAI, DeepSeek, and OpenAI-compatible APIs
- **Interactive CLI**: Rich terminal interface with slash commands
- **Skills System**: Dynamic skill loading and matching (Anthropic-style)
  - Automatic skill matching based on user intent
  - Manual skill activation/deactivation
  - Hot-reload skills from disk
  - Built-in skills: code-review, data-analysis, document-generator

#### Tools (16 total)

**Development Tools:**
- `bash`: Shell command execution with security controls
- `read_file`: File reading with line limits
- `write_file`: File creation and overwriting
- `edit_file`: SEARCH/REPLACE editing with diff preview
- `glob`: File pattern matching
- `grep`: Content search with regex support
- `find`: Search for files by name or pattern
- `ls`: List directory contents

**Web & Data Tools:**
- `web_fetch`: URL content fetching with security controls
- `web_search`: Search the web (API key required)

**Productivity Tools:**
- `todo_write`: Task list management
- `reminder`: Set and manage reminders
- `notes`: Quick note taking
- `timer`: Timer and Pomodoro sessions

**Utility Tools:**
- `calculator`: Mathematical calculations
- `weather`: Weather information

#### Security
- **3-Gate Permission System**:
  - Gate 1: Hard deny list (always blocked commands)
  - Gate 2: Destructive pattern detection (requires confirmation)
  - Gate 3: Path escape prevention (workspace boundary enforcement)
- Path validation for all file operations
- Localhost and private IP blocking for web_fetch

#### Architecture
- **Hook System**: Event-based extension points
  - `PreToolUse`: Run before tool execution
  - `PostToolUse`: Run after tool execution
  - `Stop`: Run when agent loop ends
  - `UserPromptSubmit`: Run when user submits input
- **Auto-Discovery**: Tools and hooks self-register on import
- **Tool Registry**: Central management of all available tools

#### Context Management
- **Context Compaction**: Automatic conversation history management
  - Token estimation
  - Intelligent message summarization
  - Configurable compression threshold
- **Error Recovery**: Robust error handling
  - Exponential backoff for retries
  - Retryable error detection (rate limits, timeouts)
  - Context trimming on length errors

#### Configuration
- Multi-level configuration (global, project, CLI)
- Provider registry for easy LLM integration
- JSON-based configuration files
- Environment variable support

#### Production Features
- **Memory System**: Persistent cross-session knowledge storage with YAML frontmatter
- **Session Management**: Save and restore conversation state
- **Subagent System**: Spawn parallel agents for complex task decomposition
- **Metrics Collection**: Track usage, performance, and costs across providers
- **Caching System**: LLM response and tool result caching to reduce API costs
- **Structured Logging**: JSON and colored console output with log rotation

#### Documentation
- Comprehensive README with examples (3 languages: EN/简体中文/繁體中文)
- Quick start guide
- Development report
- Contributing guidelines
- MIT License

### Security

- Implemented 3-gate permission system from day one
- Path escape protection for all file operations
- Command deny list for dangerous operations
- Localhost blocking for web requests
- Workspace boundary enforcement

### Performance

- Token-aware context management
- Automatic context compaction to prevent overflow
- Efficient tool result handling
- Streaming support for LLM responses

### Developer Experience

- Rich terminal output with colors and formatting
- Debug mode with verbose logging
- Comprehensive test suite
- Type hints throughout codebase
- Auto-discovery for easy extension

## [Unreleased]

### Planned
- Coverage push: test webui/server.py (428 lines), server/async_server.py (439 lines), server/gateways/ (475 lines)
- Reduce 232 broad `except Exception` catches to specific exception types
- Address 21 FIXME markers (module-level logger) across checkpoint, dynamic_workflow, error_recovery
- Plugin system for third-party extensions
- Browser automation and database query tools
- Comprehensive end-to-end tests with mock LLM responses

---

## Version History

### Versioning Policy

- **Major (X.0.0)**: Breaking changes
- **Minor (0.X.0)**: New features, backward compatible
- **Patch (0.0.X)**: Bug fixes, backward compatible

### Commit Message Convention (v1.0.0+)

Every commit message must include the version number:
```
<type>: vX.Y.Z: <description>


```
Types: `fix:` (patch), `feat:` (minor), `BREAKING:` (major). Examples:
```
fix: v1.0.1: replace hardcoded versions, semver validation
feat: v1.1.0: add new browser automation tool
```
Always bump version numbers before committing. Organize and review all changes before commit & push.

### README News Policy

- **Minor (0.X.0) + Major (X.0.0)**: Update all three READMEs' News sections with a new entry.
- **Patch (0.0.X)**: Do NOT update README News — bug fixes and doc cleanup are invisible to end users. CHANGELOG.md is the authoritative record.

### Release Notes

For detailed release notes and migration guides, see the [GitHub Releases](https://github.com/terry-ai/terry/releases) page.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to Terry.

## License

Terry is licensed under the MIT License. See [LICENSE](LICENSE) for details.
