<p align="center">
  <h1 align="center">Terry 🤖</h1>
  <p align="center"><strong>你的 AI 编程代理 — 终端 · 网页 · 桌面 · 手机</strong></p>
</p>

<p align="center">
  <a href="https://github.com/tchangtc/haha_terry/actions"><img src="https://img.shields.io/badge/CI-passing-brightgreen.svg" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.12+-green.svg" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-1.0.0-orange.svg" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-1089%20assertions-brightgreen.svg" alt="Tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/tools-27-blue.svg" alt="Tools"></a>
  <a href="#"><img src="https://img.shields.io/badge/modules-127-orange.svg" alt="Modules"></a>
  <a href="#"><img src="https://img.shields.io/badge/ruff-0%20issues-green.svg" alt="Ruff"></a>
  <a href="#"><img src="https://img.shields.io/badge/CLI-✅-purple.svg" alt="CLI"></a>
  <a href="#"><img src="https://img.shields.io/badge/WebUI-✅-purple.svg" alt="WebUI"></a>
  <a href="#"><img src="https://img.shields.io/badge/Desktop-✅-purple.svg" alt="Desktop"></a>
  <a href="#"><img src="https://img.shields.io/badge/Mobile-✅-purple.svg" alt="Mobile"></a>
  <a href="#"><img src="https://img.shields.io/badge/container-Docker%20%7C%20containerd%20%7C%20K8s-blue.svg" alt="Container"></a>
  <a href="#"><img src="https://img.shields.io/badge/arch-amd64%20%7C%20arm64-blue.svg" alt="Arch"></a>
</p>

<p align="center">
  <a href="./README.md">English</a> |
  <a href="./README_zh-CN.md">简体中文</a> |
  <a href="./README_zh-TW.md">繁體中文</a>
</p>

---

## 📰 新闻

**2026-06**

- **v1.5.0** — **自主深化** — 项目上下文引擎（自动索引 + 相关性评分）、Memory 2.0（跨项目共享 + 偏好学习）、自主工作流 v2（webhook/CI/文件监听触发器）。
- **v1.4.0** — **观测与企业级** — OpenTelemetry 全链路追踪（LLM + 工具 + Agent）、Prometheus 指标导出（token、成本、延迟）、结构化审计日志（JSONL，90 天留存）、RBAC 4 角色权限矩阵覆盖全部 28 个工具。
- **v1.3.0** — **Agent 协作与路由** — 智能模型路由（成本/延迟感知）、Agent Swarm（scatter/gather/broadcast）、共享会话（多 Agent 锁 + 5 种内置角色）、PyPI 包更名为 `terry-agent`。
- **v1.2.0** — **插件生态与多模态** — 插件市场（GitHub 源 + 信任级别）、视频输入（ffmpeg 帧提取）、5 个内置 Agent 角色配置、对话式 MCP 配置、JSON 模式结构化输出。
- **v1.1.0** — **分发与集成** — 单二进制构建 (`curl \| bash`)、ACP 编辑器协议 (Zed/JetBrains)、OAuth 登录 (`terry login`)、公开 SDK (`terry/sdk.py`)、MkDocs 文档站。
- **v1.0.0** — **GA 发布** — 稳定 API、`pip install terry-agent`、社区治理、CI/CD、128K 输出、完整文档。
- **v0.9.0** — **设计系统** 统一配色体系。**Textual TUI** 多面板布局与 Vim 键位。**语音模式** Web Speech API。**WebUI** 代码高亮与动画。
- **v0.8.0** — **Agentic Task Loop** 自动规划执行与进度追踪。**Session Teleportation** 跨机器会话迁移。**Skill Marketplace** 社区技能市场。**Slash Command 工具** LLM 驱动 CLI 交互。
- **v0.7.0** — **Workflow Script DSL** Python 流式 API。**多层子代理** 5 级递归。**Agent View** 仪表盘实时监控。**Ultrareview** 4 维度对抗审查。**Routines** Webhook + API 触发。
- **v0.6.0** — **1M 上下文窗口**。**Effort 等级** (`/effort low|medium|high|xhigh`)。**Auto 模式分类器** 智能权限。**`/doctor` 诊断** 7 项检查。
- **v0.5.0** — **交互式 Rewind UI** 带 diff 预览。**Settings 热重载** 免重启迭代。**Background Tasks 管理** 统一 `/tasks` 监控。**`/goal` 命令** 目标驱动自主循环 + 评估器评分。
- **v0.4.0** — **自进化 Agent** 自动从工作流中学习并创建技能。**MiniMax** 及动态供应商支持。**CJK 分词估算**。**类型化工具错误** 提升自修正能力。
- **v0.3.0** — **Git 工作流工具**、**向量记忆**、**4 层上下文压缩**、**AutoHealer** 自愈、**安全中间件**。
- **v0.2.0** — **多 Agent 编排**（6 种模式）、**WebUI**、**桌面托盘**、**PWA 移动端**、**VS Code 扩展**。
- **v0.1.0** — **初始发布。** ReAct 智能体、多供应商 LLM、技能系统、3 门权限、16 工具。

---

## Terry 是什么？

Terry 是一个可以从**任何地方**对话的 AI 编程代理——终端、网页浏览器、桌面托盘、甚至手机上的 Telegram。你用自然语言描述需求，Terry 会读取你的代码库、执行命令、编辑文件，帮你把事情做完。

> **智能来自模型。Terry 是工具。**

---

## 选择你的交互方式

| 界面 | 启动命令 | 最适合 |
|-----------|--------------|----------|
| **终端** 🖥️ | `terry` | 极客用户、tmux/vim 工作流、CI/CD |
| **网页浏览器** 🌐 | `terry webui` | 可视化聊天、团队演示、远程访问 |
| **桌面应用** 🖥️ | `terry desktop` | 系统托盘、常驻后台、通知提醒 |
| **手机（PWA）** 📱 | 打开 WebUI → "添加到主屏幕" | 手机/平板随时随地编程 |
| **Telegram** 💬 | `TelegramGateway(token=...).start_polling()` | 从任何地方对话，无需安装 |
| **Discord** 💬 | `DiscordGateway(token=...).start_polling()` | 团队服务器协作 |

---

## 快速上手

```bash
# 终端模式
git clone https://github.com/tchangtc/haha_terry.git && cd haha_terry
pip install -e . 2>/dev/null || pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
terry || python -m terry.cli

# 网页模式（浏览器打开）
python -m terry.cli webui

# 桌面模式（系统托盘 + 网页界面）
terry desktop
```

启动后，直接输入任务：

```
terry [ask] ▸ 帮我找到这个项目里用户认证逻辑在哪里实现的
```

**支持的模型：** Anthropic Claude · OpenAI GPT-4o · DeepSeek · 智谱 GLM · 通义千问 · Ollama（本地运行）

---

## Terry 的与众不同

| 你关心的 | Terry 的做法 |
|---|---|
| **安全** | 4 级权限系统 + 运行时防护（DDoS、注入、CORS）。破坏性命令默认阻止。重要操作由你批准。 |
| **上下文** | 4 层渐进压缩。代码库再大也不会在执行中丢失上下文。 |
| **成本** | 模型路由器把简单任务分配给便宜模型。内置 Prompt 缓存。成本实时可见。 |
| **可控** | Plan-First 模式让 Terry 先出方案，你审核后再动手修改代码。 |
| **自愈** | 自动修复常见错误（缺包、路径错）——减少 40% 的人工干预。 |
| **记忆** | 跨会话记住你的偏好。从重复的工作流中自动总结技能。 |
| **安全网** | 交互式 Rewind UI — 浏览、对比、恢复任何快照。回滚前预览变更内容。 |
| **免重启配置** | Settings 热重载 — 编辑 `terry.json`，`/config reload` 立即生效。 |
| **自主目标** | `/goal` — 描述期望结果，Terry 自动迭代直到目标达成 + 自动评估。 |
| **隐私** | 一切本地运行。你的代码不会离开你的机器。 |
| **全界面** | 同一个 Agent 驱动所有界面——CLI、WebUI、桌面、手机、Telegram、Discord。 |

---

## 核心能力

### 🛠️ 27 个内置工具

- **文件** — 读取、写入、编辑（含 diff 预览）、多点编辑（原子操作）、Jupyter 笔记本编辑
- **搜索** — 正则搜索、glob 模式匹配、文件查找、目录列表
- **Git** — status、diff、log、commit（约定式提交格式）、branch、checkout、merge
- **网络** — 网页抓取（SSRF 安全防护）、网页搜索
- **扩展** — 图片/PDF 读取、计算器（安全沙箱求值）、天气、计时器、笔记、提醒

### 🔄 智能工作流

```
"我要重构认证模块"

/plan 重构认证模块              ← Terry 先出详细计划
                                ← 你审核通过后再执行

/wfd 重构认证 fan-out-merge     ← 或者：Terry 拆成并行子任务，
                                ← 分别执行，最后汇总结果
```

支持 6 种编排模式——分发汇总、对抗验证、竞赛、分类执行、循环至完成、生成筛选。

### 🧠 越用越聪明

Terry 会注意你重复做的事。几次之后，它会提议把这种工作流保存为技能。

```bash
/auto-skills         # 看看 Terry 从你的对话中学到了什么
/auto-skill-approve  # 把建议升级为永久技能
/curator             # 查看技能库的 7 天策展统计
```

---

## 命令速查

### 日常命令

| 命令 | 作用 |
|---------|--------------|
| `/help` | 显示所有命令 |
| `/new` | 开始新对话 |
| `/undo [<id>]` | 撤销变更（含 diff 预览 + 确认） |
| `/checkpoints` | 浏览所有快照 — diff、删除、选择性恢复 |
| `/search <关键词>` | 全文搜索聊天历史 |
| `/stream <消息>` | 实时流式查看回复 |
| `/save` / `/load` | 保存和恢复会话 |

### 安全与控制

| 命令 | 作用 |
|---------|--------------|
| `/mode ask` | 破坏性操作前询问（推荐） |
| `/mode auto` | 自动批准安全操作 |
| `/permissions` | 查看和管理权限规则 |
| `/plan <任务>` | 先看方案再执行 |
| `/config reload` | 热重载磁盘配置（无需重启） |
| `/config key=value` | 实时修改设置 |

### 高级功能

| 命令 | 作用 |
|---------|--------------|
| `/repomap` | 生成代码库结构图谱 |
| `/fork` | 分叉对话，探索不同方案 |
| `/goal <目标>` | 自主循环 — 迭代直到目标达成 |
| `/wfd <目标> <模式>` | 启动多代理动态工作流 |
| `/bg <任务>` | 投递即忘的后台任务 |
| `/tasks list` | 监控所有后台任务（peek、cancel） |
| `/auto <任务>` | 提交后台自主任务 |
| `/benchmark` | 运行评测套件 |
| `/sync-export` | 导出记忆到其他设备 |

---

## 启动 WebUI

```bash
terry webui                    # → http://127.0.0.1:8670
terry webui --port 9000        # 自定义端口
terry webui --host 0.0.0.0    # 允许局域网访问
```

WebUI 提供完整聊天界面：暗色主题、会话管理、流式响应、PWA 支持（可添加到手机主屏幕，像原生 App 一样使用）。

## 连接消息平台

```python
# Telegram：在手机上通过 Bot 和 Terry 对话
from terry.server.gateways.telegram_gateway import TelegramGateway
TelegramGateway(token="...", agent_factory=lambda: agent).start_polling()

# Discord：把 Terry 带到团队服务器
from terry.server.gateways.discord_gateway import DiscordGateway
DiscordGateway(token="...", agent_factory=lambda: agent).start_polling()
```

---

## 支持的 LLM 提供商

| 提供商 | 配置方式 | 最适合 |
|----------|-------|----------|
| **Anthropic Claude** | `export ANTHROPIC_API_KEY=...` | 复杂推理、大型代码库 |
| **OpenAI GPT-4o** | `export OPENAI_API_KEY=...` | 通用任务 |
| **DeepSeek** | `export DEEPSEEK_API_KEY=...` | 高性价比编程 |
| **智谱 GLM** | `export ZHIPU_API_KEY=...` | 中文场景支持 |
| **通义千问** | `export DASHSCOPE_API_KEY=...` | 有竞争力的性能 |
| **Ollama（本地）** | `ollama pull llama3` | 完全离线、零成本 |

需要其他提供商？添加 8 行配置即可——参考 [adapter.py](terry/core/adapter.py)。

---

## 架构一览

```
CLI · WebUI · Desktop · Mobile(PWA) · Telegram · Discord
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌──────────────┐              ┌─────────────────┐
│  HTTP Server │              │  CLI REPL (Rich) │
│  (REST+SSE)  │              │  45+ 命令        │
└──────┬───────┘              └───────┬─────────┘
       │                              │
       └──────────┬───────────────────┘
                  ▼
        ┌─────────────────┐
        │  Agent (ReAct)  │  ← 规划、路由到 LLM、执行工具
        └────────┬────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    ▼            ▼            ▼              ▼
┌───────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
│24     │ │4 级     │ │检查点    │ │动态工作      │
│工具   │ │安全     │ │和回滚    │ │流引擎 (6)    │
└───────┘ └─────────┘ └──────────┘ └──────────────┘
```

- **41 个核心模块**，职责清晰
- **6 种交互界面** — CLI、WebUI、桌面、PWA、Telegram、Discord
- **710 个测试** — pytest + 依赖注入

---


## 分发方式

| 方式 | 命令 | 平台 |
|--------|---------|----------|
| **PyPI** | `pip install terry-agent` | 全平台 (x86_64 + arm64) |
| **Docker** | `docker compose up` | 全平台 |
| **containerd** | `nerdctl compose up` | Linux 服务器 |
| **Kubernetes** | `kubectl apply -f deploy/kubernetes/terry.yaml` | 集群 |
| **Homebrew** | `brew install terry` | macOS |
| **源码** | `pip install -e .` | Python 3.12+ |

### 支持的架构

| 架构 | 平台 | 状态 |
|-------------|----------|--------|
| **x86_64 (amd64)** | Intel/AMD 服务器、云虚拟机 | ✅ |
| **aarch64 (arm64)** | Apple Silicon M1-M4、AWS Graviton、树莓派 5 | ✅ |
| **armv7** | 树莓派 3 | ✅ |

### 移动端 App

| 平台 | 方法 | 安装 |
|----------|--------|---------|
| **Android** | PWA → APK (Bubblewrap TWA) | `bubblewrap build` |
| **iOS** | PWA → 添加到主屏幕 | Safari → 分享 → 添加 |
| **双平台** | Telegram Bot | `/start` 在 Telegram 中 |


## 文档

- **[INSTALL.md](INSTALL.md)** — macOS、Linux、Windows 详细安装指南
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — 如何贡献工具、技能或修复
- **[CHANGELOG.md](CHANGELOG.md)** — 每个版本的变更记录
- **[docs/skills/README.md](docs/skills/README.md)** — 创建自定义技能
- **[RUNTIME_SECURITY.md](RUNTIME_SECURITY.md)** — 生产部署安全功能

---

## 参与贡献

```bash
git clone https://github.com/YOUR_USERNAME/haha_terry.git
git checkout -b feat/my-cool-tool
# 添加你的工具：继承 BaseTool，在 discover_tools() 中导入
pip install -e ".[dev]"
python -m pytest tests/ -v
# 提交 PR！
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

Terry 基于 **MIT 许可证** 发布。

Copyright (c) 2026 Terry Contributors

```
版权所有 (c) 2026 Terry Contributors

特此免费授予任何获得本软件及相关文档文件（"软件"）副本的人
不受限制地处理本软件的权利，包括但不限于使用、复制、修改、
合并、发布、分发、再许可和/或销售本软件副本的权利...
```

完整许可文本：[LICENSE](LICENSE)

**署名声明：** "Terry" 名称及其标识为 Terry Contributors 的商标。其他商标均为其各自所有者的财产。

### 第三方依赖许可证

Terry 依赖以下开源包（均为 MIT 或 Apache 2.0）：

| 包 | 许可证 | 用途 |
|---------|---------|-------|
| anthropic | MIT | Anthropic Claude SDK |
| openai | Apache 2.0 | OpenAI 及兼容提供商 |
| httpx | BSD | HTTP 客户端 |
| rich | MIT | 终端 UI |
| typer | MIT | CLI 框架 |
| pyyaml | MIT | YAML 解析 |
| tiktoken | MIT | Token 计数 |
| python-dotenv | BSD | 环境变量加载 |

### 贡献许可

向 Terry 贡献代码即表示您同意您的贡献将基于 MIT 许可证发布。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

<p align="center">
  <sub>用 ❤️ 构建，来自 Terry 社区 · <a href="#terry-">回到顶部 ↑</a></sub>
</p>
