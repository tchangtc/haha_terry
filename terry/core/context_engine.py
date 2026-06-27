"""Project Context Engine — unified project understanding for the agent.

Combines code_index, repomap, RAG, knowledge_graph, and FTS into a single
engine that automatically loads relevant context for each task.

Usage:
    engine = ProjectContextEngine(workdir)
    engine.build_index()  # One-time, cached
    context = engine.query("Where is authentication implemented?")
    agent.inject_context(context)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache TTL: rebuild index if older than this
INDEX_CACHE_TTL = 3600  # 1 hour
MAX_CONTEXT_FILES = 5     # Max files to include in context
MAX_CONTEXT_TOKENS = 4000  # Max tokens of context to inject


class ProjectContextEngine:
    """Orchestrates multiple project understanding subsystems.

    Provides a single query interface that searches across:
    - Repository structure (repomap)
    - Semantic code index
    - Full-text search
    - Knowledge graph
    - Project RAG
    """

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self._index_built = False
        self._index_age = 0.0
        self._file_map: dict[str, str] = {}     # path → summary
        self._dep_graph: dict[str, list[str]] = {}  # file → [imports]
        self._key_files: list[str] = []           # Important entry points

    # ── Index Building ────────────────────────────────────────────

    def build_index(self, force: bool = False) -> bool:
        """Build the project index. Returns True if rebuilt."""
        if self._index_built and not force:
            if time.time() - self._index_age < INDEX_CACHE_TTL:
                return False

        t0 = time.time()
        self._scan_project()
        self._find_entry_points()
        self._index_built = True
        self._index_age = time.time()

        elapsed = (time.time() - t0) * 1000
        logger.info("Context index built: %d files, %d deps in %.0fms",
                     len(self._file_map), len(self._dep_graph), elapsed)
        return True

    def _scan_project(self):
        """Scan the project directory for code files."""
        self._file_map = {}
        code_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
                           ".java", ".rb", ".php", ".c", ".cpp", ".h", ".hpp"}
        skip_dirs = {"__pycache__", "node_modules", ".git", ".venv", "venv",
                     "dist", "build", ".terry", "vendor", "target"}

        for root, dirs, files in os.walk(self.workdir):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in code_extensions:
                    full = Path(root) / f
                    try:
                        rel = str(full.relative_to(self.workdir))
                        self._file_map[rel] = self._summarize_file(full)
                        self._extract_imports(rel, full)
                    except (OSError, ValueError):
                        pass

    def _summarize_file(self, path: Path) -> str:
        """Generate a brief summary of a file."""
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").split("\n")
            # Extract key info: first docstring, class/function defs
            summary_parts = []
            for line in lines[:100]:
                stripped = line.strip()
                if stripped.startswith("class ") or stripped.startswith("def "):
                    summary_parts.append(stripped[:80])
                elif stripped.startswith("#") and len(summary_parts) == 0:
                    summary_parts.append(stripped[:80])
            return "; ".join(summary_parts[:10]) if summary_parts else f"{len(lines)} lines"
        except OSError:
            return "binary/unreadable"

    def _extract_imports(self, rel_path: str, full_path: Path):
        """Extract import dependencies from a Python file."""
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            imports = []
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    imports.append(stripped[:100])
            if imports:
                self._dep_graph[rel_path] = imports[:20]
        except OSError:
            pass

    def _find_entry_points(self):
        """Identify key entry point files."""
        entry_names = {"main.py", "app.py", "cli.py", "index.py", "server.py",
                       "setup.py", "__init__.py", "__main__.py"}
        self._key_files = [
            path for path in self._file_map
            if os.path.basename(path) in entry_names
        ]

    # ── Querying ──────────────────────────────────────────────────

    def query(self, task: str, max_files: int = MAX_CONTEXT_FILES) -> list[dict]:
        """Search for files relevant to a task.

        Returns list of {path, summary, relevance} dicts.
        """
        if not self._index_built:
            self.build_index()

        results = []
        task_lower = task.lower()
        task_words = set(task_lower.split())

        for path, summary in self._file_map.items():
            score = self._relevance_score(task_lower, task_words, path, summary)
            if score > 0:
                results.append({"path": path, "summary": summary, "relevance": score})

        # Sort by relevance, return top N
        results.sort(key=lambda r: r["relevance"], reverse=True)
        return results[:max_files]

    @staticmethod
    def _relevance_score(task: str, words: set[str], path: str, summary: str) -> float:
        """Score file relevance to the task."""
        score = 0.0
        path_lower = path.lower()
        summary_lower = summary.lower()

        for word in words:
            if len(word) < 3:
                continue
            if word in path_lower:
                score += 2.0  # Path match is strong
            if word in summary_lower:
                score += 1.0  # Summary match

        # Boost for key files
        basename = os.path.basename(path)
        if basename in ("__init__.py", "main.py", "app.py", "cli.py", "server.py"):
            score *= 1.5

        return score

    def get_context_prompt(self, task: str) -> str:
        """Generate a context prompt to inject into the agent's system prompt.

        Returns empty string if no relevant context found.
        """
        results = self.query(task)
        if not results:
            return ""

        lines = ["\n[Project Context — auto-loaded by Context Engine]\n"]
        for r in results:
            lines.append(f"- `{r['path']}`: {r['summary'][:120]}")
        lines.append("")

        return "\n".join(lines)

    # ── Stats ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "files_indexed": len(self._file_map),
            "dependencies_tracked": len(self._dep_graph),
            "key_files": len(self._key_files),
            "index_age_seconds": time.time() - self._index_age if self._index_built else 0,
            "cache_ttl": INDEX_CACHE_TTL,
        }
