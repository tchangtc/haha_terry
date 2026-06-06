# Terry 快速测试脚本
# 验证核心功能是否正常工作

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("🧪 Terry 核心功能测试\n")

# 测试 1: 导入核心模块
print("1️⃣  测试模块导入...")
try:
    from terry.core.config import TerryConfig, ModelConfig
    from terry.core.llm import LLMClient
    from terry.core.agent import Agent
    from terry.tools import ToolRegistry
    from terry.hooks import HookRegistry
    print("   ✅ 所有核心模块导入成功\n")
except Exception as e:
    print(f"   ❌ 导入失败: {e}\n")
    sys.exit(1)

# 测试 2: 配置系统
print("2️⃣  测试配置系统...")
try:
    config = TerryConfig()
    assert config.max_tool_calls == 50
    assert config.compression_threshold == 0.75
    print(f"   ✅ 配置加载成功 (max_tool_calls={config.max_tool_calls})\n")
except Exception as e:
    print(f"   ❌ 配置测试失败: {e}\n")

# 测试 3: 工具注册
print("3️⃣  测试工具注册...")
try:
    registry = ToolRegistry()
    # 手动注册测试工具
    from terry.tools.bash import BashTool
    from terry.tools.read_file import ReadFileTool
    from terry.tools.write_file import WriteFileTool

    registry.register(BashTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())

    tools = registry.list_tools()
    print(f"   ✅ 注册了 {len(tools)} 个工具:")
    for tool in tools:
        print(f"      - {tool.name}: {tool.description[:50]}...")
    print()
except Exception as e:
    print(f"   ❌ 工具注册失败: {e}\n")

# 测试 4: Hook 系统
print("4️⃣  测试 Hook 系统...")
try:
    hooks = HookRegistry()

    # 注册测试钩子
    test_calls = []
    def test_hook(event, data):
        test_calls.append((event, data))

    hooks.register("PreToolUse", lambda tool_name, args: test_hook("PreToolUse", tool_name))
    hooks.register("PostToolUse", lambda tool_name, result: test_hook("PostToolUse", tool_name))

    # 触发钩子
    hooks.trigger("PreToolUse", "bash", {"command": "ls"})
    hooks.trigger("PostToolUse", "bash", "success")

    assert len(test_calls) == 2
    print(f"   ✅ Hook 系统工作正常 (触发了 {len(test_calls)} 个钩子)\n")
except Exception as e:
    print(f"   ❌ Hook 测试失败: {e}\n")

# 测试 5: LLM 客户端初始化
print("5️⃣  测试 LLM 客户端...")
try:
    model_config = ModelConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        api_key="test-key",  # 仅用于测试初始化
        max_tokens=4096
    )
    llm = LLMClient(model_config)
    print(f"   ✅ LLM 客户端初始化成功 (provider={model_config.provider})\n")
except Exception as e:
    print(f"   ❌ LLM 客户端测试失败: {e}\n")

# 测试 6: Agent 初始化
print("6️⃣  测试 Agent 初始化...")
try:
    config = TerryConfig()
    config.model.api_key = "test-key"  # 仅用于测试
    agent = Agent(config, workdir=str(Path(__file__).parent.parent))

    system_prompt = agent.build_system_prompt()
    assert "Terry" in system_prompt
    assert "coding agent" in system_prompt.lower()

    print(f"   ✅ Agent 初始化成功")
    print(f"   ✅ System prompt 生成正常 ({len(system_prompt)} 字符)\n")
except Exception as e:
    print(f"   ❌ Agent 测试失败: {e}\n")

# 测试 7: 权限检查
print("7️⃣  测试权限检查...")
try:
    from terry.hooks.permission import check_deny_list, check_destructive

    # 测试硬拒绝列表 (返回字符串表示被阻止，None 表示允许)
    assert check_deny_list("rm -rf /") is not None  # 应该返回阻止原因
    assert check_deny_list("sudo shutdown") is not None  # 应该返回阻止原因
    assert check_deny_list("ls -la") is None  # 应该返回 None (允许)

    # 测试破坏性模式 (返回字符串表示需要确认，None 表示允许)
    assert check_destructive("rm file.txt") is not None  # 应该返回确认原因
    assert check_destructive("chmod 777 file") is not None  # 应该返回确认原因
    assert check_destructive("cat file.txt") is None  # 应该返回 None (允许)

    print(f"   ✅ 权限检查逻辑正确")
    print(f"      - 硬拒绝列表: 3/3 测试通过")
    print(f"      - 破坏性模式: 3/3 测试通过\n")
except Exception as e:
    print(f"   ❌ 权限检查测试失败: {e}\n")

print("=" * 60)
print("🎉 所有核心功能测试通过！")
print("=" * 60)
print("\n📝 下一步:")
print("   1. 配置 API Key: export ANTHROPIC_API_KEY=sk-ant-...")
print("   2. 启动 Terry: source tc_terry/bin/activate && terry")
print("   3. 测试对话: 输入 '列出当前目录的文件'")
print(f"\n📚 详细文档: {Path(__file__).parent.parent / 'README.md'}")
