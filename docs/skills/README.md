# Terry Skills

[English](./README.md) | [简体中文](./README_zh-CN.md) | [繁體中文](./README_zh-TW.md)

Skills are reusable instruction sets that teach Terry specialized workflows. Think of them as "onboarding guides" — when a skill is active, Terry automatically follows domain-specific best practices without you having to explain the steps every time.

---

## Quick Start

Want to create a skill? Here's the minimal example:

```bash
mkdir -p ~/.terry/skills/my-reviewer

cat > ~/.terry/skills/my-reviewer/SKILL.md << 'EOF'
---
name: my-reviewer
description: Quick code sanity check before commit
triggers:
  - pre-commit check
  - 提交前检查
---

# Pre-Commit Reviewer

## Process

1. Read the changed files with `git diff --name-only`
2. For each file, check for:
   - Debug prints or console.log statements
   - Hardcoded credentials or API keys
   - Missing type hints or docstrings
3. Report any issues found. If clean, confirm "Ready to commit."

## Tools

- `git_diff` — See what changed
- `read_file` — Inspect changed files
- `grep` — Search for debug statements
EOF

# Reload and activate
/reload-skills
pre-commit check
```

That's it. A folder with a `SKILL.md` file, a YAML header, and instructions in Markdown.

---

## How It Works

```
User types a message
        │
        ▼
Terry scans all skill triggers
        │
   ┌────┴────┐
   ▼         ▼
 Match?     No match?
   │         │
   ▼         ▼
Inject      Normal
skill       agent
context     behavior
```

When a trigger word matches, Terry injects the skill's instructions into the system prompt. The LLM sees these instructions as its "standard operating procedure" for that task.

**Key point:** Skills don't replace tools — they guide *how* tools are used. A `code-review` skill doesn't add new tools; it tells Terry *which* tools to use, *in what order*, and *what to look for*.

---

## SKILL.md Format

```markdown
---
name: my-skill           # Required: unique ID (lowercase, hyphens)
description: What it does # Required: one-line summary
triggers:                # Required: phrases that activate this skill
  - trigger phrase
  - 中文触发词
---

# Skill Title

Instructions here — any Markdown is valid.

## Process

Step-by-step workflow the agent should follow.

## Tools

List of tools the agent should use, with brief rationale.

## Guidelines

Best practices and constraints for this workflow.
```

### Trigger Matching

Terry matches triggers in this order:

1. **Exact substring** — user message contains the trigger phrase
2. **Name match** — user message contains the skill name
3. **Description match** — user message overlaps with skill description

Example: typing `"review this code"` matches the `code-review` skill because `"review code"` is one of its triggers.

---

## Built-in Skills

Terry ships with three skills to get you started:

### `code-review`

Systematic code review covering security, performance, maintainability, and best practices. Produces a structured report with severity-ranked findings.

**Triggers:** `code review`, `review code`, `代码审查`, `审查代码`

### `data-analysis`

Analyze data files (CSV, JSON, logs). Performs statistical analysis, trend detection, and suggests visualizations.

**Triggers:** `data analysis`, `analyze data`, `数据分析`, `分析数据`

### `document-generator`

Generate professional documents — technical reports, project proposals, API docs, user guides — with proper structure and formatting.

**Triggers:** `generate document`, `create report`, `生成文档`, `创建报告`

---

## Creating Great Skills

### 1. Write good triggers

**Good** — specific, unambiguous:
```yaml
triggers:
  - code review
  - review my code
  - 代码审查
```

**Avoid** — too generic, will fire constantly:
```yaml
triggers:
  - help
  - check
  - do it
```

### 2. Structure your process

Give the agent a clear sequence:

```markdown
## Process

1. **Understand** — read the relevant files
2. **Analyze** — identify issues or patterns
3. **Act** — apply fixes or generate output
4. **Verify** — confirm the result is correct
```

### 3. Be specific about tools

Don't just list tool names — explain *when* and *why*:

```markdown
## Tools

- `read_file` — Read the target file first to understand its structure
- `grep` — Search for TODO, FIXME, and hardcoded values
- `edit_file` — Apply fixes one at a time, with clear commit messages
```

### 4. Include examples

Concrete examples help the LLM understand expected behavior:

```markdown
## Example

**Input:** "Review auth.py"

**Output:**
1. Found: SQL injection risk at line 45
2. Warning: Missing rate limiting on login endpoint
3. Suggestion: Extract JWT logic into separate module
```

---

## Managing Skills

```bash
/skills              # List all installed skills
/skill <name>        # Show skill details and content
/activate <name>     # Manually activate a skill
/deactivate          # Deactivate current skill
/reload-skills       # Reload all skills from disk
/auto-skills         # View auto-generated skills (from conversation patterns)
/auto-skill-approve  # Promote an auto-generated skill to permanent
```

---

## Auto-Created Skills

Terry watches for repeated workflows in your conversations. After it detects the same pattern multiple times, it proposes a reusable skill:

```
You: "Find all SQL queries in this project and check for injection risks"
Terry: [searches, finds issues, reports them]

... a few conversations later ...

You: "Audit the new API endpoints for security issues"
Terry: [searches, finds issues, reports them]

Terry: "I notice you frequently run security audits. I've drafted a skill for this — review it with /auto-skills"
```

This means Terry's skill library grows with your usage patterns.

---

## Skill Directories

Terry loads skills from (in priority order):

1. `./skills/` — Project-specific skills (committed with your repo)
2. `~/.terry/skills/` — Personal skills (available across all projects)

---

## Troubleshooting

**Skill doesn't appear in `/skills`**
- Check `SKILL.md` has valid YAML frontmatter with `---` delimiters
- Verify `name`, `description`, and `triggers` are all present
- Run `/reload-skills`

**Skill doesn't activate automatically**
- Make sure your trigger phrase appears in the user message
- Add more trigger variations (include both English and Chinese if needed)
- Use `/activate <name>` to test manually

**Skill produces unexpected results**
- Check the skill instructions for ambiguity
- Add more specific examples to guide the LLM
- Review the process steps — are they in the right order?
