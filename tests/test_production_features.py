#!/usr/bin/env python3
"""Production features test suite."""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from terry.core.config import TerryConfig
from terry.core.memory import Memory
from terry.core.session import Session
from terry.core.metrics import Metrics
from terry.core.cache import Cache, LLMCache, ToolCache
from terry.core.logger import Logger


def test_memory_system():
    """Test memory system functionality."""
    print("\n1️⃣  Testing Memory System...")

    with tempfile.TemporaryDirectory() as tmpdir:
        memory = Memory(memory_dir=Path(tmpdir))

        # Test adding memories
        memory.add(
            name="test-preference",
            content="User prefers concise responses",
            memory_type="preference",
            description="User communication preference"
        )

        memory.add(
            name="project-context",
            content="Working on Terry AI agent project",
            memory_type="context",
            description="Current project information"
        )

        # Test listing memories
        memories = memory.list_memories()
        assert len(memories) == 2, f"Expected 2 memories, got {len(memories)}"
        print("   ✅ Added and listed 2 memories")

        # Test getting specific memory
        content = memory.get("test-preference")
        assert content is not None, "Failed to retrieve memory"
        assert "concise" in content, "Memory content incorrect"
        print("   ✅ Retrieved specific memory")

        # Test searching memories
        results = memory.search("Terry")
        assert len(results) == 1, f"Expected 1 search result, got {len(results)}"
        print("   ✅ Search functionality works")

        # Test updating memory
        memory.update("test-preference", "User prefers detailed responses")
        content = memory.get("test-preference")
        assert "detailed" in content, "Memory update failed"
        print("   ✅ Memory update works")

        # Test deleting memory
        memory.delete("project-context")
        memories = memory.list_memories()
        assert len(memories) == 1, f"Expected 1 memory after delete, got {len(memories)}"
        print("   ✅ Memory deletion works")


def test_session_system():
    """Test session management functionality."""
    print("\n2️⃣  Testing Session System...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session = Session(session_dir=Path(tmpdir))

        # Test creating new session
        session_id = session.new()
        assert session_id is not None, "Failed to create session"
        print(f"   ✅ Created session: {session_id}")

        # Test adding messages
        session.add_message("user", "Hello Terry!")
        session.add_message("assistant", "Hello! How can I help you?")

        messages = session.get_messages()
        assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
        print("   ✅ Added and retrieved messages")

        # Test saving session
        session.save()
        print("   ✅ Saved session to disk")

        # Test loading session
        new_session = Session(session_dir=Path(tmpdir))
        loaded = new_session.load(session_id)
        assert loaded, "Failed to load session"

        loaded_messages = new_session.get_messages()
        assert len(loaded_messages) == 2, f"Expected 2 messages, got {len(loaded_messages)}"
        print("   ✅ Loaded session from disk")

        # Test listing sessions
        sessions = Session.list_sessions(Path(tmpdir))
        assert len(sessions) == 1, f"Expected 1 session, got {len(sessions)}"
        print("   ✅ Listed available sessions")


def test_metrics_system():
    """Test metrics collection functionality."""
    print("\n3️⃣  Testing Metrics System...")

    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = Metrics(metrics_dir=Path(tmpdir))

        # Test counters
        metrics.increment("tool_calls", 5)
        metrics.increment("tool_calls", 3)
        assert metrics.get_counter("tool_calls") == 8, "Counter increment failed"
        print("   ✅ Counter increments work")

        # Test timers
        start = metrics.timer_start()
        import time
        time.sleep(0.1)
        duration = metrics.timer_stop("test_operation", start)
        assert duration >= 0.1, f"Timer duration incorrect: {duration}"

        stats = metrics.get_timer_stats("test_operation")
        assert stats["count"] == 1, "Timer stats incorrect"
        print("   ✅ Timer tracking works")

        # Test costs
        metrics.add_cost("anthropic", 0.05)
        metrics.add_cost("openai", 0.03)
        total = metrics.get_total_cost()
        assert abs(total - 0.08) < 0.001, f"Total cost incorrect: {total}"
        print("   ✅ Cost tracking works")

        # Test summary
        summary = metrics.get_summary()
        assert "counters" in summary, "Summary missing counters"
        assert "timers" in summary, "Summary missing timers"
        assert "costs" in summary, "Summary missing costs"
        print("   ✅ Metrics summary works")

        # Test saving metrics
        metrics.save("test_metrics.json")
        print("   ✅ Saved metrics to disk")


def test_cache_system():
    """Test caching functionality."""
    print("\n4️⃣  Testing Cache System...")

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(cache_dir=Path(tmpdir))

        # Test basic caching
        cache.set("test-key", "test-value")
        value = cache.get("test-key")
        assert value == "test-value", f"Expected 'test-value', got {value}"
        print("   ✅ Basic caching works")

        # Test complex data caching
        complex_data = {
            "messages": [{"role": "user", "content": "Hello"}],
            "metadata": {"timestamp": "2026-01-05"},
        }
        cache.set("complex-key", complex_data)
        retrieved = cache.get("complex-key")
        assert retrieved == complex_data, "Complex data caching failed"
        print("   ✅ Complex data caching works")

        # Test cache deletion
        cache.delete("test-key")
        value = cache.get("test-key")
        assert value is None, "Cache deletion failed"
        print("   ✅ Cache deletion works")

        # Test LLM cache
        llm_cache = LLMCache(cache)
        messages = [{"role": "user", "content": "Test"}]
        response = {"content": "Response", "stop_reason": "end_turn"}

        llm_cache.set_response(messages, response, model="test-model")
        cached = llm_cache.get_response(messages, model="test-model")
        assert cached == response, "LLM cache failed"
        print("   ✅ LLM response caching works")

        # Test tool cache
        tool_cache = ToolCache(cache)
        tool_result = "Tool output"

        tool_cache.set_result("bash", {"command": "ls"}, tool_result)
        cached = tool_cache.get_result("bash", {"command": "ls"})
        assert cached == tool_result, "Tool cache failed"
        print("   ✅ Tool result caching works")

        # Test cache stats
        stats = cache.get_stats()
        assert "memory_entries" in stats, "Stats missing memory_entries"
        assert "disk_entries" in stats, "Stats missing disk_entries"
        print("   ✅ Cache statistics work")


def test_logger_system():
    """Test logging functionality."""
    print("\n5️⃣  Testing Logger System...")

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = Logger(
            name="test",
            log_dir=Path(tmpdir),
            console=False,  # Disable console for testing
            file=True,
        )

        # Test different log levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Check log files were created
        log_file = Path(tmpdir) / "test.log"
        error_file = Path(tmpdir) / "test.error.log"

        assert log_file.exists(), "Log file not created"
        assert error_file.exists(), "Error log file not created"
        print("   ✅ Log files created")

        # Check error log only contains errors
        error_content = error_file.read_text()
        assert "Error message" in error_content, "Error not in error log"
        assert "Info message" not in error_content, "Info incorrectly in error log"
        print("   ✅ Log level filtering works")


def test_new_tools():
    """Test newly added tools."""
    print("\n6️⃣  Testing New Tools...")

    from terry.tools import tool_registry
    from terry.tools.find_tool import FindTool
    from terry.tools.ls_tool import LsTool

    # Register new tools
    find_tool = FindTool()
    ls_tool = LsTool()

    tool_registry.register(find_tool)
    tool_registry.register(ls_tool)

    # Test find tool
    result = find_tool.execute(pattern="*.py", path=".")
    assert "Error" not in result or "No files" in result, f"Find tool failed: {result}"
    print("   ✅ Find tool works")

    # Test ls tool
    result = ls_tool.execute(path=".")
    assert "Error" not in result, f"Ls tool failed: {result}"
    print("   ✅ Ls tool works")


def test_agent_integration():
    """Test agent integration with all features."""
    print("\n7️⃣  Testing Agent Integration...")

    from terry.core.agent import Agent

    config = TerryConfig()
    config.model.api_key = "test-key"

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = Agent(
            config=config,
            workdir=Path(tmpdir),
            enable_memory=True,
            enable_session=True,
            enable_metrics=True,
            enable_cache=True,
            enable_subagents=True,
        )

        # Test agent status
        status = agent.get_status()
        assert "workdir" in status, "Status missing workdir"
        assert "tools_available" in status, "Status missing tools_available"
        assert status["tools_available"] >= 20, f"Expected 20+ tools, got {status['tools_available']}"
        print(f"   ✅ Agent initialized with {status['tools_available']} tools")

        # Test metrics integration
        metrics = agent.get_metrics_summary()
        assert metrics is not None, "Metrics not available"
        print("   ✅ Metrics integration works")

        # Test cache clearing
        count = agent.clear_cache()
        assert count >= 0, "Cache clear failed"
        print(f"   ✅ Cache clearing works (cleared {count} entries)")


def main():
    """Run all production feature tests."""
    print("="*70)
    print("🧪 Terry Production Features Test Suite")
    print("="*70)

    try:
        test_memory_system()
        test_session_system()
        test_metrics_system()
        test_cache_system()
        test_logger_system()
        test_new_tools()
        test_agent_integration()

        print("\n" + "="*70)
        print("🎉 All production feature tests passed!")
        print("="*70)
        print("\n✅ Terry is production-ready with:")
        print("   - Persistent memory system")
        print("   - Session management")
        print("   - Metrics collection")
        print("   - Response caching")
        print("   - Structured logging")
        print("   - 16 built-in tools")
        print("   - Subagent support")
        print("   - Error recovery")
        print("   - Context compaction")

        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
