# Changelog

All notable changes to Terry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-05

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
- Task dependency graph
- Background task execution
- More tools (browser automation, database queries)
- Plugin system for third-party extensions
- Web UI interface
- MCP protocol support
- Streaming response support
- Async agent loop

---

## Version History

### Versioning Policy

- **Major (X.0.0)**: Breaking changes
- **Minor (0.X.0)**: New features, backward compatible
- **Patch (0.0.X)**: Bug fixes, backward compatible

### Release Notes

For detailed release notes and migration guides, see the [GitHub Releases](https://github.com/terry-ai/terry/releases) page.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to Terry.

## License

Terry is licensed under the MIT License. See [LICENSE](LICENSE) for details.
