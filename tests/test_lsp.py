"""Tests for the LSP client (terry/lsp/__init__.py).

No real language server is launched: ``start()`` paths use a fake process, and
the hover/definition result-parsing branches are exercised by stubbing
``_send_request``. This covers the JSON-RPC framing and the content-shape
handling without depending on pyright being installed.
"""

from __future__ import annotations

import json

from terry.lsp import LSPClient


# ── fakes ───────────────────────────────────────────────────────────


class _FakeStdin:
    def __init__(self) -> None:
        self.written: list[str] = []

    def write(self, s: str) -> int:
        self.written.append(s)
        return len(s)

    def flush(self) -> None:
        pass


class _FakeStdout:
    def __init__(self, lines: list[str] | None = None) -> None:
        self._lines = list(lines or [])

    def readline(self) -> str:
        return self._lines.pop(0) if self._lines else ""

    def read(self, _n: int) -> str:
        return ""


class _FakeProc:
    def __init__(self, stdout_lines: list[str] | None = None) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(stdout_lines)
        self.stderr = _FakeStdout()
        self.terminated = 0

    def terminate(self) -> None:
        self.terminated += 1


# ── construction ────────────────────────────────────────────────────


class TestConstruction:
    def test_defaults(self):
        c = LSPClient()
        assert c.language == "python"
        assert c.root_uri.startswith("file://")
        assert c._process is None
        assert c._initialized is False
        assert c._id_counter == 0

    def test_custom_root_and_language(self):
        c = LSPClient(root_uri="file:///tmp/proj", language="rust")
        assert c.root_uri == "file:///tmp/proj"
        assert c.language == "rust"

    def test_lsp_commands_table(self):
        cmds = LSPClient.LSP_COMMANDS
        assert set(cmds) >= {"python", "typescript", "rust"}
        assert cmds["python"] == ["pyright-langserver", "--stdio"]


# ── start / stop ────────────────────────────────────────────────────


class TestStartStop:
    def test_start_unsupported_language(self):
        assert LSPClient(language="brainfuck").start() is False

    def test_start_binary_not_found(self, monkeypatch):
        c = LSPClient(language="python")

        def fake_popen(*_a, **_k):
            raise FileNotFoundError("no pyright")

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        assert c.start() is False
        assert c._initialized is False

    def test_start_success_writes_initialize(self, monkeypatch):
        c = LSPClient(language="python")
        proc = _FakeProc()
        monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: proc)
        assert c.start() is True
        assert c._initialized is True
        written = "".join(proc.stdin.written)
        assert "Content-Length:" in written
        assert '"method": "initialize"' in written
        assert '"initialized"' in written  # the initialized notification
        assert c.root_uri in written

    def test_stop_when_not_started(self):
        c = LSPClient()
        c.stop()  # no error
        assert c._initialized is False
        assert c._process is None

    def test_stop_terminates_process_and_notifies_exit(self):
        c = LSPClient()
        proc = _FakeProc()
        c._process = proc
        c._initialized = True
        c.stop()
        assert c._process is None
        assert c._initialized is False
        assert proc.terminated == 1
        assert any('"exit"' in w for w in proc.stdin.written)


# ── uninitialized defaults ──────────────────────────────────────────


class TestUninitializedDefaults:
    def test_all_return_empty_or_none(self):
        c = LSPClient()
        assert c.get_diagnostics("x.py") == []
        assert c.get_hover("x.py", 0, 0) is None
        assert c.get_definition("x.py", 0, 0) is None


# ── hover content parsing ───────────────────────────────────────────


class TestHoverParsing:
    def _client(self, monkeypatch, result):
        c = LSPClient()
        c._initialized = True
        monkeypatch.setattr(c, "_send_request", lambda method, params: result)
        return c

    def test_dict_contents(self, monkeypatch):
        c = self._client(monkeypatch, {"contents": {"value": "hover text"}})
        assert c.get_hover("x.py", 0, 0) == "hover text"

    def test_list_contents_joined(self, monkeypatch):
        c = self._client(monkeypatch, {"contents": [{"value": "a"}, {"value": "b"}]})
        assert c.get_hover("x.py", 0, 0) == "a\nb"

    def test_string_contents(self, monkeypatch):
        c = self._client(monkeypatch, {"contents": "plain"})
        assert c.get_hover("x.py", 0, 0) == "plain"

    def test_no_contents_returns_none(self, monkeypatch):
        c = self._client(monkeypatch, {"other": 1})
        assert c.get_hover("x.py", 0, 0) is None

    def test_none_result_returns_none(self, monkeypatch):
        c = self._client(monkeypatch, None)
        assert c.get_hover("x.py", 0, 0) is None


# ── definition parsing ──────────────────────────────────────────────


class TestDefinitionParsing:
    def _client(self, monkeypatch, result):
        c = LSPClient()
        c._initialized = True
        monkeypatch.setattr(c, "_send_request", lambda method, params: result)
        return c

    def test_list_returns_first(self, monkeypatch):
        c = self._client(monkeypatch, [{"uri": "u1"}, {"uri": "u2"}])
        assert c.get_definition("x.py", 0, 0) == {"uri": "u1"}

    def test_dict_returned_as_is(self, monkeypatch):
        loc = {"uri": "u1", "range": {"start": {}}}
        c = self._client(monkeypatch, loc)
        assert c.get_definition("x.py", 0, 0) == loc

    def test_none_returns_none(self, monkeypatch):
        c = self._client(monkeypatch, None)
        assert c.get_definition("x.py", 0, 0) is None


# ── diagnostics + notification framing ──────────────────────────────


class TestDiagnosticsAndFraming:
    def test_get_diagnostics_opens_doc_and_returns_empty(self):
        c = LSPClient()
        proc = _FakeProc()
        c._process = proc
        c._initialized = True
        assert c.get_diagnostics(__file__) == []
        written = "".join(proc.stdin.written)
        assert '"textDocument/didOpen"' in written
        assert __file__ in written  # uri derived from the path

    def test_send_request_increments_id_and_returns_none_on_empty(self):
        c = LSPClient()
        proc = _FakeProc()  # stdout.readline returns "" → no header
        c._process = proc
        assert c._send_request("textDocument/hover", {}) is None
        assert c._id_counter == 1

    def test_send_notification_framing(self):
        c = LSPClient()
        proc = _FakeProc()
        c._process = proc
        c._send_notification("textDocument/didOpen", {"x": 1})
        written = "".join(proc.stdin.written)
        assert written.startswith("Content-Length: ")
        assert "\r\n\r\n" in written
        body = written.split("\r\n\r\n", 1)[1]
        parsed = json.loads(body)
        assert parsed["method"] == "textDocument/didOpen"
        assert parsed["params"] == {"x": 1}

    def test_send_request_reads_response_body(self):
        c = LSPClient()
        # Header with Content-Length, blank line, then JSON body.
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"contents": "parsed"}})
        header_lines = [f"Content-Length: {len(body)}\r\n", "\r\n"]
        proc = _FakeProc(stdout_lines=header_lines)
        c._process = proc
        # Override read to return the body once the header is consumed.
        proc.stdout.read = lambda n: body  # type: ignore[method-assign]
        result = c._send_request("textDocument/hover", {})
        assert result == {"contents": "parsed"}
