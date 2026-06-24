# Terry 🤖

**Your AI Coding Agent — Terminal · Web · Desktop · Mobile**

Terry is an open-source AI coding agent. It reads your codebase, runs commands, edits files, and gets things done — from your terminal, browser, desktop, or phone.

## Quick Start

```bash
# Option 1: Single binary (no Python needed)
curl -fsSL https://github.com/tchangtc/haha_terry/releases/latest/download/install.sh | bash

# Option 2: pip
pip install terry

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start coding
terry
```

## Key Features

| Feature | Description |
|:--|:--|
| **27 Built-in Tools** | bash, read, write, edit, git (7 tools), web search/fetch, grep, glob, notebook, and more |
| **Multi-Interface** | Terminal (CLI + TUI), Web (WebUI), Desktop (tray app), Mobile (PWA + Telegram + Discord) |
| **4-Tier Permissions** | deny/ask/auto modes with fine-grained rules — your code stays safe |
| **4-Layer Context Compaction** | Won't lose track mid-task even with large codebases |
| **Multi-Agent Orchestration** | 6 patterns: fan-out-merge, adversarial verify, tournament, classify-execute, loop-until-done, generate-filter |
| **Multi-Provider** | Anthropic Claude, OpenAI GPT-4o, DeepSeek, Zhipu GLM, Qwen, Ollama (local) |
| **ACP Protocol** | Connect Zed, JetBrains, or any ACP-compatible editor via `terry acp` |
| **OAuth Login** | No API key needed — `terry login` with browser-based OAuth |

## Interfaces

```bash
terry              # Terminal (REPL mode)
terry tui          # Terminal (Textual TUI)
terry webui        # Web interface (http://127.0.0.1:8670)
terry desktop      # Desktop tray app
terry acp          # ACP protocol for editor integration
```

## SDK

Embed Terry in your own applications:

```python
from terry.sdk import Agent, TerryConfig

config = TerryConfig()
config.model.api_key = "sk-ant-..."

agent = Agent(config)
agent.run("Explain the authentication flow in this project")
```

See [SDK documentation](sdk.md) for details.
