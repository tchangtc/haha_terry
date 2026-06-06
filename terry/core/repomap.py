"""Repo-map generator - creates a structured overview of the codebase."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class RepoMapGenerator:
    """Generates a structured map of the codebase for agent context.

    Creates a text representation of the project structure including
    key symbols (classes, functions), their signatures, and relationships.
    """

    IGNORE_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "dist", "build", "*.egg-info",
    }

    IGNORE_FILES = {
        ".DS_Store", "Thumbs.db",
    }

    MAX_FILES = 100

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def generate_map(self, max_files: int = 100) -> str:
        """Generate a repo map as a text outline.

        Returns:
            Markdown-formatted repo map
        """
        files = self._collect_files(max_files)
        structure = self._build_tree(files)
        symbols = self._extract_symbols(files)

        lines = [
            f"# Repo Map: {self.workdir.name}",
            f"Path: {self.workdir}",
            f"Files indexed: {len(files)}",
            "",
            "## Directory Structure",
            "```",
            structure,
            "```",
        ]

        if symbols:
            lines.extend([
                "",
                "## Key Symbols",
            ])
            for sig in symbols[:100]:
                lines.append(f"- `{sig['type']}` **{sig['name']}** → `{sig['file']}:{sig['line']}`")
                if sig.get("signature"):
                    lines.append(f"  ```\n  {sig['signature']}\n  ```")

        return "\n".join(lines)

    def _collect_files(self, max_files: int) -> list[Path]:
        """Collect code files, excluding ignored dirs/files."""
        files = []
        for path in self.workdir.rglob("*"):
            if len(files) >= max_files:
                break
            if not path.is_file():
                continue
            if path.name in self.IGNORE_FILES:
                continue
            # Skip ignored directories
            parts = set(path.relative_to(self.workdir).parts)
            if parts & self.IGNORE_DIRS:
                continue
            # Only include text/code files
            if self._is_code_file(path):
                files.append(path)
        return sorted(files)[:max_files]

    def _is_code_file(self, path: Path) -> bool:
        """Check if a file is a code file worth indexing."""
        code_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
            ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
            ".rb", ".php", ".cs", ".scala", ".clj", ".ex", ".exs",
            ".md", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini",
            ".sh", ".bash", ".zsh", ".fish",
            ".sql", ".r", ".jl", ".lua", ".dart",
        }
        return path.suffix.lower() in code_extensions

    def _build_tree(self, files: list[Path]) -> str:
        """Build a directory tree representation."""
        tree: dict[str, Any] = {}
        for f in files:
            try:
                rel = f.relative_to(self.workdir)
            except ValueError:
                rel = f
            parts = rel.parts
            current = tree
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = f  # Store full path

        def render(node: dict, indent: int = 0) -> list[str]:
            lines = []
            prefix = "  " * indent
            # Sort: dirs first, then files
            items = sorted(node.items(), key=lambda x: (
                not isinstance(x[1], dict),
                x[0].lower(),
            ))
            for name, value in items:
                if isinstance(value, dict):
                    lines.append(f"{prefix}{name}/")
                    lines.extend(render(value, indent + 1))
                else:
                    size = ""
                    try:
                        size = f" ({value.stat().st_size} bytes)"
                    except Exception:
                        pass
                    lines.append(f"{prefix}{name}{size}")
            return lines

        return "\n".join(render(tree))

    def _extract_symbols(self, files: list[Path]) -> list[dict[str, Any]]:
        """Extract key symbols from source files.

        Currently supports Python files with AST parsing.
        """
        symbols = []
        for file_path in files:
            if file_path.suffix != ".py":
                continue
            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                rel_path = file_path.relative_to(self.workdir)

                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.FunctionDef):
                        params = [a.arg for a in node.args.args]
                        sig = f"def {node.name}({', '.join(params)})"
                        symbols.append({
                            "type": "function",
                            "name": node.name,
                            "file": str(rel_path),
                            "line": node.lineno,
                            "signature": sig,
                        })
                    elif isinstance(node, ast.ClassDef):
                        methods = [
                            n.name for n in ast.iter_child_nodes(node)
                            if isinstance(n, ast.FunctionDef)
                        ]
                        sig = f"class {node.name}"
                        if methods:
                            sig += f" ({len(methods)} methods: {', '.join(methods[:5])}{'...' if len(methods) > 5 else ''})"
                        symbols.append({
                            "type": "class",
                            "name": node.name,
                            "file": str(rel_path),
                            "line": node.lineno,
                            "signature": sig,
                        })
            except (SyntaxError, UnicodeDecodeError, Exception):
                continue

        return sorted(symbols, key=lambda s: (s["type"], s["name"]))

    def find_symbol(self, name: str) -> list[dict[str, Any]]:
        """Find a symbol by name in the codebase.

        Args:
            name: Symbol name to search for

        Returns:
            List of matching symbols with file and line info
        """
        files = self._collect_files(200)
        symbols = self._extract_symbols(files)
        return [s for s in symbols if name.lower() in s["name"].lower()]

    def save_map(self, path: Path | None = None) -> Path:
        """Save the repo map to disk."""
        if path is None:
            path = self.workdir / ".terry" / "repo_map.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        map_content = self.generate_map()
        path.write_text(map_content, encoding="utf-8")
        return path
