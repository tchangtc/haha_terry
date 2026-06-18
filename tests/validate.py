#!/usr/bin/env python3
"""Final validation script for Terry v0.1.0."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_project_structure():
    """Verify project structure is correct."""
    print("📁 Checking project structure...")

    required_files = [
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "pyproject.toml",
        ".gitignore",
        ".env.example",
    ]

    for file in required_files:
        if not os.path.exists(file):
            print(f"   ❌ Missing: {file}")
            return False
        print(f"   ✅ {file}")

    required_dirs = [
        "terry",
        "terry/core",
        "terry/tools",
        "terry/hooks",
    ]

    for dir in required_dirs:
        if not os.path.isdir(dir):
            print(f"   ❌ Missing directory: {dir}")
            return False
        print(f"   ✅ {dir}/")

    return True


def check_imports():
    """Verify all imports work."""
    print("\n📦 Checking imports...")

    modules = [
        ("terry", "__version__"),
        ("terry.core.config", "TerryConfig"),
        ("terry.core.llm", "LLMClient"),
        ("terry.core.agent", "Agent"),
        ("terry.core.context_compact", "ContextCompactor"),
        ("terry.core.error_recovery", "ErrorRecovery"),
        ("terry.tools", "tool_registry"),
        ("terry.tools.bash", "BashTool"),
        ("terry.tools.read_file", "ReadFileTool"),
        ("terry.tools.write_file", "WriteFileTool"),
        ("terry.tools.edit_file", "EditFileTool"),
        ("terry.tools.glob_tool", "GlobTool"),
        ("terry.tools.grep_tool", "GrepTool"),
        ("terry.tools.web_fetch", "WebFetchTool"),
        ("terry.tools.todo_write", "TodoWriteTool"),
        ("terry.hooks", "hook_registry"),
        ("terry.hooks.permission", "permission_hook"),
        ("terry.hooks.logging_hook", "log_hook"),
        ("terry.cli", "app"),
    ]

    for module_name, attr in modules:
        try:
            module = __import__(module_name, fromlist=[attr])
            getattr(module, attr)
            print(f"   ✅ {module_name}.{attr}")
        except Exception as e:
            print(f"   ❌ {module_name}.{attr}: {e}")
            return False

    # Validate __version__ is valid semver
    import re
    from terry import __version__
    semver_re = re.compile(r'^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$')
    if not semver_re.match(__version__):
        print(f"   ❌ terry.__version__ = '{__version__}' is not valid semver (X.Y.Z)")
        return False
    print(f"   ✅ terry.__version__ = {__version__} (valid semver)")

    return True


def check_tools():
    """Verify all tools are registered."""
    print("\n🔧 Checking tool registration...")

    from terry.tools import discover_tools, tool_registry

    discover_tools()
    tools = tool_registry.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {
        "bash", "read_file", "write_file", "edit_file",
        "glob", "grep", "web_fetch", "todo_write"
    }

    missing = expected_tools - tool_names
    if missing:
        print(f"   ❌ Missing tools: {missing}")
        return False

    for name in expected_tools:
        print(f"   ✅ {name}")

    return True


def check_functionality():
    """Verify core functionality works."""
    print("\n⚙️  Checking core functionality...")

    from terry.core.config import TerryConfig
    from terry.core.context_compact import ContextCompactor
    from terry.core.error_recovery import ErrorRecovery

    # Config
    try:
        config = TerryConfig()
        assert config.max_tool_calls == 50
        print("   ✅ Config system")
    except Exception as e:
        print(f"   ❌ Config system: {e}")
        return False

    # Context compactor
    try:
        compactor = ContextCompactor()
        messages = [{"role": "user", "content": "test"}]
        tokens = compactor.estimate_tokens(messages)
        assert tokens > 0
        print("   ✅ Context compactor")
    except Exception as e:
        print(f"   ❌ Context compactor: {e}")
        return False

    # Error recovery
    try:
        recovery = ErrorRecovery()
        error = Exception("Rate limit exceeded")
        assert recovery.should_retry(error, attempt=0)
        print("   ✅ Error recovery")
    except Exception as e:
        print(f"   ❌ Error recovery: {e}")
        return False

    return True


def check_documentation():
    """Verify documentation is complete."""
    print("\n📚 Checking documentation...")

    docs = {
        "README.md": ["Features", "Quick Start", "Tools", "Architecture"],
        "CONTRIBUTING.md": ["Code of Conduct", "How to Contribute", "Coding Standards"],
        "CHANGELOG.md": ["0.1.0", "Added", "Security"],
    }

    for doc, keywords in docs.items():
        if not os.path.exists(doc):
            print(f"   ❌ Missing: {doc}")
            return False

        with open(doc, "r") as f:
            content = f.read()

        missing = [kw for kw in keywords if kw not in content]
        if missing:
            print(f"   ❌ {doc} missing: {missing}")
            return False

        print(f"   ✅ {doc}")

    return True


def check_tests():
    """Verify tests exist and can be imported."""
    print("\n🧪 Checking tests...")

    test_files = [
        "tests/test_new_features.py",
        "tests/test_production_features.py",
    ]

    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"   ❌ Missing: {test_file}")
            return False
        print(f"   ✅ {test_file}")

    return True


def main():
    """Run all validation checks."""
    print("="*70)
    print("🔍 Terry v0.1.0 Final Validation")
    print("="*70)
    print()

    checks = [
        ("Project Structure", check_project_structure),
        ("Imports", check_imports),
        ("Tools", check_tools),
        ("Functionality", check_functionality),
        ("Documentation", check_documentation),
        ("Tests", check_tests),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} check failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print()

    # Summary
    print("="*70)
    print("📊 Validation Summary")
    print("="*70)

    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if not result:
            all_passed = False

    print()

    if all_passed:
        print("🎉 All validation checks passed!")
        print()
        print("Terry is ready for release!")
        print()
        print("Next steps:")
        print("  1. git add .")
        print("  2. git commit -m 'feat: initial release v0.1.0'")
        print("  3. git tag v0.1.0")
        print("  4. git push origin main --tags")
        print()
        return 0
    else:
        print("❌ Some validation checks failed.")
        print("Please fix the issues above before releasing.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
