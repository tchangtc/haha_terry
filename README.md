# Terry 🤖 | Terry 🤖 | Terry 🤖

[English](#english) | [简体中文](#简体中文) | [繁體中文](#繁體中文)

---

## English

### A Personal AI Coding Agent - The Harness for Your LLM

Terry is a lightweight, extensible AI coding agent built on principles from Claude Code, merco, and learn-claude-code. It implements the ReAct (Reasoning + Acting) pattern with comprehensive safety features and context management.

> **Agency comes from the model. Terry is the harness.**

#### ✨ Features

- **🧠 Core Agent Loop** - ReAct pattern with tool budget and hallucination filtering
- **🔧 16 Built-in Tools** - bash, read_file, write_file, edit_file, glob, grep, web_fetch, web_search, todo_write, reminder, notes, timer, calculator, weather, find, ls
- **🎯 Skills System** - Dynamic skill loading and matching (code-review, data-analysis, document-generator)
- **🔒 3-Gate Security** - Deny list → Destructive patterns → User approval
- **🪝 Hook System** - Extensible event-based architecture (PreToolUse, PostToolUse, Stop, UserPromptSubmit)
- **🌐 Multi-Provider** - Anthropic, OpenAI, DeepSeek, and OpenAI-compatible APIs
- **📝 Edit with Diff** - SEARCH/REPLACE mode with unified diff preview
- **🗜️ Context Compaction** - Automatic conversation history management with LLM-assisted summarization
- **🔄 Error Recovery** - Exponential backoff retry (1s → 60s) with intelligent error detection

#### 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/terry-ai/terry.git
cd terry

# Create and activate virtual environment
uv venv tc_terry
source tc_terry/bin/activate

# Install in development mode
uv pip install -e .

# Configure API key
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."
# or
export DEEPSEEK_API_KEY="sk-..."

# Start Terry
terry

# Check version
terry --version
```

#### 🎯 Interactive Commands

- `/help` - Show help
- `/new` - Start new conversation
- `/model` - Show current model
- `/tools` - List available tools
- `/skills` - List available skills
- `/skill <name>` - Show skill details
- `/activate <name>` - Activate a skill
- `/deactivate` - Deactivate current skill
- `/reload-skills` - Reload skills from disk
- `/context` - Show context usage
- `/exit` - Exit Terry

#### 🛠️ Tools

**Development Tools:**

| Tool | Description | Security |
|------|-------------|----------|
| `bash` | Execute shell commands | 120s timeout, 50KB output limit |
| `read_file` | Read file contents | Path escape protection |
| `write_file` | Create/overwrite files | Path escape protection |
| `edit_file` | SEARCH/REPLACE editing | Uniqueness check + diff preview |
| `glob` | File pattern matching | Path protection + 100 result limit |
| `grep` | Code search | Regex support, case-insensitive |
| `find` | Search for files | Path protection |
| `ls` | List directory contents | Path protection |

**Web & Data Tools:**

| Tool | Description | Security |
|------|-------------|----------|
| `web_fetch` | URL content fetching | Private IP blocking, 50KB limit |
| `web_search` | Search the web | API key required |

**Productivity Tools:**

| Tool | Description | Features |
|------|-------------|----------|
| `todo_write` | Task management | Status tracking, persistence |
| `reminder` | Set reminders | Time-based alerts |
| `notes` | Take notes | Quick note capture |
| `timer` | Timer/Pomodoro | Focus sessions |

**Utility Tools:**

| Tool | Description | Features |
|------|-------------|----------|
| `calculator` | Mathematical calculations | Basic math operations |
| `weather` | Weather information | Location-based forecasts |

#### 🎯 Skills System

Skills are dynamic instruction sets that teach Terry specialized workflows. They are loaded from Markdown files and matched automatically based on user intent.

**Built-in Skills:**

| Skill | Description | Triggers |
|-------|-------------|----------|
| `code-review` | Comprehensive code review | "代码审查", "code review", "审查代码" |
| `data-analysis` | Data file analysis | "数据分析", "data analysis", "分析数据" |
| `document-generator` | Professional document generation | "生成文档", "generate document", "创建报告" |

**Using Skills:**

```bash
# Automatic matching (recommended)
You > Help me review this code
Terry > [Automatically activates code-review skill]

# Manual activation
/activate code-review

# List all skills
/skills

# View skill details
/skill code-review

# Deactivate current skill
/deactivate

# Reload skills from disk
/reload-skills
```

**Creating Custom Skills:**

```bash
# 1. Create skill directory
mkdir -p ~/.terry/skills/my-skill

# 2. Create SKILL.md
cat > ~/.terry/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: My custom skill
triggers:
  - my trigger
  - 我的触发词
---

# My Skill

Instructions here...
EOF

# 3. Reload in Terry
/reload-skills
```

See [Skills Documentation](docs/skills/README.md) for detailed format and examples.

#### 🧪 Testing & Dependency Injection

Terry uses a global singleton pattern with `reset_xxx()` / `set_xxx()` injection for test isolation:

```python
from terry.core.memory import get_memory, set_memory, reset_memory
from terry.core.metrics import get_metrics, set_metrics, reset_metrics

# Inject mock instances for testing
set_memory(mock_memory)
set_metrics(mock_metrics)

# Reset all singletons between tests
reset_memory()
reset_metrics()
```

Run tests:
```bash
# Run all pytest-compatible tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_tools_and_security.py -v
```

#### 📡 Streaming Support

Terry supports streaming LLM responses for real-time output:

```python
from terry.core.llm import LLMClient
from terry.core.config import ModelConfig

client = LLMClient(ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key="..."))
for chunk in client.chat_stream(
    messages=[{"role": "user", "content": "Hello"}],
    system="You are helpful.",
):
    print(chunk, end="", flush=True)
```

#### 🤖 CI/CD

GitHub Actions CI runs linting, type checking, and tests on push/PR:
- **Lint**: Ruff checks code style
- **Type Check**: MyPy verifies type annotations
- **Test**: Pytest across Python 3.12 and 3.13

#### 🔒 Security System

Terry implements a 3-gate permission system:

1. **Gate 1: Hard Deny List** - Always blocked (e.g., `rm -rf /`, `sudo`, `shutdown`)
2. **Gate 2: Destructive Patterns** - Require user approval (e.g., `rm `, `chmod 777`)
3. **Gate 3: Path Escape Check** - File operations outside workspace require approval

#### 🏗️ Architecture

```
terry/
├── core/                  # Core modules
│   ├── agent.py          # Agent loop (ReAct pattern)
│   ├── config.py         # Configuration system
│   ├── llm.py            # LLM client wrapper
│   ├── skill.py          # Skills system
│   ├── context_compact.py # Context compression
│   └── error_recovery.py # Error recovery
├── tools/                 # Tools (16 total)
│   ├── bash.py
│   ├── read_file.py
│   ├── write_file.py
│   ├── edit_file.py
│   ├── glob_tool.py
│   ├── grep_tool.py
│   ├── web_fetch.py
│   ├── web_search.py
│   ├── todo_write.py
│   ├── reminder.py
│   ├── notes.py
│   ├── timer.py
│   ├── calculator.py
│   ├── weather.py
│   ├── find_tool.py
│   └── ls_tool.py
├── hooks/                 # Hook system
│   ├── permission.py     # 3-gate permission
│   └── logging_hook.py   # Audit logging
└── skills/                # Skills directory
    ├── code-review/
    ├── data-analysis/
    └── document-generator/
```

#### 📚 Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [LICENSE](LICENSE) - MIT License
- [docs/internal/](docs/internal/) - Internal development reports

#### 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

#### 📄 License

MIT License - Copyright (c) 2026 Terry Contributors

---

## 简体中文

### 个人 AI 编程 Agent - 为您的 LLM 提供工具

Terry 是一个轻量级、可扩展的 AI 编程 Agent，基于 Claude Code、merco 和 learn-claude-code 的原则构建。它实现了 ReAct（推理 + 行动）模式，具有全面的安全特性和上下文管理功能。

> **智能来自模型。Terry 是工具。**

#### ✨ 特性

- **🧠 核心 Agent 循环** - ReAct 模式，带工具预算和幻觉过滤
- **🔧 16 个内置工具** - bash、read_file、write_file、edit_file、glob、grep、web_fetch、web_search、todo_write、reminder、notes、timer、calculator、weather、find、ls
- **🎯 Skills 系统** - 动态技能加载和匹配（code-review、data-analysis、document-generator）
- **🔒 3 层安全系统** - 拒绝列表 → 破坏性模式 → 用户确认
- **🪝 Hook 系统** - 可扩展的事件架构（PreToolUse、PostToolUse、Stop、UserPromptSubmit）
- **🌐 多提供商支持** - Anthropic、OpenAI、DeepSeek 及 OpenAI 兼容 API
- **📝 差异编辑** - SEARCH/REPLACE 模式，带统一差异预览
- **🗜️ 上下文压缩** - 自动管理对话历史，LLM 辅助摘要
- **🔄 错误恢复** - 指数退避重试（1s → 60s），智能错误检测

#### 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/terry-ai/terry.git
cd terry

# 创建并激活虚拟环境
uv venv tc_terry
source tc_terry/bin/activate

# 开发模式安装
uv pip install -e .

# 配置 API 密钥
export ANTHROPIC_API_KEY="sk-ant-..."
# 或
export OPENAI_API_KEY="sk-..."
# 或
export DEEPSEEK_API_KEY="sk-..."

# 启动 Terry
terry

# 查看版本
terry --version
```

#### 🎯 交互命令

- `/help` - 显示帮助
- `/new` - 开始新对话
- `/model` - 显示当前模型
- `/tools` - 列出可用工具
- `/skills` - 列出可用技能
- `/skill <name>` - 显示技能详情
- `/activate <name>` - 激活技能
- `/deactivate` - 停用当前技能
- `/reload-skills` - 重新加载技能
- `/context` - 显示上下文使用情况
- `/exit` - 退出 Terry

#### 🛠️ 工具

**开发工具：**

| 工具 | 描述 | 安全措施 |
|------|------|----------|
| `bash` | 执行 shell 命令 | 120秒超时，50KB 输出限制 |
| `read_file` | 读取文件内容 | 路径逃逸保护 |
| `write_file` | 创建/覆盖文件 | 路径逃逸保护 |
| `edit_file` | SEARCH/REPLACE 编辑 | 唯一性检查 + 差异预览 |
| `glob` | 文件模式匹配 | 路径保护 + 100 结果限制 |
| `grep` | 代码搜索 | 支持正则，大小写不敏感 |
| `find` | 搜索文件 | 路径保护 |
| `ls` | 列出目录内容 | 路径保护 |

**网络与数据工具：**

| 工具 | 描述 | 安全措施 |
|------|------|----------|
| `web_fetch` | URL 内容获取 | 阻止 localhost，50KB 限制 |
| `web_search` | 网络搜索 | 需要 API 密钥 |

**生产力工具：**

| 工具 | 描述 | 功能 |
|------|------|------|
| `todo_write` | 任务管理 | 状态跟踪，持久化 |
| `reminder` | 设置提醒 | 基于时间的提醒 |
| `notes` | 记笔记 | 快速笔记捕获 |
| `timer` | 计时器/番茄钟 | 专注会话 |

**实用工具：**

| 工具 | 描述 | 功能 |
|------|------|------|
| `calculator` | 数学计算 | 基本数学运算 |
| `weather` | 天气信息 | 基于位置的天气预报 |

#### 🎯 Skills 系统

Skills 是动态指令集，教 Terry 专门的工作流程。它们从 Markdown 文件加载，并根据用户意图自动匹配。

**内置技能：**

| 技能 | 描述 | 触发词 |
|------|------|--------|
| `code-review` | 全面代码审查 | "代码审查", "code review", "审查代码" |
| `data-analysis` | 数据文件分析 | "数据分析", "data analysis", "分析数据" |
| `document-generator` | 专业文档生成 | "生成文档", "generate document", "创建报告" |

**使用技能：**

```bash
# 自动匹配（推荐）
You > 帮我审查这段代码
Terry > [自动激活 code-review 技能]

# 手动激活
/activate code-review

# 列出所有技能
/skills

# 查看技能详情
/skill code-review

# 停用当前技能
/deactivate

# 重新加载技能
/reload-skills
```

**创建自定义技能：**

```bash
# 1. 创建技能目录
mkdir -p ~/.terry/skills/my-skill

# 2. 创建 SKILL.md
cat > ~/.terry/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 我的自定义技能
triggers:
  - my trigger
  - 我的触发词
---

# 我的技能

指令说明...
EOF

# 3. 在 Terry 中重新加载
/reload-skills
```

详见 [技能文档](docs/skills/README.md) 了解详细格式和示例。

#### 🔒 安全系统

1. **第一层：硬拒绝列表** - 始终阻止（如 `rm -rf /`、`sudo`、`shutdown`）
2. **第二层：破坏性模式** - 需要用户确认（如 `rm `、`chmod 777`）
3. **第三层：路径逃逸检查** - 工作区外的文件操作需要确认

#### 🏗️ 架构

```
terry/
├── core/                  # 核心模块
│   ├── agent.py          # Agent 循环（ReAct 模式）
│   ├── config.py         # 配置系统
│   ├── llm.py            # LLM 客户端封装
│   ├── skill.py          # Skills 系统
│   ├── context_compact.py # 上下文压缩
│   └── error_recovery.py # 错误恢复
├── tools/                 # 工具（共 16 个）
│   ├── bash.py
│   ├── read_file.py
│   ├── write_file.py
│   ├── edit_file.py
│   ├── glob_tool.py
│   ├── grep_tool.py
│   ├── web_fetch.py
│   ├── web_search.py
│   ├── todo_write.py
│   ├── reminder.py
│   ├── notes.py
│   ├── timer.py
│   ├── calculator.py
│   ├── weather.py
│   ├── find_tool.py
│   └── ls_tool.py
├── hooks/                 # Hook 系统
│   ├── permission.py     # 3 层权限
│   └── logging_hook.py   # 审计日志
└── skills/                # Skills 目录
    ├── code-review/
    ├── data-analysis/
    └── document-generator/
```

#### 📚 文档

- [CONTRIBUTING.md](CONTRIBUTING.md) - 贡献指南
- [CHANGELOG.md](CHANGELOG.md) - 版本历史
- [LICENSE](LICENSE) - MIT 许可证
- [docs/internal/](docs/internal/) - 内部开发报告

#### 🤝 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解指南。

#### 📄 许可证

MIT 许可证 - 版权所有 (c) 2026 Terry Contributors

---

## 繁體中文

### 個人 AI 編程 Agent - 為您的 LLM 提供工具

Terry 是一個輕量級、可擴展的 AI 編程 Agent，基於 Claude Code、merco 和 learn-claude-code 的原則構建。它實現了 ReAct（推理 + 行動）模式，具有全面的安全特性和上下文管理功能。

> **智能來自模型。Terry 是工具。**

#### ✨ 特性

- **🧠 核心 Agent 循環** - ReAct 模式，帶工具預算和幻覺過濾
- **🔧 16 個內置工具** - bash、read_file、write_file、edit_file、glob、grep、web_fetch、web_search、todo_write、reminder、notes、timer、calculator、weather、find、ls
- **🎯 Skills 系統** - 動態技能加載和匹配（code-review、data-analysis、document-generator）
- **🔒 3 層安全系統** - 拒絕列表 → 破壞性模式 → 用戶確認
- **🪝 Hook 系統** - 可擴展的事件架構（PreToolUse、PostToolUse、Stop、UserPromptSubmit）
- **🌐 多提供商支持** - Anthropic、OpenAI、DeepSeek 及 OpenAI 兼容 API
- **📝 差異編輯** - SEARCH/REPLACE 模式，帶統一差異預覽
- **🗜️ 上下文壓縮** - 自動管理對話歷史，LLM 輔助摘要
- **🔄 錯誤恢復** - 指數退避重試（1s → 60s），智能錯誤檢測

#### 🚀 快速開始

```bash
# 克隆倉庫
git clone https://github.com/terry-ai/terry.git
cd terry

# 創建並激活虛擬環境
uv venv tc_terry
source tc_terry/bin/activate

# 開發模式安裝
uv pip install -e .

# 配置 API 密鑰
export ANTHROPIC_API_KEY="sk-ant-..."
# 或
export OPENAI_API_KEY="sk-..."
# 或
export DEEPSEEK_API_KEY="sk-..."

# 啟動 Terry
terry

# 查看版本
terry --version
```

#### 🎯 交互命令

- `/help` - 顯示幫助
- `/new` - 開始新對話
- `/model` - 顯示當前模型
- `/tools` - 列出可用工具
- `/skills` - 列出可用技能
- `/skill <name>` - 顯示技能詳情
- `/activate <name>` - 激活技能
- `/deactivate` - 停用當前技能
- `/reload-skills` - 重新加載技能
- `/context` - 顯示上下文使用情況
- `/exit` - 退出 Terry

#### 🛠️ 工具

**開發工具：**

| 工具 | 描述 | 安全措施 |
|------|------|----------|
| `bash` | 執行 shell 命令 | 120秒超時，50KB 輸出限制 |
| `read_file` | 讀取文件內容 | 路徑逃逸保護 |
| `write_file` | 創建/覆蓋文件 | 路徑逃逸保護 |
| `edit_file` | SEARCH/REPLACE 編輯 | 唯一性檢查 + 差異預覽 |
| `glob` | 文件模式匹配 | 路徑保護 + 100 結果限制 |
| `grep` | 代碼搜索 | 支持正則，大小寫不敏感 |
| `find` | 搜索文件 | 路徑保護 |
| `ls` | 列出目錄內容 | 路徑保護 |

**網絡與數據工具：**

| 工具 | 描述 | 安全措施 |
|------|------|----------|
| `web_fetch` | URL 內容獲取 | 阻止 localhost，50KB 限制 |
| `web_search` | 網絡搜索 | 需要 API 密鑰 |

**生產力工具：**

| 工具 | 描述 | 功能 |
|------|------|------|
| `todo_write` | 任務管理 | 狀態跟踪，持久化 |
| `reminder` | 設置提醒 | 基於時間的提醒 |
| `notes` | 記筆記 | 快速筆記捕獲 |
| `timer` | 計時器/番茄鐘 | 專注會話 |

**實用工具：**

| 工具 | 描述 | 功能 |
|------|------|------|
| `calculator` | 數學計算 | 基本數學運算 |
| `weather` | 天氣信息 | 基於位置的天氣預報 |

#### 🎯 Skills 系統

Skills 是動態指令集，教 Terry 專門的工作流程。它們從 Markdown 文件加載，並根據用戶意圖自動匹配。

**內置技能：**

| 技能 | 描述 | 觸發詞 |
|------|------|--------|
| `code-review` | 全面代碼審查 | "代碼審查", "code review", "審查代碼" |
| `data-analysis` | 數據文件分析 | "數據分析", "data analysis", "分析數據" |
| `document-generator` | 專業文檔生成 | "生成文檔", "generate document", "創建報告" |

**使用技能：**

```bash
# 自動匹配（推薦）
You > 幫我審查這段代碼
Terry > [自動激活 code-review 技能]

# 手動激活
/activate code-review

# 列出所有技能
/skills

# 查看技能詳情
/skill code-review

# 停用當前技能
/deactivate

# 重新加載技能
/reload-skills
```

**創建自定義技能：**

```bash
# 1. 創建技能目錄
mkdir -p ~/.terry/skills/my-skill

# 2. 創建 SKILL.md
cat > ~/.terry/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 我的自定義技能
triggers:
  - my trigger
  - 我的觸發詞
---

# 我的技能

指令說明...
EOF

# 3. 在 Terry 中重新加載
/reload-skills
```

詳見 [技能文檔](docs/skills/README.md) 了解詳細格式和示例。

#### 🔒 安全系統

Terry 實現了 3 層權限系統：

1. **第一層：硬拒絕列表** - 始終阻止（如 `rm -rf /`、`sudo`、`shutdown`）
2. **第二層：破壞性模式** - 需要用戶確認（如 `rm `、`chmod 777`）
3. **第三層：路徑逃逸檢查** - 工作區外的文件操作需要確認

#### 🏗️ 架構

```
terry/
├── core/                  # 核心模塊
│   ├── agent.py          # Agent 循環（ReAct 模式）
│   ├── config.py         # 配置系統
│   ├── llm.py            # LLM 客戶端封裝
│   ├── skill.py          # Skills 系統
│   ├── context_compact.py # 上下文壓縮
│   └── error_recovery.py # 錯誤恢復
├── tools/                 # 工具（共 16 個）
│   ├── bash.py
│   ├── read_file.py
│   ├── write_file.py
│   ├── edit_file.py
│   ├── glob_tool.py
│   ├── grep_tool.py
│   ├── web_fetch.py
│   ├── web_search.py
│   ├── todo_write.py
│   ├── reminder.py
│   ├── notes.py
│   ├── timer.py
│   ├── calculator.py
│   ├── weather.py
│   ├── find_tool.py
│   └── ls_tool.py
├── hooks/                 # Hook 系統
│   ├── permission.py     # 3 層權限
│   └── logging_hook.py   # 審計日誌
└── skills/                # Skills 目錄
    ├── code-review/
    ├── data-analysis/
    └── document-generator/
```

#### 📚 文檔

- [CONTRIBUTING.md](CONTRIBUTING.md) - 貢獻指南
- [CHANGELOG.md](CHANGELOG.md) - 版本歷史
- [LICENSE](LICENSE) - MIT 許可證
- [docs/internal/](docs/internal/) - 內部開發報告

#### 🤝 貢獻

歡迎貢獻！請閱讀 [CONTRIBUTING.md](CONTRIBUTING.md) 了解指南。

#### 📄 許可證

MIT 許可證 - 版權所有 (c) 2026 Terry Contributors

---

<div align="center">

**Built with ❤️ by the Terry community**

[⬆ Back to top](#terry-----terry-----terry-)

</div>
