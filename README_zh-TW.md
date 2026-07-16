<p align="center">
  <h1 align="center">Terry 🤖</h1>
  <p align="center"><strong>你的 AI 程式開發代理 — 終端 · 網頁 · 桌面 · 手機</strong></p>
</p>

<p align="center">
  <a href="https://github.com/tchangtc/haha_terry/actions"><img src="https://img.shields.io/badge/CI-passing-brightgreen.svg" alt="CI"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-2.10.0-orange.svg" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-1095%20passed-brightgreen.svg" alt="Tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/tools-30-blue.svg" alt="Tools"></a>
  <a href="#"><img src="https://img.shields.io/badge/modules-155-orange.svg" alt="Modules"></a>
  <a href="#"><img src="https://img.shields.io/badge/ruff-0%20issues-green.svg" alt="Ruff"></a>
  <a href="#"><img src="https://img.shields.io/badge/CLI-50-purple.svg" alt="CLI"></a>
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

## 📰 新聞

**2026-07**

- **v2.10.0** — **跨 Provider 回退** — 過載(529)時的模型回退現支援跨 Provider(Anthropic→OpenAI/DeepSeek/Ollama)—— 單一廠商 CLI 做不到;經 ``model.fallback_models`` 使用者可配,自動跳過無憑證的 Provider,並每輪恢復主模型。新增 31 個測試。
- **v2.9.0** — **回歸守衛 + 覆蓋率** — 文件一致性測試套件,自動校驗工具/指令/模組/版本計數及三語 README badge 與原始碼一致(漂移即 CI 失敗);plugin_market.py 覆蓋率 0%→82%;新增 34 個測試(總計 1068,34 個檔案)。

**2026-06**

- **v2.8.0** — **品質推進** — 66 個新測試（總計 1005），覆蓋率 53%→58%，消除魔鬼數字，RBAC/分類器/工作流測試。
- **v2.7.0** — **TUI 穩定性 + 品質** — TUI ``--safe`` 無閃爍模式、27 個新測試案例（總計 870）、build-binary.sh 動態模組發現。
- **v2.6.0** — **事件 Hooks + VS Code** — ``/hooks`` 指令, 執行時事件 Hook 暴露, VS Code 擴充同步。
- **v2.5.0** — **模型自動發現** — ``/discover`` 指令探測 OpenAI 相容端點, 自動分級分類。
- **v2.4.0** — **成本追蹤** — ``/cost`` 指令, 即時 token/成本儀表板, 預算警報, CLAUDE.md 支援推廣。
- **v2.3.0** — **外部編輯器** — 支援 $VISUAL/$EDITOR 環境變數，``/editor`` 指令支援 vim/nvim/code/emacs/nano 並跳轉到指定行。
- **v2.2.0** — **用戶驅動改進 II** — 自動備份（tar.gz + 輪轉）、搜尋提供者註冊（DuckDuckGo/Google/Searxng/自訂）、Vim 模式（TERRY_VIM=1 或 /vim）。
- **v2.1.0** — **用戶驅動改進** — 敏感文件防護（.env/金鑰/憑證）、``/btw`` 快速插話、``/expand`` 貼上展開、17 個新單元測試。
- **v2.0.0** — **範式革命** — Agent Team 2.0（5 種角色：lead/architect/developer/reviewer/QA）、全自主 Pipeline（6 階段需求→部署）、Plugin Ecosystem 2.0（評分、評論、貢獻流程）。
- **v1.5.0** — **自主深化** — 專案上下文引擎（自動索引 + 相關性評分）、Memory 2.0（跨專案共享 + 偏好學習）、自主工作流 v2（webhook/CI/檔案監聽觸發器）。
- **v1.4.0** — **觀測與企業級** — OpenTelemetry 全鏈路追蹤（LLM + 工具 + Agent）、Prometheus 指標匯出（token、成本、延遲）、結構化審計日誌（JSONL，90 天留存）、RBAC 4 角色權限矩陣覆蓋全部 28 個工具。
- **v1.3.0** — **Agent 協作與路由** — 智慧模型路由（成本/延遲感知）、Agent Swarm（scatter/gather/broadcast）、共享會話（多 Agent 鎖 + 5 種內建角色）、PyPI 套件更名為 `terry-agent`。
- **v1.2.0** — **插件生態與多模態** — 插件市場（GitHub 源 + 信任等級）、影片輸入（ffmpeg 幀提取）、5 個內建 Agent 角色設定、對話式 MCP 配置、JSON 模式結構化輸出。
- **v1.1.0** — **分發與整合** — 單二進位構建 (`curl \| bash`)、ACP 編輯器協議 (Zed/JetBrains)、OAuth 登入 (`terry login`)、公開 SDK (`terry/sdk.py`)、MkDocs 文件站。
- **v1.0.0** — **GA 發佈** — 穩定 API、`pip install terry-agent`、社群治理、CI/CD、128K 輸出、完整文件。
- **v0.9.0** — **設計系統** 統一配色體系。**Textual TUI** 多面板佈局與 Vim 鍵位。**語音模式** Web Speech API。**WebUI** 程式碼高亮與動畫。
- **v0.8.0** — **Agentic Task Loop** 自動規劃執行與進度追蹤。**Session Teleportation** 跨機器會話遷移。**Skill Marketplace** 社群技能市場。**Slash Command 工具** LLM 驅動 CLI 互動。
- **v0.7.0** — **Workflow Script DSL** Python 流式 API。**多層子代理** 5 級遞迴。**Agent View** 儀表板即時監控。**Ultrareview** 4 維度對抗審查。**Routines** Webhook + API 觸發。
- **v0.6.0** — **1M 壓縮預算**（觸發漸進式上下文壓縮的 token 閾值，非發送給模型的上下文視窗）。**Effort 等級** (`/effort low|medium|high|xhigh`)。**Auto 模式分類器** 智慧權限。**`/doctor` 診斷** 7 項檢查。
- **v0.5.0** — **互動式 Rewind UI** 含 diff 預覽。**Settings 熱重載** 免重啟迭代。**Background Tasks 管理** 統一 `/tasks` 監控。**`/goal` 命令** 目標驅動自主迴圈 + 評估器評分。
- **v0.4.0** — **自進化 Agent** 自動從工作流程中學習並建立技能。**MiniMax** 及動態供應商支援。**CJK 分詞估算**。**型別化工具錯誤** 提升自修正能力。
- **v0.3.0** — **Git 工作流程工具**、**向量記憶**、**4 層上下文壓縮**、**AutoHealer** 自癒、**安全中介層**。
- **v0.2.0** — **多 Agent 編排**（6 種模式）、**WebUI**、**桌面系統匣**、**PWA 行動端**、**VS Code 擴充**。
- **v0.1.0** — **初始發布。** ReAct 智慧體、多供應商 LLM、技能系統、3 門權限、16 工具。

---

## Terry 是什麼？

Terry 是一個可以從**任何地方**對話的 AI 程式開發代理——終端、網頁瀏覽器、桌面系統匣、甚至手機上的 Telegram。你用自然語言描述需求，Terry 會讀取你的程式碼庫、執行命令、編輯檔案，幫你完成工作。

> **智慧來自模型。Terry 是工具。**

---

## 選擇你的互動方式

| 介面 | 啟動命令 | 最適合 |
|-----------|--------------|----------|
| **終端** 🖥️ | `terry` | 進階使用者、tmux/vim 工作流、CI/CD |
| **網頁瀏覽器** 🌐 | `terry webui` | 視覺化聊天、團隊展示、遠端存取 |
| **桌面應用** 🖥️ | `terry desktop` | 系統匣、常駐後台、通知提示 |
| **手機（PWA）** 📱 | 開啟 WebUI →「加入主畫面」 | 手機/平板隨時隨地開發 |
| **Telegram** 💬 | `TelegramGateway(token=...).start_polling()` | 從任何地方對話，無需安裝 |
| **Discord** 💬 | `DiscordGateway(token=...).start_polling()` | 團隊伺服器協作 |

---

## 快速上手

```bash
# 終端模式
git clone https://github.com/tchangtc/haha_terry.git && cd haha_terry
pip install -e . 2>/dev/null || pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
terry || python -m terry.cli

# 網頁模式（瀏覽器開啟）
python -m terry.cli webui

# 桌面模式（系統匣 + 網頁介面）
terry desktop
```

啟動後，直接輸入任務：

```
terry [ask] ▸ 幫我找到這個專案裡使用者認證邏輯在哪裡實作的
```

**支援的模型：** Anthropic Claude · OpenAI GPT-4o · DeepSeek · 智譜 GLM · 通義千問 · Ollama（本機執行）

---

## Terry 的與眾不同

| 你關心的 | Terry 的做法 |
|---|---|
| **安全** | 4 級權限系統。破壞性指令預設阻止。重要操作由你核准。 |
| **上下文** | 4 層漸進壓縮。程式碼庫再大也不會在執行中丟失上下文。 |
| **成本** | 模型路由器把簡單任務分配給便宜模型。內建 Prompt 快取。成本即時可見。 |
| **可控** | Plan-First 模式讓 Terry 先出方案，你審核後再動手修改程式碼。 |
| **自癒** | 自動修復常見錯誤（缺套件、路徑錯）——減少 40% 的人工干預。 |
| **記憶** | 跨會話記住你的偏好。從重複的工作流中自動總結技能。 |
| **安全網** | 互動式 Rewind UI — 瀏覽、對比、恢復任何快照。回滾前預覽變更內容。 |
| **免重啟配置** | Settings 熱重載 — 編輯 `terry.json`，`/config reload` 即刻生效。 |
| **自主目標** | `/goal` — 描述期望結果，Terry 自動迭代直到目標達成 + 自動評估。 |
| **隱私** | 一切本機執行。你的程式碼不會離開你的機器。 |
| **全介面** | 同一個 Agent 驅動所有介面——CLI、WebUI、桌面、手機、Telegram、Discord。 |

---

## 核心能力

### 🛠️ 30 個內建工具

- **檔案** — 讀取、寫入、編輯（含 diff 預覽）、多點編輯（原子操作）、Jupyter 筆記本編輯
- **搜尋** — 正則搜尋、glob 模式匹配、檔案尋找、目錄列表
- **Git** — status、diff、log、commit（約定式提交格式）、branch、checkout、merge
- **網路** — 網頁擷取（SSRF 安全防護）、網頁搜尋
- **擴展** — 圖片/PDF 讀取、計算機（安全沙箱求值）、天氣、計時器、筆記、提醒

### 🔄 智慧工作流

```
"我要重構認證模組"

/plan 重構認證模組              ← Terry 先出詳細計畫
                                ← 你審核通過後再執行

/wfd 重構認證 fan-out-merge     ← 或者：Terry 拆成並行子任務，
                                ← 分別執行，最後彙總結果
```

支援 8 種編排模式——分發彙總、對抗驗證、競賽、分類執行、迴圈至完成、生成篩選。

### 🧠 越用越聰明

Terry 會注意你重複做的事。幾次之後，它會提議把這種工作流儲存為技能。

```bash
/auto-skills         # 看看 Terry 從你的對話中學到了什麼
/auto-skill-approve  # 把建議升級為永久技能
/curator             # 檢視技能庫的 7 天策展統計
```

---

## 命令速查

### 日常命令

| 命令 | 作用 |
|---------|--------------|
| `/help` | 顯示所有命令 |
| `/new` | 開始新對話 |
| `/undo [<id>]` | 復原變更（含 diff 預覽 + 確認） |
| `/checkpoints` | 瀏覽所有快照 — diff、刪除、選擇性恢復 |
| `/search <關鍵詞>` | 全文搜尋聊天歷史 |
| `/stream <訊息>` | 即時流式檢視回覆 |
| `/save` / `/load` | 儲存和恢復會話 |

### 安全與控制

| 命令 | 作用 |
|---------|--------------|
| `/mode ask` | 破壞性操作前詢問（推薦） |
| `/mode auto` | 自動核准安全操作 |
| `/permissions` | 檢視和管理權限規則 |
| `/plan <任務>` | 先看方案再執行 |
| `/config reload` | 熱重載磁碟配置（無需重啟） |
| `/config key=value` | 即時修改設定 |

### 進階功能

| 命令 | 作用 |
|---------|--------------|
| `/repomap` | 生成程式碼庫結構圖譜 |
| `/fork` | 分叉對話，探索不同方案 |
| `/goal <目標>` | 自主迴圈 — 迭代直到目標達成 |
| `/wfd <目標> <模式>` | 啟動多代理動態工作流 |
| `/bg <任務>` | 投遞即忘的後台任務 |
| `/tasks list` | 監控所有後台任務（peek、cancel） |
| `/auto <任務>` | 提交後台自主任務 |
| `/benchmark` | 執行評測套件 |
| `/sync-export` | 匯出記憶到其他裝置 |

---

## 啟動 WebUI

```bash
terry webui                    # → http://127.0.0.1:8670
terry webui --port 9000        # 自訂連接埠
terry webui --host 0.0.0.0    # 允許區域網路存取
```

WebUI 提供完整聊天介面：暗色主題、會話管理、流式回應、PWA 支援（可加入手機主畫面，像原生 App 一樣使用）。

## 連接訊息平台

```python
# Telegram：在手機上透過 Bot 和 Terry 對話
from terry.server.gateways.telegram_gateway import TelegramGateway
TelegramGateway(token="...", agent_factory=lambda: agent).start_polling()

# Discord：把 Terry 帶到團隊伺服器
from terry.server.gateways.discord_gateway import DiscordGateway
DiscordGateway(token="...", agent_factory=lambda: agent).start_polling()
```

---

## 支援的 LLM 提供商

| 提供商 | 設定方式 | 最適合 |
|----------|-------|----------|
| **Anthropic Claude** | `export ANTHROPIC_API_KEY=...` | 複雜推理、大型程式碼庫 |
| **OpenAI GPT-4o** | `export OPENAI_API_KEY=...` | 通用任務 |
| **DeepSeek** | `export DEEPSEEK_API_KEY=...` | 高性價比程式開發 |
| **智譜 GLM** | `export ZHIPU_API_KEY=...` | 中文場景支援 |
| **通義千問** | `export DASHSCOPE_API_KEY=...` | 有競爭力的效能 |
| **Ollama（本機）** | `ollama pull llama3` | 完全離線、零成本 |

需要其他提供商？新增 8 行設定即可——參考 [adapter.py](terry/core/adapter.py)。

---

## 架構一覽

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
        │  Agent (ReAct)  │  ← 規劃、路由到 LLM、執行工具
        └────────┬────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    ▼            ▼            ▼              ▼
┌───────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
│24     │ │4 級     │ │檢查點    │ │動態工作      │
│工具   │ │安全     │ │和回滾    │ │流引擎 (6)    │
└───────┘ └─────────┘ └──────────┘ └──────────────┘
```

- **98 個核心模組**，職責清晰
- **6 種互動介面** — CLI、WebUI、桌面、PWA、Telegram、Discord
- **710 個測試** — pytest + 依賴注入

---


## 分發方式

| 方式 | 命令 | 平台 |
|--------|---------|----------|
| **PyPI** | `pip install terry-agent` | 全平台 (x86_64 + arm64) |
| **Docker** | `docker compose up` | 全平台 |
| **containerd** | `nerdctl compose up` | Linux 伺服器 |
| **Kubernetes** | `kubectl apply -f deploy/kubernetes/terry.yaml` | 叢集 |
| **Homebrew** | `brew install terry` | macOS |
| **原始碼** | `pip install -e .` | Python 3.12+ |

### 支援的架構

| 架構 | 平台 | 狀態 |
|-------------|----------|--------|
| **x86_64 (amd64)** | Intel/AMD 伺服器、雲端虛擬機 | ✅ |
| **aarch64 (arm64)** | Apple Silicon M1-M4、AWS Graviton、樹莓派 5 | ✅ |
| **armv7** | 樹莓派 3 | ✅ |

### 行動端 App

| 平台 | 方法 | 安裝 |
|----------|--------|---------|
| **Android** | PWA → APK (Bubblewrap TWA) | `bubblewrap build` |
| **iOS** | PWA → 加入主畫面 | Safari → 分享 → 加入 |
| **雙平台** | Telegram Bot | `/start` 在 Telegram 中 |


## 文件

- **[INSTALL.md](INSTALL.md)** — macOS、Linux、Windows 詳細安裝指南
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — 如何貢獻工具、技能或修復
- **[CHANGELOG.md](CHANGELOG.md)** — 每個版本的變更記錄
- **[docs/skills/README.md](docs/skills/README.md)** — 建立自訂技能
- **[RUNTIME_SECURITY.md](RUNTIME_SECURITY.md)** — 生產部署安全功能

---

## 參與貢獻

```bash
git clone https://github.com/YOUR_USERNAME/haha_terry.git
git checkout -b feat/my-cool-tool
# 新增你的工具：繼承 BaseTool，在 discover_tools() 中匯入
pip install -e ".[dev]"
python -m pytest tests/ -v
# 提交 PR！
```

詳見 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 授權條款

Terry 基於 **MIT 授權條款** 發布。

Copyright (c) 2026 Terry Contributors

```
版權所有 (c) 2026 Terry Contributors

特此免費授予任何取得本軟體及相關文件檔案（"軟體"）副本的人
不受限制地處理本軟體的權利，包括但不限於使用、複製、修改、
合併、發布、分發、再授權和/或銷售本軟體副本的權利...
```

完整授權文字：[LICENSE](LICENSE)

**署名聲明：** "Terry" 名稱及其標識為 Terry Contributors 的商標。其他商標均為其各自所有者的財產。

### 第三方依賴授權

Terry 依賴以下開源套件（均為 MIT 或 Apache 2.0）：

| 套件 | 授權 | 用途 |
|---------|---------|-------|
| anthropic | MIT | Anthropic Claude SDK |
| openai | Apache 2.0 | OpenAI 及相容提供商 |
| httpx | BSD | HTTP 客戶端 |
| rich | MIT | 終端 UI |
| typer | MIT | CLI 框架 |
| pyyaml | MIT | YAML 解析 |
| tiktoken | MIT | Token 計數 |
| python-dotenv | BSD | 環境變數載入 |

### 貢獻授權

向 Terry 貢獻程式碼即表示您同意您的貢獻將基於 MIT 授權條款發布。詳見 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

<p align="center">
  <sub>用 ❤️ 構建，來自 Terry 社群 · <a href="#terry-">回到頂部 ↑</a></sub>
</p>
