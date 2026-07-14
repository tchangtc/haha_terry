"""Regression guard against documentation drift.

These tests recompute the project's real metrics (tool count, CLI command
count, module count, version) from source and assert that the numbers claimed
in CLAUDE.md and the trilingual READMEs still match. When code changes the
counts, the test fails and forces the docs to be updated in the same commit —
which is exactly the drift this suite exists to prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── actual metrics, computed from source ─────────────────────────────


def _actual_tool_count() -> int:
    """Tools available to a running Agent: auto-registered + agent-bound."""
    import terry.tools as tools_pkg
    from terry.tools import slash_command, task_update

    tools_pkg.discover_tools()
    # These two need an agent reference, so they self-register lazily.
    task_update.register(agent=None)
    slash_command.register(agent=None)
    return len(tools_pkg.tool_registry.list_tools())


def _actual_cli_command_count() -> int:
    src = _read("terry/cli_commands.py")
    calls = len(re.findall(r"register_cli_command\(", src))
    return calls - src.count("def register_cli_command")


def _actual_module_count() -> int:
    return sum(
        1
        for p in (ROOT / "terry").rglob("*.py")
        if "__pycache__" not in p.parts
    )


# ── CLAUDE.md header claims ──────────────────────────────────────────


def _claude_header() -> str:
    for line in _read("CLAUDE.md").splitlines():
        if "Version:" in line and "modules" in line:
            return line
    raise AssertionError("CLAUDE.md version/metrics header line not found")


def _claim(header: str, unit: str) -> int:
    m = re.search(rf"(\d[\d,]*)\s+{unit}", header)
    assert m, f"could not find '<N> {unit}' in CLAUDE.md header"
    return int(m.group(1).replace(",", ""))


class TestClaudeMdMetrics:
    def test_tool_count_matches(self):
        assert _claim(_claude_header(), "tools") == _actual_tool_count()

    def test_cli_command_count_matches(self):
        assert _claim(_claude_header(), "CLI commands") == _actual_cli_command_count()

    def test_module_count_matches(self):
        assert _claim(_claude_header(), "modules") == _actual_module_count()


class TestVersionConsistency:
    def test_init_matches_pyproject(self):
        from terry import __version__

        m = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.MULTILINE)
        assert m, "version not found in pyproject.toml"
        assert __version__ == m.group(1)

    def test_claude_header_version_matches(self):
        from terry import __version__

        m = re.search(r"Version:\s*\*\*v([0-9][^\s*]*)", _claude_header())
        assert m, "version not found in CLAUDE.md header"
        assert m.group(1) == __version__


class TestReadmeTrilingualSync:
    """The three READMEs must claim the same tool count as each other."""

    PATTERNS = {
        "README.md": r"Rich Tool Set \((\d+) tools\)",
        "README_zh-CN.md": r"###\s*🛠️\s*(\d+)\s*个内置工具",
        "README_zh-TW.md": r"###\s*🛠️\s*(\d+)\s*個內建工具",
    }

    def _readme_counts(self) -> dict[str, int]:
        counts = {}
        for fname, pat in self.PATTERNS.items():
            m = re.search(pat, _read(fname))
            assert m, f"tool-count header not found in {fname}"
            counts[fname] = int(m.group(1))
        return counts

    def test_all_readmes_agree(self):
        counts = self._readme_counts()
        assert len(set(counts.values())) == 1, f"README tool counts diverge: {counts}"

    def test_readmes_match_actual_tool_count(self):
        counts = self._readme_counts()
        assert next(iter(counts.values())) == _actual_tool_count()


class TestReadmeBadges:
    """Shields.io badges in every README must track real code metrics.

    This is the exact drift class that slipped through before: the tool-set
    header was fixed while the ``tools-NN`` / ``CLI-NN`` badges stayed stale.
    """

    READMES = ("README.md", "README_zh-CN.md", "README_zh-TW.md")

    def _badge(self, text: str, key: str) -> int | str:
        m = re.search(rf"badge/{key}-([0-9.]+?)-", text)
        assert m, f"badge '{key}' not found"
        val = m.group(1)
        return val if key == "version" else int(val)

    def test_version_badge_matches(self):
        from terry import __version__

        for fname in self.READMES:
            assert self._badge(_read(fname), "version") == __version__, fname

    def test_tools_badge_matches(self):
        actual = _actual_tool_count()
        for fname in self.READMES:
            assert self._badge(_read(fname), "tools") == actual, fname

    def test_cli_badge_matches(self):
        actual = _actual_cli_command_count()
        for fname in self.READMES:
            assert self._badge(_read(fname), "CLI") == actual, fname


def _news_versions(fname: str) -> list[tuple[int, int, int]]:
    """Ordered (major, minor, patch) tuples of the ``## 📰 News`` entries."""
    text = _read(fname)
    start = text.index("📰")
    rest = text[start:]
    end = re.search(r"\n## ", rest)
    section = rest[: end.start()] if end else rest
    return [
        tuple(int(x) for x in m.split("."))
        for m in re.findall(r"\*\*v(\d+\.\d+\.\d+)\*\*", section)
    ]


class TestNewsVersionRules:
    """Guard the News-section conventions the project relies on."""

    READMES = ("README.md", "README_zh-CN.md", "README_zh-TW.md")

    def test_trilingual_news_sequences_identical(self):
        seqs = {f: _news_versions(f) for f in self.READMES}
        assert len({tuple(v) for v in seqs.values()}) == 1, (
            f"News version order diverges across languages: "
            f"{ {f: [f'{a}.{b}.{c}' for a, b, c in v] for f, v in seqs.items()} }"
        )

    def test_news_strictly_descending(self):
        for fname in self.READMES:
            v = _news_versions(fname)
            assert all(v[i] > v[i + 1] for i in range(len(v) - 1)), f"{fname} not descending"

    def test_news_is_minor_plus_only(self):
        # Convention: News lists Minor+ releases only; patch (X.Y.Z, Z>0) stays in CHANGELOG.
        for fname in self.READMES:
            patches = [f"{a}.{b}.{c}" for a, b, c in _news_versions(fname) if c != 0]
            assert not patches, f"{fname} News contains patch releases: {patches}"

    def test_newest_news_entry_is_current_version(self):
        from terry import __version__

        for fname in self.READMES:
            newest = _news_versions(fname)[0]
            assert ".".join(map(str, newest)) == __version__, fname
