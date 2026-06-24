# Terry SDK

The Terry SDK provides a clean, stable Python API for embedding Terry in your own applications.

## Installation

```bash
pip install terry
```

## Quick Start

```python
from terry.sdk import Agent, TerryConfig

# 1. Configure
config = TerryConfig()
config.model.api_key = "sk-ant-..."        # or os.environ["ANTHROPIC_API_KEY"]
config.model.provider = "anthropic"
config.model.model = "claude-sonnet-4-20250514"

# 2. Create agent
agent = Agent(config)

# 3. Run
agent.run("Find where authentication logic is implemented")
```

## Core Classes

### TerryConfig

```python
from terry.sdk import TerryConfig, ModelConfig

config = TerryConfig()

# Model settings
config.model.provider = "anthropic"          # anthropic, openai, deepseek, ollama
config.model.model = "claude-sonnet-4-20250514"
config.model.api_key = "sk-ant-..."
config.model.max_tokens = 128000
config.model.temperature = 0.7

# Context settings
config.max_input_tokens = 1000000

# Effort level
config.effort_level = "high"                 # low, medium, high, xhigh
```

### Agent

```python
from terry.sdk import Agent

agent = Agent(
    config,
    enable_subagents=False,     # Enable multi-agent orchestration
    enable_skills=True,         # Enable skill system
    enable_memory=True,         # Enable persistent memory
    enable_session=True,        # Enable session persistence
)

# Synchronous
response = agent.run("Refactor the user module")

# Get conversation history
messages = agent.messages

# Save session
agent.save_session("my-session")
```

### BaseTool — Custom Tools

```python
from terry.sdk import BaseTool, ToolRegistry

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    risk_level = "safe"
    category = "general"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The query"}
        },
        "required": ["query"]
    }

    def execute(self, query: str) -> str:
        return f"Result for: {query}"

# Register
from terry.sdk import tool_registry
tool_registry.register(MyTool())
```
