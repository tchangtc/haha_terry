"""Discord Bot gateway for Terry — chat with your agent from Discord servers."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from ...core.platform_utils import get_terry_dir


class DiscordGateway:
    """Lightweight Discord Bot gateway using HTTP REST API + Gateway.

    Requires a bot token from Discord Developer Portal.
    Uses httpx (already in Terry's dependencies) — no discord.py needed.
    """

    API_BASE = "https://discord.com/api/v10"

    def __init__(
        self,
        token: str,
        agent_factory: Callable | None = None,
        allowed_channels: list[int] | None = None,
        history_dir: Path | None = None,
    ):
        self.token = token
        self.agent_factory = agent_factory
        self.allowed_channels = allowed_channels or []  # Empty = all channels
        self.history_dir = history_dir or get_terry_dir("discord")
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_message_id: dict[int, str] = {}
        self._conversations: dict[int, list[dict]] = {}

    def _api_call(self, method: str, endpoint: str, json_data: dict | None = None) -> dict:
        """Make a Discord API call."""
        try:
            url = f"{self.API_BASE}{endpoint}"
            if method == "GET":
                resp = httpx.get(url, headers=self._headers, timeout=15)
            elif method == "POST":
                resp = httpx.post(url, headers=self._headers, json=json_data, timeout=15)
            else:
                return {"ok": False}
            if resp.status_code == 204:
                return {"ok": True}
            return resp.json() if resp.text else {"ok": False}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_message(
        self, channel_id: int, content: str,
        reply_to: str | None = None,
    ) -> dict:
        """Send a message to a Discord channel."""
        # Discord has a 2000 char limit
        if len(content) > 1900:
            parts = [content[i:i+1900] for i in range(0, len(content), 1900)]
            for part in parts:
                payload = {"content": part}
                if reply_to:
                    payload["message_reference"] = {"message_id": reply_to}
                self._api_call("POST", f"/channels/{channel_id}/messages", payload)
            return {"ok": True}

        payload = {"content": content}
        if reply_to:
            payload["message_reference"] = {"message_id": reply_to}
        return self._api_call("POST", f"/channels/{channel_id}/messages", payload)

    def send_typing(self, channel_id: int) -> None:
        """Trigger typing indicator."""
        self._api_call("POST", f"/channels/{channel_id}/typing")

    def get_messages(self, channel_id: int, limit: int = 10) -> list[dict]:
        """Get recent messages from a channel."""
        endpoint = f"/channels/{channel_id}/messages?limit={limit}"
        resp = self._api_call("GET", endpoint)
        return resp if isinstance(resp, list) else []

    def handle_mention(self, channel_id: int, message_id: str, author: str, content: str) -> None:
        """Handle a message that mentions the bot."""
        # Strip bot mention
        text = content.replace(f"<@!{self._get_bot_id()}>", "").strip()
        text = text.replace(f"<@{self._get_bot_id()}>", "").strip()

        if not text:
            self.send_message(channel_id, "👋 How can I help? Send me a message!")
            return

        if text.startswith("!"):
            self._handle_command(channel_id, text[1:], message_id)
            return

        if self.agent_factory:
            self.send_typing(channel_id)
            try:
                agent = self.agent_factory()
                # Load conversation
                if channel_id not in self._conversations:
                    self._conversations[channel_id] = []

                response = agent.run(text)
                self.send_message(channel_id, response[:1900], reply_to=message_id)

                self._conversations[channel_id].append({"role": "user", "content": text[:500]})
                self._conversations[channel_id].append({"role": "assistant", "content": response[:500]})

            except Exception as e:
                self.send_message(channel_id, f"❌ Error: {str(e)[:500]}")

    def _handle_command(self, channel_id: int, command: str, message_id: str) -> None:
        """Handle Discord bot commands."""
        cmd = command.lower().split()[0]

        if cmd == "new":
            self._conversations[channel_id] = []
            self.send_message(channel_id, "🆕 Conversation reset.")
        elif cmd == "status":
            if self.agent_factory:
                agent = self.agent_factory()
                st = agent.get_status()
                self.send_message(channel_id, f"```json\n{json.dumps(st, indent=2)[:1500]}\n```")
        elif cmd == "skills":
            if self.agent_factory:
                agent = self.agent_factory()
                skills = agent.list_skills()
                lines = [f"**{s['name']}**: {s['description'][:80]}" for s in skills]
                self.send_message(channel_id, "\n".join(lines)[:1900])
        elif cmd == "help":
            self.send_message(
                channel_id,
                "**Terry Agent Commands:**\n"
                "`!new` — Reset conversation\n"
                "`!status` — Show agent status\n"
                "`!skills` — List skills\n"
                "`!help` — Show this help",
            )

    _bot_id: str | None = None

    def _get_bot_id(self) -> str:
        """Get the bot's user ID."""
        if self._bot_id is None:
            resp = self._api_call("GET", "/users/@me")
            self._bot_id = resp.get("id", "")
        return self._bot_id

    def start_polling(self, poll_interval: int = 3) -> None:
        """Start polling for messages in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, args=(poll_interval,), daemon=True
        )
        self._thread.start()

    def _poll_loop(self, poll_interval: int) -> None:
        """Background polling loop."""
        channels = self.allowed_channels or []
        if not channels:
            # Try to discover channels the bot has access to
            try:
                resp = self._api_call("GET", "/users/@me/guilds")
                guilds = resp if isinstance(resp, list) else []
                for guild in guilds:
                    guild_id = guild.get("id")
                    channels_resp = self._api_call("GET", f"/guilds/{guild_id}/channels")
                    guild_channels = channels_resp if isinstance(channels_resp, list) else []
                    for ch in guild_channels:
                        if ch.get("type") == 0:  # Text channel
                            channels.append(int(ch.get("id")))
            except Exception:
                pass

        while self._running:
            for channel_id in channels[:10]:  # Limit to 10 channels
                try:
                    msgs = self.get_messages(channel_id, limit=3)
                    for msg in msgs:
                        msg_id = msg.get("id", "")
                        if msg_id == self._last_message_id.get(channel_id):
                            continue
                        author_data = msg.get("author", {})
                        if author_data.get("bot"):
                            continue
                        content = msg.get("content", "")
                        self.handle_mention(
                            channel_id, msg_id,
                            author_data.get("username", "unknown"),
                            content,
                        )
                        self._last_message_id[channel_id] = msg_id
                except Exception:
                    pass
            time.sleep(poll_interval)

    def stop(self) -> None:
        """Stop polling."""
        self._running = False
