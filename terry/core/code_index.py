"""Code semantic index - symbol table and reference graph for project-wide code intelligence.

Builds a structured index of classes, functions, imports, and their
relationships for fast cross-file reference lookups.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


class CodeSemanticIndex:
    """Symbol table and reference graph for code intelligence.

    Parses source files to build an index of symbols (classes, functions)
    and their cross-references, enabling "go to definition" and
    "find all references" without an LSP server.
    """

    IGNORE_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    }

    MAX_FILES = 200

    def __init__(self, workdir: Path | None = None, cache_dir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.cache_dir = cache_dir or Path.home() / ".terry" / "index"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.symbols: dict[str, list[dict[str, Any]]] = {}
        self.references: dict[str, list[str]] = {}
        self._built = False

    def build_index(self, force: bool = False) -> int:
        """Build or load the symbol index.

        Returns number of files indexed.
        """
        cache_file = self.cache_dir / "symbol_index.json"

        if not force and cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                self.symbols = data.get("symbols", {})
                self.references = data.get("references", {})
                self._built = True
                return data.get("file_count", 0)
            except Exception:
                pass

        # Collect and parse Python files
        files = self._collect_files()
        for file_path in files:
            self._parse_file(file_path)

        # Save to cache
        cache_file.write_text(
            json.dumps({
                "file_count": len(files),
                "symbols": self.symbols,
                "references": self.references,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self._built = True
        return len(files)

    def _collect_files(self) -> list[Path]:
        """Collect Python files for indexing."""
        files = []
        for path in self.workdir.rglob("*.py"):
            if len(files) >= self.MAX_FILES:
                break
            parts = set(path.relative_to(self.workdir).parts)
            if parts & self.IGNORE_DIRS:
                continue
            files.append(path)
        return sorted(files)[:self.MAX_FILES]

    def _parse_file(self, file_path: Path) -> None:
        """Extract symbols from a Python file."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            rel_path = str(file_path.relative_to(self.workdir))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self._add_symbol(
                        node.name, "function", rel_path,
                        node.lineno, node.col_offset,
                    )
                    # Track references
                    self._track_references(node.name, rel_path, node)

                elif isinstance(node, ast.ClassDef):
                    self._add_symbol(
                        node.name, "class", rel_path,
                        node.lineno, node.col_offset,
                    )
                    self._track_references(node.name, rel_path, node)

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self._add_symbol(
                            alias.asname or alias.name, "import",
                            rel_path, node.lineno, node.col_offset,
                        )

                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        self._add_symbol(
                            name, "import", rel_path,
                            node.lineno, node.col_offset,
                        )
        except (SyntaxError, UnicodeDecodeError, Exception):
            pass

    def _add_symbol(
        self, name: str, kind: str, file: str, line: int, col: int
    ) -> None:
        """Add a symbol to the index."""
        if name not in self.symbols:
            self.symbols[name] = []
        # Avoid duplicates
        exists = any(
            s["file"] == file and s["line"] == line
            for s in self.symbols[name]
        )
        if not exists:
            self.symbols[name].append({
                "kind": kind,
                "file": file,
                "line": line,
                "column": col,
            })

    def _track_references(
        self, name: str, file: str, node: ast.AST
    ) -> None:
        """Track where symbols are referenced."""
        # Simple: track the file where this symbol is defined
        if name not in self.references:
            self.references[name] = []
        if file not in self.references[name]:
            self.references[name].append(file)

    def find_definition(self, symbol: str) -> list[dict[str, Any]]:
        """Find all definitions of a symbol."""
        if not self._built:
            self.build_index()
        return self.symbols.get(symbol, [])

    def find_references(self, symbol: str) -> list[str]:
        """Find files that reference a symbol."""
        if not self._built:
            self.build_index()
        return self.references.get(symbol, [])

    def search(self, query: str) -> list[dict[str, Any]]:
        """Fuzzy search for symbols by name."""
        if not self._built:
            self.build_index()
        results = []
        q = query.lower()
        for name, defs in self.symbols.items():
            if q in name.lower():
                for d in defs:
                    results.append({"name": name, **d})
        return sorted(results[:50], key=lambda r: r["kind"])
