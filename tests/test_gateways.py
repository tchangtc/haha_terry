"""Tests for the Telegram and Discord gateways.

Network-free: every test replaces the single ``_api_call`` chokepoint with a
recorder, so message handling, commands, access control, history, and broadcast
logic are exercised without touching httpx.
"""

from __future__ import annotations

import json

from terry.server.gateways.discord_gateway import DiscordGateway
from terry.server.gateways.telegram_gateway import TelegramGateway


class _Memory:
    def list_memories(self):
        return [{"name": "pref", "description": "a saved preference"}]


class FakeAgent:
    def __init__(self, response="hi there", raises=False, with_memory=False):
        self._response = response
        self._raises = raises
        self.memory = _Memory() if with_memory else None
        self.last_input = None

    def run(self, text):
        self.last_input = text
        if self._raises:
            raise RuntimeError("boom")
        return self._response

    def get_status(self):
        return {"state": "ready"}

    def list_skills(self):
        return [{"name": "demo", "description": "a demo skill"}]


# ── Telegram ─────────────────────────────────────────────────────────


def _telegram(tmp_path, **kw):
    gw = TelegramGateway(token="TOKEN", history_dir=tmp_path, **kw)
    calls: list[tuple[str, dict]] = []

    def fake_api(method, params=None):
        calls.append((method, params or {}))
        return {"ok": True, "result": []}

    gw._api_call = fake_api
    gw._calls = calls
    return gw


def _msg(text, chat_id=1, user_id=7):
    return {"message": {"text": text, "chat": {"id": chat_id}, "from": {"id": user_id}}}


class TestTelegramBasics:
    def test_api_url(self, tmp_path):
        gw = _telegram(tmp_path)
        assert gw._api_url("getUpdates").endswith("/botTOKEN/getUpdates")

    def test_send_message_short(self, tmp_path):
        gw = _telegram(tmp_path)
        gw.send_message(1, "hello")
        assert gw._calls[0][0] == "sendMessage"
        assert gw._calls[0][1]["text"] == "hello"

    def test_send_message_long_is_split(self, tmp_path):
        gw = _telegram(tmp_path)
        gw.send_message(1, "x" * 9000)
        assert len(gw._calls) == 3  # 9000 / 4000 → 3 chunks
        assert all(c[0] == "sendMessage" for c in gw._calls)

    def test_send_typing_rate_limited(self, tmp_path):
        gw = _telegram(tmp_path)
        gw.send_typing(1)
        gw.send_typing(1)  # within 5s → suppressed
        assert sum(1 for c in gw._calls if c[0] == "sendChatAction") == 1


class TestTelegramHandleMessage:
    def test_empty_text_ignored(self, tmp_path):
        gw = _telegram(tmp_path)
        gw.handle_message(_msg("   "))
        assert gw._calls == []

    def test_access_denied_for_unlisted_user(self, tmp_path):
        gw = _telegram(tmp_path, allowed_users=[999])
        gw.handle_message(_msg("hi", user_id=7))
        assert "Access denied" in gw._calls[0][1]["text"]

    def test_runs_agent_and_saves_history(self, tmp_path):
        gw = _telegram(tmp_path, agent_factory=lambda: FakeAgent("the answer"))
        gw.handle_message(_msg("question"))
        texts = [c[1].get("text", "") for c in gw._calls]
        assert "the answer" in texts
        assert (tmp_path / "chat_1.json").exists()
        saved = json.loads((tmp_path / "chat_1.json").read_text())
        assert saved[-1]["role"] == "assistant"

    def test_no_agent_configured(self, tmp_path):
        gw = _telegram(tmp_path)
        gw.handle_message(_msg("hi"))
        assert "not configured" in gw._calls[0][1]["text"]

    def test_agent_error_is_reported(self, tmp_path):
        gw = _telegram(tmp_path, agent_factory=lambda: FakeAgent(raises=True))
        gw.handle_message(_msg("hi"))
        assert any("Error" in c[1].get("text", "") for c in gw._calls)


class TestTelegramCommands:
    def test_start(self, tmp_path):
        gw = _telegram(tmp_path)
        gw.handle_message(_msg("/start"))
        assert "Ready" in gw._calls[0][1]["text"]

    def test_new_resets_conversation(self, tmp_path):
        gw = _telegram(tmp_path, agent_factory=lambda: FakeAgent())
        gw.handle_message(_msg("hi"))  # seed history
        gw.handle_message(_msg("/new"))
        assert gw._conversations[1] == []
        assert any("reset" in c[1].get("text", "").lower() for c in gw._calls)

    def test_status(self, tmp_path):
        gw = _telegram(tmp_path, agent_factory=lambda: FakeAgent())
        gw.handle_message(_msg("/status"))
        assert any("Status" in c[1].get("text", "") for c in gw._calls)

    def test_skills(self, tmp_path):
        gw = _telegram(tmp_path, agent_factory=lambda: FakeAgent())
        gw.handle_message(_msg("/skills"))
        assert any("demo" in c[1].get("text", "") for c in gw._calls)


class TestTelegramHistoryAndBroadcast:
    def test_history_roundtrip(self, tmp_path):
        gw = _telegram(tmp_path)
        gw._conversations[5] = [{"role": "user", "content": "a"}]
        gw._save_history(5)
        assert gw._load_history(5) == [{"role": "user", "content": "a"}]

    def test_load_missing_history_returns_empty(self, tmp_path):
        gw = _telegram(tmp_path)
        assert gw._load_history(404) == []

    def test_save_caps_at_100(self, tmp_path):
        gw = _telegram(tmp_path)
        gw._conversations[5] = [{"role": "user", "content": str(i)} for i in range(150)]
        gw._save_history(5)
        assert len(gw._load_history(5)) == 100

    def test_broadcast(self, tmp_path):
        gw = _telegram(tmp_path)
        results = gw.send_broadcast([1, 2, 3], "notice")
        assert results == {1: True, 2: True, 3: True}


class TestTelegramExtra:
    def test_command_memory(self, tmp_path):
        gw = _telegram(tmp_path, agent_factory=lambda: FakeAgent(with_memory=True))
        gw.handle_message(_msg("/memory"))
        assert any("pref" in c[1].get("text", "") for c in gw._calls)

    def test_context_is_injected_into_agent(self, tmp_path):
        agent = FakeAgent("ok")
        gw = _telegram(tmp_path, agent_factory=lambda: agent)
        gw._conversations[1] = [{"role": "user", "content": "earlier"}]
        gw.handle_message(_msg("follow-up"))
        assert "[Context]" in agent.last_input and "follow-up" in agent.last_input

    def test_load_history_corrupt_returns_empty(self, tmp_path):
        gw = _telegram(tmp_path)
        (tmp_path / "chat_9.json").write_text("{ not json")
        assert gw._load_history(9) == []

    def test_start_polling_guard_and_stop(self, tmp_path):
        gw = _telegram(tmp_path)
        gw._running = True  # pretend already polling
        gw.start_polling()
        assert gw._thread is None  # guard prevented a second thread
        gw.stop()
        assert gw._running is False


# ── Discord ──────────────────────────────────────────────────────────


def _discord(tmp_path, **kw):
    gw = DiscordGateway(token="TOKEN", history_dir=tmp_path, **kw)
    calls: list[tuple[str, str, dict]] = []

    def fake_api(method, endpoint, json_data=None):
        calls.append((method, endpoint, json_data or {}))
        if endpoint == "/users/@me":
            return {"id": "BOT"}
        return {"ok": True}

    gw._api_call = fake_api
    gw._calls = calls
    gw._bot_id = "BOT"  # avoid the extra /users/@me call in handle_mention
    return gw


class TestDiscord:
    def test_send_message_short(self, tmp_path):
        gw = _discord(tmp_path)
        gw.send_message(10, "hello")
        assert gw._calls[0][2]["content"] == "hello"

    def test_send_message_long_is_split(self, tmp_path):
        gw = _discord(tmp_path)
        gw.send_message(10, "y" * 4000)
        assert len(gw._calls) == 3  # 4000 / 1900 → 3 chunks

    def test_mention_empty_prompts_for_input(self, tmp_path):
        gw = _discord(tmp_path)
        gw.handle_mention(10, "m1", "user", "<@BOT>   ")
        assert "How can I help" in gw._calls[0][2]["content"]

    def test_mention_runs_agent(self, tmp_path):
        gw = _discord(tmp_path, agent_factory=lambda: FakeAgent("discord answer"))
        gw.handle_mention(10, "m1", "user", "<@BOT> question")
        assert any("discord answer" in c[2].get("content", "") for c in gw._calls)

    def test_mention_agent_error(self, tmp_path):
        gw = _discord(tmp_path, agent_factory=lambda: FakeAgent(raises=True))
        gw.handle_mention(10, "m1", "user", "<@BOT> boom")
        assert any("Error" in c[2].get("content", "") for c in gw._calls)

    def test_command_new(self, tmp_path):
        gw = _discord(tmp_path)
        gw.handle_mention(10, "m1", "user", "<@BOT> !new")
        assert any("reset" in c[2].get("content", "").lower() for c in gw._calls)

    def test_command_help(self, tmp_path):
        gw = _discord(tmp_path)
        gw.handle_mention(10, "m1", "user", "<@BOT> !help")
        assert any("Commands" in c[2].get("content", "") for c in gw._calls)

    def test_command_skills(self, tmp_path):
        gw = _discord(tmp_path, agent_factory=lambda: FakeAgent())
        gw.handle_mention(10, "m1", "user", "<@BOT> !skills")
        assert any("demo" in c[2].get("content", "") for c in gw._calls)

    def test_get_messages_returns_list(self, tmp_path):
        gw = _discord(tmp_path)
        gw._api_call = lambda m, e, j=None: [{"id": "1"}]
        assert gw.get_messages(10) == [{"id": "1"}]

    def test_get_bot_id_cached(self, tmp_path):
        gw = _discord(tmp_path)
        gw._bot_id = None
        assert gw._get_bot_id() == "BOT"
        # Second call uses cache — no extra /users/@me lookup.
        n = sum(1 for c in gw._calls if c[1] == "/users/@me")
        gw._get_bot_id()
        assert sum(1 for c in gw._calls if c[1] == "/users/@me") == n

    def test_command_status(self, tmp_path):
        gw = _discord(tmp_path, agent_factory=lambda: FakeAgent())
        gw.handle_mention(10, "m1", "user", "<@BOT> !status")
        assert any("ready" in c[2].get("content", "") for c in gw._calls)

    def test_send_message_reply_to(self, tmp_path):
        gw = _discord(tmp_path)
        gw.send_message(10, "hi", reply_to="m9")
        assert gw._calls[0][2]["message_reference"] == {"message_id": "m9"}

    def test_send_typing(self, tmp_path):
        gw = _discord(tmp_path)
        gw.send_typing(10)
        assert gw._calls[0][1] == "/channels/10/typing"

    def test_get_messages_non_list_returns_empty(self, tmp_path):
        gw = _discord(tmp_path)
        gw._api_call = lambda m, e, j=None: {"ok": False}
        assert gw.get_messages(10) == []

    def test_start_polling_guard_and_stop(self, tmp_path):
        gw = _discord(tmp_path)
        gw._running = True
        gw.start_polling()
        assert gw._thread is None
        gw.stop()
        assert gw._running is False
