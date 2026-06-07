# 跨平台安装指南 / Cross-Platform Installation Guide

## 支持的平台 / Supported Platforms

### ✅ 完全支持 / Fully Supported
- **Windows 10/11** (64-bit)
- **macOS** 10.15+ (Intel & Apple Silicon)
- **Linux** (Ubuntu 20.04+, Debian 11+, Fedora 35+, Arch Linux)

### ⚠️ 有限支持 / Limited Support
- **Android** (via Termux) - 命令行版本可用，部分功能受限
- **iOS** (via Pythonista/iSH) - 实验性支持，功能受限

### ❌ 不支持 / Not Supported
- 原生移动应用 (Native mobile apps)
- Windows 32-bit
- Windows 7/8

---

## Windows 安装 / Windows Installation

### 方法 1: 使用 uv (推荐)

```powershell
# 1. 安装 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 克隆仓库
git clone https://github.com/tchangtc/haha_terry.git
cd terry

# 3. 创建虚拟环境
uv venv tc_terry

# 4. 激活虚拟环境
.\tc_terry\Scripts\Activate.ps1

# 5. 安装依赖
uv pip install -e .

# 6. 配置 API 密钥
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# 7. 运行 Terry
terry
```

### 方法 2: 使用 pip

```powershell
# 1. 安装 Python 3.12+
# 从 https://python.org 下载并安装

# 2. 克隆仓库
git clone https://github.com/tchangtc/haha_terry.git
cd terry

# 3. 创建虚拟环境
python -m venv tc_terry

# 4. 激活虚拟环境
.\tc_terry\Scripts\activate.bat

# 5. 安装依赖
pip install -e .

# 6. 配置 API 密钥
set ANTHROPIC_API_KEY=sk-ant-...

# 7. 运行 Terry
terry
```

---

## macOS 安装 / macOS Installation

### 方法 1: 使用 uv (推荐)

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆仓库
git clone https://github.com/tchangtc/haha_terry.git
cd terry

# 3. 创建虚拟环境
uv venv tc_terry

# 4. 激活虚拟环境
source tc_terry/bin/activate

# 5. 安装依赖
uv pip install -e .

# 6. 配置 API 密钥
export ANTHROPIC_API_KEY="sk-ant-..."

# 7. 运行 Terry
terry
```

### Apple Silicon (M1/M2/M3) 特别说明

Terry 完全支持 Apple Silicon，无需额外配置。如果遇到性能问题：

```bash
# 确保使用 ARM64 版本的 Python
python -c "import platform; print(platform.machine())"
# 应该输出: arm64
```

---

## Linux 安装 / Linux Installation

### 方法 1: 使用 uv (推荐)

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆仓库
git clone https://github.com/tchangtc/haha_terry.git
cd terry

# 3. 创建虚拟环境
uv venv tc_terry

# 4. 激活虚拟环境
source tc_terry/bin/activate

# 5. 安装依赖
uv pip install -e .

# 6. 配置 API 密钥
export ANTHROPIC_API_KEY="sk-ant-..."

# 7. 运行 Terry
terry
```

### Ubuntu/Debian 额外依赖

```bash
# 安装 Python 3.12+ 和开发工具
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip git
```

### Fedora 额外依赖

```bash
# 安装 Python 3.12+ 和开发工具
sudo dnf install python3.12 python3-pip git
```

---

## Android 安装 (Termux) / Android Installation (Termux)

⚠️ **注意**: Android 支持是实验性的，部分功能可能受限

### 前提条件
- 安装 [Termux](https://termux.dev/) (从 F-Droid 或 GitHub，不要用 Play Store 版本)
- 至少 2GB 可用存储空间

### 安装步骤

```bash
# 1. 更新 Termux
pkg update && pkg upgrade

# 2. 安装 Python 和 Git
pkg install python git

# 3. 安装 uv
pip install uv

# 4. 克隆仓库
git clone https://github.com/tchangtc/haha_terry.git
cd terry

# 5. 创建虚拟环境
uv venv tc_terry

# 6. 激活虚拟环境
source tc_terry/bin/activate

# 7. 安装依赖
uv pip install -e .

# 8. 配置 API 密钥
export ANTHROPIC_API_KEY="sk-ant-..."

# 9. 运行 Terry
terry
```

### Android 限制 / Android Limitations

1. **bash 工具**: 使用 Termux 的 shell，功能有限
2. **文件系统访问**: 受限于 Termux 沙箱
3. **性能**: 移动设备性能较低，LLM 调用可能较慢
4. **网络**: 需要稳定的网络连接

---

## iOS 安装 / iOS Installation

⚠️ **警告**: iOS 支持是实验性的，不推荐生产使用

### 方法 1: Pythonista (付费应用)

1. 从 App Store 安装 [Pythonista 3](https://apps.apple.com/app/pythonista-3/id1085978097)
2. 使用内置的 pip 安装依赖:
   ```python
   import pip
   pip.main(['install', 'anthropic', 'openai', 'typer', 'rich'])
   ```
3. 手动复制 Terry 代码到 Pythonista
4. 在 Pythonista 中运行

### 方法 2: iSH (免费，基于 Alpine Linux)

1. 从 App Store 安装 [iSH](https://ish.app/)
2. 在 iSH 中:
   ```sh
   apk add python3 git
   git clone https://github.com/tchangtc/haha_terry.git
   cd terry
   pip3 install -e .
   ```

### iOS 限制 / iOS Limitations

1. **后台运行**: iOS 会限制后台应用
2. **文件系统**: 严重受限，无法访问系统文件
3. **bash 工具**: 可能完全不可用
4. **性能**: 性能较差，不适合长时间使用
5. **网络**: 后台网络请求可能被中断

---

## 跨平台配置路径 / Cross-Platform Configuration Paths

Terry 使用平台特定的配置目录：

| 平台 | 配置目录 | 数据目录 | 缓存目录 |
|------|---------|---------|---------|
| **Windows** | `%APPDATA%\terry` | `%LOCALAPPDATA%\terry` | `%LOCALAPPDATA%\terry\cache` |
| **macOS** | `~/Library/Application Support/terry` | `~/Library/Application Support/terry` | `~/Library/Caches/terry` |
| **Linux** | `~/.config/terry` | `~/.local/share/terry` | `~/.cache/terry` |
| **Android** | `~/.config/terry` | `~/.local/share/terry` | `~/.cache/terry` |
| **iOS** | `~/.config/terry` | `~/.local/share/terry` | `~/.cache/terry` |

---

## 故障排除 / Troubleshooting

### Windows 问题

**问题**: `terry` 命令未找到
```powershell
# 解决: 添加到 PATH
$env:Path += ";$PWD\tc_terry\Scripts"
```

**问题**: PowerShell 执行策略阻止脚本
```powershell
# 解决: 修改执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### macOS 问题

**问题**: "terry" cannot be opened because the developer cannot be verified
```bash
# 解决: 移除隔离属性
xattr -d com.apple.quarantine tc_terry/bin/terry
```

### Linux 问题

**问题**: Permission denied
```bash
# 解决: 添加执行权限
chmod +x tc_terry/bin/terry
```

### Android/iOS 问题

**问题**: 性能很慢
- 解决: 这是移动设备的正常现象，考虑使用桌面版本

**问题**: 某些工具不可用
- 解决: 移动平台限制，bash 和 grep 工具可能受限

---

## 验证安装 / Verify Installation

运行以下命令验证安装：

```bash
# 检查版本
terry --version

# 检查平台
python -c "from terry.core.platform_utils import get_platform; print(get_platform())"

# 运行测试
python tests/verify_terry.py
```

---

## 下一步 / Next Steps

1. **配置 API 密钥**: 参考 README.md
3. **了解工具**: 在 Terry 中输入 `/tools`
4. **查看示例**: 参考 `examples/` 目录（如果存在）

---

**需要帮助？** 请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 或提交 Issue。
