# Terry Skills 文档

## 概述

Skills 是 Terry 的动态指令系统，让 Terry 能够按照特定领域的最佳实践执行任务。Skills 从 Markdown 文件加载，根据用户意图自动匹配和激活。

## 核心概念

### Skill vs Tool

| 特性 | Tools (工具) | Skills (技能) |
|------|-------------|--------------|
| **定义方式** | Python 代码 | Markdown + YAML frontmatter |
| **创建门槛** | 需要编程 | 非程序员也能创建 |
| **加载方式** | 启动时加载 | 按需动态加载 |
| **灵活性** | 固定功能 | 可组合、可迭代 |
| **示例** | `bash`, `read_file` | "代码审查流程"、"数据分析工作流" |
| **可分发性** | 需要安装包 | 复制文件夹即可 |
| **社区共享** | 复杂 | 简单（GitHub 仓库） |

### Skill 文件结构

每个 skill 是一个包含 `SKILL.md` 文件的目录：

```
my-skill/
├── SKILL.md              # 必需：skill 定义
├── examples/             # 可选：示例文件
└── templates/            # 可选：模板文件
```

## SKILL.md 格式

### 基本结构

```markdown
---
name: skill-name
description: Skill 的简短描述
triggers:
  - 触发词1
  - 触发词2
  - trigger word 3
---

# Skill 标题

详细的 skill 指令和工作流程说明。

## 工作流程

1. 第一步
2. 第二步
3. 第三步

## 工具使用

- `tool_name` - 工具用途说明

## 示例

具体的使用示例和预期输出。

## 指南

- 指南1
- 指南2
```

### YAML Frontmatter 字段

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `name` | ✅ | string | Skill 唯一标识符（小写、连字符） |
| `description` | ✅ | string | Skill 功能描述 |
| `triggers` | ✅ | list | 触发词列表（中英文） |

### 触发词匹配

Terry 按以下优先级匹配 skill：

1. **精确触发词匹配** - 用户输入包含 skill 的 trigger 词
2. **Skill 名称匹配** - 用户输入包含 skill 名称
3. **描述匹配** - 用户输入与 skill 描述相似

**示例**：
```
用户输入: "帮我审查这段代码"
匹配到: code-review skill (trigger: "审查代码")
```

## 内置 Skills

### 1. Code Review (代码审查)

**位置**: `skills/code-review/SKILL.md`

**功能**:
- 系统化的代码审查流程
- 检查安全性、性能、可维护性
- 生成结构化审查报告

**触发词**:
- 代码审查、code review
- 审查代码、review code
- 检查代码、check code

**审查维度**:
1. **安全性** - 注入、XSS、敏感信息泄露
2. **性能** - 算法复杂度、内存使用、数据库查询
3. **可维护性** - 代码结构、命名、注释
4. **最佳实践** - 设计模式、SOLID 原则

### 2. Data Analysis (数据分析)

**位置**: `skills/data-analysis/SKILL.md`

**功能**:
- 数据文件分析（CSV、JSON、日志）
- 统计计算和趋势识别
- 生成可视化建议

**触发词**:
- 数据分析、data analysis
- 分析数据、analyze data
- 数据统计、data statistics

**分析流程**:
1. 数据加载和探索
2. 数据清洗和质量检查
3. 统计分析和聚合
4. 趋势识别和异常检测
5. 生成报告和可视化建议

### 3. Document Generator (文档生成)

**位置**: `skills/document-generator/SKILL.md`

**功能**:
- 生成专业文档（报告、提案、文档）
- 提供多种文档模板
- 确保格式和结构规范

**触发词**:
- 生成文档、generate document
- 创建报告、create report
- 写文档、write document

**文档类型**:
- 技术报告
- 项目提案
- API 文档
- 用户指南

## 使用方法

### 自动激活（推荐）

Terry 会根据用户输入自动匹配合适的 skill：

```bash
用户 > 帮我审查这段代码
Terry > [自动激活 code-review skill]
       我将按照以下流程审查代码...
```

### 手动管理

```bash
# 列出所有可用 skills
/skills

# 查看 skill 详情
/skill code-review

# 手动激活 skill
/activate code-review

# 停用当前 skill
/deactivate

# 重新加载 skills（从磁盘）
/reload-skills
```

## 创建自定义 Skill

### 步骤 1: 创建 Skill 目录

```bash
# 全局 skills（所有项目可用）
mkdir -p ~/.terry/skills/my-skill

# 本地 skills（仅当前项目）
mkdir -p ./skills/my-skill
```

### 步骤 2: 创建 SKILL.md

```bash
cat > ~/.terry/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: My custom skill for specialized tasks
triggers:
  - my trigger
  - 我的触发词
  - custom task
---

# My Skill

This skill helps with specialized tasks.

## 工作流程

1. 理解用户需求
2. 使用 `read_file` 读取相关文件
3. 分析内容
4. 生成输出

## 工具使用

- `read_file` - 读取文件
- `write_file` - 写入文件
- `bash` - 执行命令

## 示例

**输入**: "执行我的自定义任务"

**输出**: 
```
[按照 skill 定义的流程执行]
```

## 指南

- 始终保持专业
- 提供清晰的输出
- 遵循最佳实践
EOF
```

### 步骤 3: 重新加载 Skills

在 Terry 中执行：
```bash
/reload-skills
```

### 步骤 4: 使用 Skill

```bash
my trigger
```

## Skill 目录

Terry 从以下目录加载 skills（按优先级）：

1. **当前项目**: `./skills/`
2. **用户全局**: `~/.terry/skills/`

## 高级功能

### 多语言触发词

Skills 支持中英文触发词：

```yaml
triggers:
  - 代码审查
  - code review
  - 审查代码
  - review code
```

### Skill 组合

可以在一个对话中使用多个 skills：

```bash
/activate code-review
# 执行代码审查

/deactivate
/activate data-analysis
# 执行数据分析
```

### Skill 依赖

Skill 可以引用其他 tools：

```markdown
## 工具使用

- `read_file` - 读取代码文件
- `grep` - 搜索特定模式
- `bash` - 运行 linter 或测试
```

## 最佳实践

### 1. 清晰的触发词

✅ **好的触发词**:
```yaml
triggers:
  - 代码审查
  - code review
  - 审查代码
```

❌ **差的触发词**:
```yaml
triggers:
  - 帮我
  - 请
  - help
```

### 2. 结构化的工作流程

✅ **好的工作流程**:
```markdown
## 工作流程

1. **理解需求**
   - 读取用户提供的文件
   - 确认审查范围

2. **执行审查**
   - 检查安全性
   - 检查性能
   - 检查可维护性

3. **生成报告**
   - 总结发现的问题
   - 提供改进建议
```

### 3. 具体的示例

✅ **好的示例**:
```markdown
## 示例

**输入**: "审查这个 Python 函数"
```python
def process_data(data):
    result = []
    for i in range(len(data)):
        if data[i] > 0:
            result.append(data[i] * 2)
    return result
```

**输出**:
```markdown
# Code Review Report

## 问题
1. 可以使用列表推导式提高可读性
2. 缺少类型提示
3. 没有处理 data 为 None 的情况

## 建议
```python
def process_data(data: list[int] | None) -> list[int]:
    if data is None:
        return []
    return [x * 2 for x in data if x > 0]
```
```

### 4. 明确的指南

✅ **好的指南**:
```markdown
## 指南

- 始终保持客观和建设性
- 提供具体的行号和代码片段
- 建议修复方案，而不仅仅指出问题
- 按严重程度优先排序问题
- 考虑代码的上下文和目的
```

## 故障排除

### Skill 未加载

**问题**: `/skills` 不显示我的 skill

**解决**:
1. 检查 SKILL.md 格式是否正确
2. 确认 YAML frontmatter 包含必需字段
3. 执行 `/reload-skills`
4. 检查 skill 目录是否在正确位置

### Skill 未匹配

**问题**: 用户输入没有触发我的 skill

**解决**:
1. 检查触发词是否匹配用户输入
2. 添加更多触发词变体
3. 使用 `/activate skill-name` 手动激活

### Skill 执行错误

**问题**: Skill 执行时出错

**解决**:
1. 检查 skill 内容是否有语法错误
2. 确认引用的 tools 存在
3. 查看 Terry 日志获取详细错误信息

## 参考资源

- [Anthropic Skills Repository](https://github.com/anthropics/skills)
- [What are skills?](https://support.claude.com/en/articles/12512176-what-are-skills)
- [How to create custom skills](https://support.claude.com/en/articles/12512198-creating-custom-skills)
- [Awesome Claude Skills](https://github.com/travisvn/awesome-claude-skills)

## 示例 Skills

### Git 工作流 Skill

```markdown
---
name: git-workflow
description: Manage Git repositories with best practices
triggers:
  - git workflow
  - git 工作流
  - 管理 git
---

# Git Workflow Skill

## 工作流程

1. 检查当前状态 (`git status`)
2. 查看变更 (`git diff`)
3. 创建有意义的提交信息
4. 执行提交 (`git commit`)
5. 推送到远程 (`git push`)

## 指南

- 使用 conventional commits 格式
- 每个提交只做一件事
- 提交信息使用现在时态
- 提交前运行测试
```

### 测试编写 Skill

```markdown
---
name: write-tests
description: Write comprehensive tests for code
triggers:
  - write tests
  - 编写测试
  - 写测试
---

# Test Writing Skill

## 工作流程

1. 理解要测试的代码
2. 识别测试场景（正常、边界、错误）
3. 编写测试用例
4. 运行测试验证

## 测试类型

- **单元测试** - 测试单个函数
- **集成测试** - 测试组件交互
- **端到端测试** - 测试完整流程

## 指南

- 遵循 AAA 模式（Arrange, Act, Assert）
- 测试名称描述行为
- 每个测试只验证一件事
- 覆盖正常和边界情况
```

## 总结

Skills 系统让 Terry 能够：
- ✅ 按专业领域最佳实践执行
- ✅ 非程序员也能扩展 Terry
- ✅ 社区可共享和复用
- ✅ 灵活且易于迭代

开始创建你的第一个 skill 吧！
