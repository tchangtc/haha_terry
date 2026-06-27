# Installation

## Single Binary (Recommended)

No Python or Node.js required. Works on Linux, macOS, and Windows (via WSL/Git Bash).

```bash
curl -fsSL https://github.com/tchangtc/haha_terry/releases/latest/download/install.sh | bash
```

After install:

```bash
terry --version
terry
```

## pip

Requires Python 3.11+.

```bash
pip install terry-agent
```

## From Source

```bash
git clone https://github.com/tchangtc/haha_terry.git
cd haha_terry
pip install -e ".[dev]"
```

## Configuration

Set your API key (at least one provider required):

```bash
# Anthropic (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Or OpenAI
export OPENAI_API_KEY="sk-..."

# Or DeepSeek
export DEEPSEEK_API_KEY="sk-..."
```

Or use OAuth (no API key needed):

```bash
terry login --provider anthropic
```

## Verify

```bash
terry --version
# Terry v1.0.3
```
