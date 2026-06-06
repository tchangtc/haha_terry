"""Test new features: grep, web_fetch, todo_write, context compaction, error recovery."""

import sys
from pathlib import Path

# Add project root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from terry.core.config import TerryConfig, ModelConfig
from terry.core.context_compact import ContextCompactor
from terry.core.error_recovery import ErrorRecovery
from terry.tools.grep_tool import GrepTool
from terry.tools.web_fetch import WebFetchTool
from terry.tools.todo_write import TodoWriteTool


def test_grep_tool():
    """Test grep tool functionality."""
    print("1️⃣  Testing grep tool...")
    grep = GrepTool()

    # Test basic grep
    result = grep.execute(pattern="import", path=".")
    assert "import" in result or "No matches" in result
    print("   ✅ Basic grep works")

    # Test case insensitive
    result = grep.execute(pattern="IMPORT", path=".", ignore_case=True)
    assert "import" in result.lower() or "No matches" in result
    print("   ✅ Case-insensitive grep works")

    # Test path escape protection
    result = grep.execute(pattern="test", path="../..")
    assert "Error" in result or "escapes workspace" in result
    print("   ✅ Path escape protection works")


def test_web_fetch_tool():
    """Test web fetch tool functionality."""
    print("\n2️⃣  Testing web_fetch tool...")
    fetch = WebFetchTool()

    # Test localhost blocking
    result = fetch.execute(url="http://localhost:8080")
    assert "Error" in result or "blocked" in result.lower() or "internal" in result.lower()
    print("   ✅ Localhost blocking works")

    # Test invalid URL scheme
    result = fetch.execute(url="ftp://example.com")
    assert "Error" in result or "Invalid URL scheme" in result
    print("   ✅ URL scheme validation works")


def test_todo_write_tool():
    """Test todo_write tool functionality."""
    print("\n3️⃣  Testing todo_write tool...")
    todo = TodoWriteTool()

    # Test creating todos
    todos = [
        {"content": "Write tests", "status": "completed"},
        {"content": "Add features", "status": "in_progress"},
        {"content": "Update docs", "status": "pending"},
    ]
    result = todo.execute(todos=todos)
    assert "Write tests" in result
    assert "Add features" in result
    assert "Update docs" in result
    print("   ✅ Todo creation works")

    # Test invalid status
    invalid_todos = [{"content": "Test", "status": "invalid"}]
    result = todo.execute(todos=invalid_todos)
    assert "Error" in result and "invalid status" in result
    print("   ✅ Status validation works")


def test_context_compactor():
    """Test context compaction functionality."""
    print("\n4️⃣  Testing context compactor...")
    compactor = ContextCompactor(max_tokens=1000, compression_threshold=0.5)

    # Test token estimation
    messages = [{"role": "user", "content": "Hello " * 100}]
    tokens = compactor.estimate_tokens(messages)
    assert tokens > 0
    print(f"   ✅ Token estimation works (estimated {tokens} tokens)")

    # Test compaction trigger
    large_messages = [{"role": "user", "content": "Test " * 500}]
    assert compactor.needs_compaction(large_messages)
    print("   ✅ Compaction trigger works")

    # Test compaction
    messages = [
        {"role": "user", "content": f"Message {i} " * 50}
        for i in range(20)
    ]
    compacted = compactor.compact(messages)
    assert len(compacted) < len(messages)
    print(f"   ✅ Compaction works ({len(messages)} → {len(compacted)} messages)")


def test_error_recovery():
    """Test error recovery functionality."""
    print("\n5️⃣  Testing error recovery...")
    recovery = ErrorRecovery(max_retries=3, base_delay=1.0)

    # Test retryable error detection
    retryable_error = Exception("Rate limit exceeded: 429")
    assert recovery.should_retry(retryable_error, attempt=0)
    print("   ✅ Retryable error detection works")

    # Test non-retryable error
    non_retryable = Exception("Invalid API key")
    assert not recovery.should_retry(non_retryable, attempt=0)
    print("   ✅ Non-retryable error detection works")

    # Test exponential backoff
    delay1 = recovery.get_delay(attempt=0)
    delay2 = recovery.get_delay(attempt=1)
    assert delay2 > delay1
    print(f"   ✅ Exponential backoff works ({delay1}s → {delay2}s)")

    # Test max delay cap
    delay10 = recovery.get_delay(attempt=10)
    assert delay10 <= recovery.max_delay
    print(f"   ✅ Max delay cap works (capped at {delay10}s)")


def test_integration():
    """Test integration of new features."""
    print("\n6️⃣  Testing integration...")

    # Test that all tools are discoverable
    from terry.tools import discover_tools, tool_registry
    discover_tools()
    tools = tool_registry.list_tools()
    tool_names = [t.name for t in tools]

    assert "grep" in tool_names
    print("   ✅ grep tool registered")

    assert "web_fetch" in tool_names
    print("   ✅ web_fetch tool registered")

    assert "todo_write" in tool_names
    print("   ✅ todo_write tool registered")

    # Test that context compactor and error recovery are integrated
    from terry.core.agent import Agent
    config = TerryConfig()
    config.model.api_key = "test-key"
    agent = Agent(config)

    assert hasattr(agent, 'compactor')
    assert isinstance(agent.compactor, ContextCompactor)
    print("   ✅ Context compactor integrated into Agent")

    assert hasattr(agent, 'error_recovery')
    assert isinstance(agent.error_recovery, ErrorRecovery)
    print("   ✅ Error recovery integrated into Agent")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 Testing New Features")
    print("="*70 + "\n")

    try:
        test_grep_tool()
        test_web_fetch_tool()
        test_todo_write_tool()
        test_context_compactor()
        test_error_recovery()
        test_integration()

        print("\n" + "="*70)
        print("🎉 All new feature tests passed!")
        print("="*70)

        print("\n📊 Summary:")
        print("   - grep tool: ✅")
        print("   - web_fetch tool: ✅")
        print("   - todo_write tool: ✅")
        print("   - Context compaction: ✅")
        print("   - Error recovery: ✅")
        print("   - Integration: ✅")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
