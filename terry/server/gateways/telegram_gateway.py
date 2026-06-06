"""Telegram Bot gateway for Terry — chat with your agent from anywhere."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx


class TelegramGateway:
    """Lightweight Telegram Bot gateway using HTTP long-polling.

    Requires a bot token from @BotFather. No additional dependencies
    beyond httpx (already in Terry's dependencies).
    """

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        token: str,
        agent_factory: Callable | None = None,
        allowed_users: list[int] | None = None,
        history_dir: Path | None = None,
    ):
        self.token = token
        self.agent_factory = agent_factory
        self.allowed_users = allowed_users or []  # Empty = allow all
        self.history_dir = history_dir or Path.home() / ".terry" / "telegram"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._offset = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._conversations: dict[int, list[dict]] = {}
        self._typing_cache: dict[int, float] = {}

    def _api_url(self, method: str) -> str:
        return f"{self.BASE_URL}/bot{self.token}/{method}"

    def _api_call(self, method: str, params: dict | None = None) -> dict:
        """Make a synchronous Telegram API call."""
        try:
            resp = httpx.post(
                self._api_url(method),
                json=params or {},
                timeout=30,
            )
            return resp.json()
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def get_updates(self) -> list[dict]:
        """Fetch pending updates from Telegram."""
        result = self._api_call("getUpdates", {
            "offset": self._offset,
            "timeout": 30,
            "allowed_updates": ["message"],
        })
        return result.get("result", [])

    def send_message(
        self, chat_id: int, text: str,
        parse_mode: str = "Markdown",
        reply_to_message_id: int | None = None,
    ) -> dict:
        """Send a message to a Telegram chat."""
        # Telegram has a 4096 char limit per message
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                self._api_call("sendMessage", {
                    "chat_id": chat_id,
                    "text": part,
                    "parse_mode": parse_mode,
                })
            return {"ok": True}
        return self._api_call("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_to_message_id": reply_to_message_id,
        })

    def send_typing(self, chat_id: int) -> None:
        """Send typing indicator (rate-limited to once per 5s)."""
        now = time.time()
        if chat_id in self._typing_cache and now - self._typing_cache[chat_id] < 5:
            return
        self._typing_cache[chat_id] = now
        self._api_call("sendChatAction", {
            "chat_id": chat_id,
            "action": "typing",
        })

    def handle_message(self, update: dict) -> None:
        """Process a single Telegram message update."""
        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        user = message.get("from", {})
        user_id = user.get("id")
        text = message.get("text", "").strip()

        if not text or not chat_id:
            return

        # Access control
        if self.allowed_users and user_id not in self.allowed_users:
            self.send_message(chat_id, "⛔ Access denied. You are not an authorized user.")
            return

        # Load conversation history
        if chat_id not in self._conversations:
            self._conversations[chat_id] = self._load_history(chat_id)

        # Handle commands
        if text.startswith("/"):
            self._handle_command(chat_id, text, user_id)
            return

        # Process with agent
        if self.agent_factory:
            self.send_typing(chat_id)
            try:
                agent = self.agent_factory()
                # Inject conversation context
                history = self._conversations.get(chat_id, [])
                if history:
                    context = "\n".join(
                        f"{m['role']}: {str(m['content'])[:500]}"
                        for m in history[-5:]
                    )
                    text = f"[Context]\n{context}\n\n[New message]\n{text}"

                response = agent.run(text)

                # Send response
                self.send_message(chat_id, response[:4000])

                # Save history
                self._conversations[chat_id].append({"role": "user", "content": text[:500]})
                self._conversations[chat_id].append({"role": "assistant", "content": response[:500]})
                self._save_history(chat_id)

            except Exception as e:
                self.send_message(chat_id, f"❌ Error: {str(e)[:500]}")
        else:
            # No agent configured
            self.send_message(chat_id, "⚠️ Agent not configured. Please set agent_factory.")

    def _handle_command(self, chat_id: int, command: str, user_id: int) -> None:
        """Handle Telegram bot commands."""
        parts = command.split()
        cmd = parts[0].lower()

        if cmd == "/start":
            self.send_message(
                chat_id,
                "🤖 *Terry Agent — Ready*\n\n"
                "Send me any message to start working.\n\n"
                "Commands:\n"
                "/new — Start fresh conversation\n"
                "/status — Show agent status\n"
                "/skills — List available skills\n"
                "/memory — Show what I remember\n"
                "/help — Show this help",
            )
        elif cmd == "/new":
            self._conversations[chat_id] = []
            self._save_history(chat_id)
            self.send_message(chat_id, "🆕 Conversation reset.")
        elif cmd == "/status":
            if self.agent_factory:
                agent = self.agent_factory()
                status = agent.get_status()
                self.send_message(chat_id, f"📊 *Status*\n```\n{json.dumps(status, indent=2)[:1000]}\n```")
        elif cmd == "/skills":
            if self.agent_factory:
                agent = self.agent_factory()
                skills = agent.list_skills()
                text = "*Available Skills:*\n" + "\n".join(
                    f"• {s['name']}: {s['description'][:80]}"
                    for s in skills
                )
                self.send_message(chat_id, text[:2000])
        elif cmd == "/memory":
            if self.agent_factory:
                agent = self.agent_factory()
                if agent.memory:
                    mems = agent.memory.list_memories()
                    text = "*Memory:*\n" + "\n".join(
                        f"• {m['name']}: {m['description'][:80]}"
                        for m in mems[:10]
                    )
                    self.send_message(chat_id, text[:2000] or "No memories yet.")
        elif cmd == "/help":
            self.send_message(
                chat_id,
                "*Commands:*\n"
                "/new /status /skills /memory /help",
            )

    def _load_history(self, chat_id: int) -> list[dict]:
        """Load conversation history from disk."""
        hist_file = self.history_dir / f"chat_{chat_id}.json"
        if hist_file.exists():
            try:
                return json.loads(hist_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save_history(self, chat_id: int) -> None:
        """Save conversation history to disk."""
        hist = self._conversations.get(chat_id, [])
        if len(hist) > 100:
            hist = hist[-100:]
        hist_file = self.history_dir / f"chat_{chat_id}.json"
        hist_file.write_text(
            json.dumps(hist, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def start_polling(self) -> None:
        """Start long-polling in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.handle_message(update)
                    self._offset = update["update_id"] + 1
            except Exception:
                time.sleep(5)

    def stop(self) -> None:
        """Stop polling."""
        self._running = False

    def send_broadcast(self, chat_ids: list[int], message: str) -> dict[int, bool]:
        """Broadcast a message to multiple chats."""
        results = {}
        for cid in chat_ids:
            resp = self.send_message(cid, message)
            results[cid] = resp.get("ok", False)
        return results
