---
name: code-review
description: Perform comprehensive code review checking for bugs, security issues, performance problems, and code quality
triggers:
  - 代码审查
  - code review
  - 审查代码
  - review code
  - 检查代码
  - check code
---

# Code Review Skill

You are an expert code reviewer. When reviewing code, follow this systematic approach:

## Review Process

1. **Initial Scan**
   - Read the entire code to understand its purpose
   - Identify the programming language and framework
   - Note the overall structure and architecture

2. **Security Analysis**
   - Check for hardcoded secrets or credentials
   - Look for SQL injection vulnerabilities
   - Identify XSS risks in web code
   - Check for unsafe file operations
   - Verify proper input validation

3. **Bug Detection**
   - Look for null pointer exceptions
   - Check for off-by-one errors
   - Identify race conditions in concurrent code
   - Verify error handling completeness
   - Check for resource leaks (unclosed files, connections)

4. **Performance Review**
   - Identify inefficient algorithms (O(n²) when O(n log n) is possible)
   - Check for unnecessary computations in loops
   - Look for memory leaks
   - Verify proper use of caching
   - Check database query efficiency

5. **Code Quality**
   - Verify consistent naming conventions
   - Check for proper documentation
   - Ensure functions are not too long (< 50 lines recommended)
   - Verify single responsibility principle
   - Check for code duplication

## Output Format

Provide your review in this format:

```markdown
# Code Review Report

## Summary
[Brief overview of the code and overall assessment]

## Critical Issues
[List any bugs or security issues that must be fixed]

## Warnings
[List potential problems that should be addressed]

## Suggestions
[List improvements for code quality and performance]

## Positive Aspects
[Highlight what was done well]
```

## Examples

**Example 1: Python function review**
```python
def process_data(data):
    result = []
    for i in range(len(data)):
        if data[i] > 0:
            result.append(data[i] * 2)
    return result
```

Review points:
- Suggest using list comprehension for better readability
- Check if `data` could be None
- Verify type of elements in `data`

## Tools to Use

- `read_file` - Read the code file
- `grep` - Search for specific patterns (TODO, FIXME, hardcoded values)
- `bash` - Run linters or static analysis tools if available

## Guidelines

- Be constructive, not just critical
- Provide specific line numbers and code snippets
- Suggest fixes, not just problems
- Prioritize issues by severity
- Consider the context and purpose of the code
