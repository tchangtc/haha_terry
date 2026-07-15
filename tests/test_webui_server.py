"""Tests for the WebUI server (terry/webui/server.py).

The stdlib HTTPServer is started on an ephemeral port (port=0) in a daemon
thread and driven with ``http.client`` — real routing/handler logic, no mock
of the request path. Security middleware is disabled so the tests focus on the
REST/SSE handlers. SSE is unit-tested via ``SSEConnection`` / ``_broadcast_sse``
to avoid the long-lived ``/api/stream`` endpoint blocking the test.
"""

from __future__ import annotations

import http.client
import json

import pytest

from terry.webui.server import ChatSession, SSEConnection, WebUIServer


# ── fakes ───────────────────────────────────────────────────────────


class _FakeTool:
    def __init__(self, name: str, description: str = "d"):
        self.name = name
        self.description = description


class _Tools:
    def __init__(self, tools: list[_FakeTool] | None = None):
        self._tools = tools or [_FakeTool("bash", "run shell"), _FakeTool("read_file", "read")]

    def list_tools(self) -> list[_FakeTool]:
        return self._tools


class _Feedback:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record_direct(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _Model:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key


class _Config:
    def __init__(self, api_key: str) -> None:
        self.model = _Model(api_key)


class FakeWebUIAgent:
    """Mimics the attributes the WebUI handlers touch on a real agent."""

    def __init__(
        self,
        response: str = "ok",
        api_key: str = "sk-test",
        raises: bool = False,
        tool_calls: int = 2,
    ) -> None:
        self._response = response
        self._raises = raises
        self.config = _Config(api_key)
        self.tools = _Tools()
        self.tool_call_count = tool_calls
        self.feedback = _Feedback()

    def run(self, message: str) -> str:
        if self._raises:
            raise RuntimeError("boom")
        return self._response

    def get_status(self) -> dict:
        return {"state": "ready", "model": "test"}


# ── helpers ─────────────────────────────────────────────────────────


def _request(server: WebUIServer, method: str, path: str, body=None, raw=None, headers=None):
    port = server._server.server_address[1]  # type: ignore[union-attr]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = dict(headers or {})
    if raw is not None:
        payload = raw if isinstance(raw, (bytes, bytearray)) else raw.encode()
    elif body is not None:
        payload = json.dumps(body).encode()
    else:
        payload = None
    conn.request(method, path, body=payload, headers=h)
    resp = conn.getresponse()
    data = resp.read().decode()
    hdrs = {k.lower(): v for k, v in resp.getheaders()}
    status = resp.status
    conn.close()
    return status, data, hdrs


def _get(server: WebUIServer, path: str):
    return _request(server, "GET", path)


def _post(server: WebUIServer, path: str, body=None, raw=None):
    return _request(server, "POST", path, body=body, raw=raw, headers={"Content-Type": "application/json"})


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def fake_agent() -> FakeWebUIAgent:
    return FakeWebUIAgent()


@pytest.fixture
def server(fake_agent: FakeWebUIAgent) -> WebUIServer:
    s = WebUIServer(agent_factory=lambda: fake_agent, enable_security=False, port=0)
    s.start()
    yield s
    s.stop()


@pytest.fixture
def bare_server() -> WebUIServer:
    s = WebUIServer(agent_factory=None, enable_security=False, port=0)
    s.start()
    yield s
    s.stop()


# ── ChatSession ─────────────────────────────────────────────────────


class TestChatSession:
    def test_add_and_to_dict(self):
        s = ChatSession("abc")
        s.add_message("user", "hi")
        s.add_message("assistant", "hello")
        d = s.to_dict()
        assert d["id"] == "abc"
        assert d["message_count"] == 2
        assert len(d["messages"]) == 2
        assert d["messages"][0]["role"] == "user"
        assert "timestamp" in d["messages"][0]

    def test_to_dict_returns_last_50(self):
        s = ChatSession("x")
        for i in range(60):
            s.add_message("user", str(i))
        d = s.to_dict()
        assert d["message_count"] == 60
        assert len(d["messages"]) == 50
        assert d["messages"][0]["content"] == "10"  # 60 - 50 = 10
        assert d["messages"][-1]["content"] == "59"


# ── SSEConnection ───────────────────────────────────────────────────


class TestSSEConnection:
    def test_send_queues_formatted_event(self):
        c = SSEConnection()
        c.send("msg", {"text": "hi"})
        payload = c.queue.get_nowait()
        assert payload.startswith("event: msg\n")
        assert "data: " in payload
        assert payload.endswith("\n\n")
        assert '"text"' in payload

    def test_close_sets_inactive_and_sentinel(self):
        c = SSEConnection()
        c.close()
        assert c.active is False
        assert c.queue.get_nowait() == ""  # sentinel unblocks consumers

    def test_send_ignored_after_close(self):
        c = SSEConnection()
        c.close()
        c.queue.get_nowait()  # drain sentinel
        c.send("x", {"a": 1})
        assert c.queue.empty()


# ── session management ──────────────────────────────────────────────


class TestSessionManagement:
    def test_get_or_create_reuses(self, bare_server: WebUIServer):
        s1 = bare_server._get_or_create_session("sid1")
        s2 = bare_server._get_or_create_session("sid1")
        assert s1 is s2
        assert "sid1" in bare_server.sessions

    def test_get_or_create_generates_id(self, bare_server: WebUIServer):
        s = bare_server._get_or_create_session(None)
        assert s.id and len(s.id) == 8  # uuid[:8]
        assert s.id in bare_server.sessions

    def test_broadcast_sse_fans_out(self, bare_server: WebUIServer):
        c = SSEConnection()
        bare_server.sse_connections["c1"] = c
        bare_server._broadcast_sse("tick", {"n": 1})
        msg = c.queue.get_nowait()
        assert "event: tick" in msg and '"n": 1' in msg

    def test_broadcast_sse_swallows_disconnected(self, bare_server: WebUIServer):
        class DeadConn:
            def send(self, event, data):
                raise BrokenPipeError()
        bare_server.sse_connections["dead"] = DeadConn()  # type: ignore[assignment]
        bare_server._broadcast_sse("x", {})  # must not raise


# ── GET handlers ────────────────────────────────────────────────────


class TestGetHandlers:
    def test_health_with_agent_ready(self, server: WebUIServer):
        st, body, _ = _get(server, "/api/health")
        data = json.loads(body)
        assert st == 200
        assert data["status"] == "ok"
        assert data["ready"] is True
        assert data["message"] == ""
        assert data["version"]

    def test_health_without_agent(self, bare_server: WebUIServer):
        st, body, _ = _get(bare_server, "/api/health")
        data = json.loads(body)
        assert st == 200
        assert data["ready"] is False
        assert "API key not configured" in data["message"]

    def test_status_without_agent(self, bare_server: WebUIServer):
        st, body, _ = _get(bare_server, "/api/status")
        assert st == 200
        assert json.loads(body)["status"] == "no agent"

    def test_status_with_agent(self, server: WebUIServer, fake_agent: FakeWebUIAgent):
        st, body, _ = _get(server, "/api/status")
        data = json.loads(body)
        assert st == 200
        assert data["state"] == "ready"
        assert data["tools_available"] == len(fake_agent.tools.list_tools())
        assert data["sessions"] == 0

    def test_tools_without_agent(self, bare_server: WebUIServer):
        st, body, _ = _get(bare_server, "/api/tools")
        assert st == 200
        assert json.loads(body)["tools"] == []

    def test_tools_with_agent(self, server: WebUIServer):
        st, body, _ = _get(server, "/api/tools")
        data = json.loads(body)
        assert st == 200
        assert [t["name"] for t in data["tools"]] == ["bash", "read_file"]

    def test_sessions_list_empty(self, bare_server: WebUIServer):
        st, body, _ = _get(bare_server, "/api/sessions")
        assert st == 200
        assert json.loads(body)["sessions"] == []

    def test_session_messages_404(self, bare_server: WebUIServer):
        st, body, _ = _get(bare_server, "/api/sessions/nope/messages")
        assert st == 404
        assert "not found" in json.loads(body)["error"].lower()

    def test_tasks_endpoint(self, server: WebUIServer):
        st, body, _ = _get(server, "/api/tasks")
        assert st == 200
        assert "tasks" in json.loads(body)

    def test_agents_endpoint(self, server: WebUIServer):
        # background_registry is a process-global singleton that other tests
        # may populate, so assert the serialization contract, not emptiness.
        st, body, _ = _get(server, "/api/agents")
        data = json.loads(body)
        assert st == 200
        assert isinstance(data["agents"], list)
        assert data["total"] == len(data["agents"])

    def test_routines_endpoint(self, server: WebUIServer):
        st, body, _ = _get(server, "/api/routines")
        assert st == 200
        assert isinstance(json.loads(body)["routines"], list)

    def test_static_index(self, bare_server: WebUIServer):
        st, body, _ = _get(bare_server, "/")
        assert st == 200
        assert "<html" in body.lower() or "terry" in body.lower()


# ── POST handlers ───────────────────────────────────────────────────


class TestPostChat:
    def test_chat_invalid_json(self, server: WebUIServer):
        st, body, _ = _post(server, "/api/chat", raw=b"{not json")
        assert st == 400
        assert json.loads(body)["error"] == "Invalid JSON"

    def test_chat_empty_message(self, server: WebUIServer):
        st, body, _ = _post(server, "/api/chat", body={"message": ""})
        assert st == 400
        assert json.loads(body)["error"] == "Message required"

    def test_chat_success(self, server: WebUIServer, fake_agent: FakeWebUIAgent):
        st, body, _ = _post(server, "/api/chat", body={"message": "hello"})
        data = json.loads(body)
        assert st == 200
        assert data["response"] == "ok"
        assert data["tool_calls"] == fake_agent.tool_call_count
        assert data["session_id"]

    def test_chat_stores_session_and_history(self, server: WebUIServer):
        sid = "s-chat-1"
        _post(server, "/api/chat", body={"message": "hi", "session_id": sid})
        st, body, _ = _get(server, "/api/sessions")
        sessions = json.loads(body)["sessions"]
        assert any(s["id"] == sid and s["message_count"] == 2 for s in sessions)
        st2, body2, _ = _get(server, f"/api/sessions/{sid}/messages")
        assert st2 == 200
        assert json.loads(body2)["message_count"] == 2

    def test_chat_agent_error_500(self, bare_server: WebUIServer, fake_agent: FakeWebUIAgent):
        fake_agent._raises = True
        bare_server.agent_factory = lambda: fake_agent
        st, body, _ = _post(bare_server, "/api/chat", body={"message": "boom"})
        data = json.loads(body)
        assert st == 500
        assert "boom" in data["error"]
        assert data["session_id"]

    def test_chat_no_agent_echoes(self, bare_server: WebUIServer):
        st, body, _ = _post(bare_server, "/api/chat", body={"message": "ping"})
        data = json.loads(body)
        assert st == 200
        assert "[No agent configured]" in data["response"]
        assert "ping" in data["response"]


class TestPostFeedback:
    def test_feedback_recorded(self, server: WebUIServer, fake_agent: FakeWebUIAgent):
        st, body, _ = _post(server, "/api/feedback", body={"rating": "good", "session_id": "s1"})
        assert st == 200
        data = json.loads(body)
        assert data == {"status": "recorded", "rating": "good"}
        assert fake_agent.feedback.calls and fake_agent.feedback.calls[0]["rating"] == "good"

    def test_feedback_invalid_json(self, server: WebUIServer):
        st, body, _ = _post(server, "/api/feedback", raw=b"---")
        assert st == 400
        assert json.loads(body)["error"] == "Invalid JSON"

    def test_feedback_without_agent(self, bare_server: WebUIServer):
        st, body, _ = _post(bare_server, "/api/feedback", body={"rating": "skip"})
        assert st == 200
        assert json.loads(body)["rating"] == "skip"


class TestPostClearSession:
    def test_clear_existing(self, server: WebUIServer):
        _post(server, "/api/chat", body={"message": "hi", "session_id": "clr1"})
        st, body, _ = _post(server, "/api/sessions/clear", body={"session_id": "clr1"})
        assert st == 200
        assert json.loads(body)["status"] == "cleared"
        assert "clr1" not in server.sessions

    def test_clear_missing_404(self, server: WebUIServer):
        st, body, _ = _post(server, "/api/sessions/clear", body={"session_id": "ghost"})
        assert st == 404
        assert "not found" in json.loads(body)["error"].lower()

    def test_clear_invalid_json(self, server: WebUIServer):
        st, _body, _ = _post(server, "/api/sessions/clear", raw=b"!")
        assert st == 400

    def test_unknown_post_404(self, server: WebUIServer):
        st, body, _ = _post(server, "/api/nope", body={})
        assert st == 404
        assert json.loads(body)["error"] == "Not found"


# ── OPTIONS / CORS ──────────────────────────────────────────────────


class TestOptions:
    def test_options_returns_204_with_cors(self, bare_server: WebUIServer):
        st, _body, hdrs = _request(bare_server, "OPTIONS", "/api/chat")
        assert st == 204
        assert "access-control-allow-origin" in hdrs
        assert "access-control-allow-methods" in hdrs
        assert "x-content-type-options" in hdrs  # security header present
