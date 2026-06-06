# Contributing to Terry

Thank you for your interest in contributing to Terry! This document provides guidelines and information for contributors.

## 🎯 Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## 🚀 How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Use the bug report template
3. Include:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, Terry version)
   - Relevant logs or error messages

### Suggesting Features

1. Check existing issues and discussions
2. Use the feature request template
3. Explain:
   - The problem you're trying to solve
   - Your proposed solution
   - Alternative approaches you considered

### Submitting Code

#### Getting Started

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/YOUR_USERNAME/terry.git
cd terry

# Create virtual environment
uv venv tc_terry
source tc_terry/bin/activate

# Install in development mode
uv pip install -e .

# Install development dependencies
uv pip install pytest ruff mypy
```

#### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the coding style (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests**
   ```bash
   # Run all tests
   python3 test_terry.py
   python3 test_new_features.py

   # Run with pytest (if available)
   pytest
   ```

4. **Check code quality**
   ```bash
   # Linting
   ruff check terry/

   # Type checking
   mypy terry/

   # Formatting
   ruff format terry/
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Adding or updating tests
   - `refactor:` Code refactoring
   - `chore:` Maintenance tasks

6. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a PR on GitHub.

## 📝 Coding Standards

### Python Style

- **Line length**: 100 characters (configured in `pyproject.toml`)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Type hints**: Required for all public functions
- **Docstrings**: Required for all public classes and functions

### Example

```python
from __future__ import annotations

from pathlib import Path


class ExampleTool:
    """A well-documented tool class.

    Attributes:
        name: The tool name.
        description: What the tool does.
    """

    def __init__(self, workdir: Path | None = None) -> None:
        """Initialize the tool.

        Args:
            workdir: Working directory for the tool.
        """
        self.workdir = workdir or Path.cwd()

    def execute(self, param: str) -> str:
        """Execute the tool.

        Args:
            param: Input parameter.

        Returns:
            Result of the execution.

        Raises:
            ValueError: If param is invalid.
        """
        if not param:
            raise ValueError("param cannot be empty")
        return f"Result: {param}"
```

### Adding a New Tool

1. Create `terry/tools/your_tool.py`
2. Inherit from `BaseTool`
3. Implement required methods
4. Register the tool at the end of the file
5. Add import to `terry/tools/__init__.py`

```python
from . import BaseTool, tool_registry


class YourTool(BaseTool):
    name = "your_tool"
    description = "What your tool does"
    input_schema = {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "Parameter description"},
        },
        "required": ["param"],
    }

    def execute(self, param: str) -> str:
        """Execute the tool."""
        return f"Result: {param}"


# Auto-register
tool_registry.register(YourTool())
```

### Adding a New Hook

1. Create `terry/hooks/your_hook.py`
2. Implement the hook function
3. Register in `terry/hooks/__init__.py` or in `agent.py`

```python
def your_hook(block, **kwargs):
    """Hook that runs before tool execution.

    Args:
        block: The tool call block.
        **kwargs: Additional context.

    Returns:
        None to allow, or a string reason to block.
    """
    print(f"Executing: {block.name}")
    return None  # Allow
```

## 🧪 Testing

### Test Structure

- `test_terry.py` - Core functionality tests
- `test_new_features.py` - New feature tests
- `tests/` - Comprehensive test suite (future)

### Writing Tests

```python
def test_your_feature():
    """Test description."""
    # Arrange
    tool = YourTool()

    # Act
    result = tool.execute("test")

    # Assert
    assert "Result" in result
    assert "test" in result
```

### Running Tests

```bash
# Run all tests
python3 test_terry.py
python3 test_new_features.py

# Run specific test
python3 -m pytest tests/test_your_feature.py -v

# Run with coverage
pytest --cov=terry tests/
```

## 📚 Documentation

### Updating README

- Keep examples concise and practical
- Use code blocks with syntax highlighting
- Update feature lists when adding functionality
- Maintain consistent formatting

### Docstrings

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int = 10) -> bool:
    """Brief description.

    Longer description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is invalid.
    """
    pass
```

## 🔒 Security

### Reporting Security Issues

**DO NOT** open a public issue for security vulnerabilities.

Instead, email security concerns to: [SECURITY_EMAIL]

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Best Practices

1. **Never commit secrets** - Use `.env` files (already in `.gitignore`)
2. **Validate all inputs** - Especially in tools that execute commands
3. **Use safe defaults** - Deny by default, allow explicitly
4. **Path validation** - Always check paths stay within workspace
5. **Command sanitization** - Validate and sanitize shell commands

## 🐛 Debugging

### Common Issues

**Issue**: Tests fail after moving directory
```bash
# Recreate virtual environment
rm -rf tc_terry
uv venv tc_terry
source tc_terry/bin/activate
uv pip install -e .
```

**Issue**: Import errors
```bash
# Reinstall Terry
uv pip install -e . --reinstall
```

**Issue**: Permission denied on tools
```bash
# Check sandbox_mode in config
# Set to "ask" for interactive approval
# Set to "auto" for automatic approval (development only)
```

### Debug Mode

```bash
terry --debug
```

This enables:
- Verbose logging
- Stack traces on errors
- Tool execution details

## 📋 Pull Request Checklist

Before submitting your PR:

- [ ] Code follows the style guide
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] No sensitive information (API keys, passwords)
- [ ] Commit messages follow conventional commits
- [ ] PR description clearly explains changes
- [ ] Related issues linked (if any)

## 🎓 Learning Resources

- [Claude Code Documentation](https://github.com/anthropics/claude-code)
- [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## 💬 Getting Help

- **Questions**: Open a discussion on GitHub
- **Bugs**: Open an issue with the bug template
- **Features**: Open an issue with the feature template
- **Security**: Email security concerns privately

## 🙏 Recognition

Contributors will be added to the README and release notes. We appreciate all contributions, big and small!

---

Thank you for contributing to Terry! 🚀
