"""ACP (Agent Client Protocol) server for Terry.

Implements the Agent Client Protocol (https://agentclientprotocol.com/)
so that ACP-compatible editors (Zed, JetBrains, etc.) can drive Terry
as an AI coding agent over stdio.

Protocol: JSON-RPC 2.0 over stdin/stdout
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

logger = logging.getLogger(__name__)

# Protocol version support
MIN_PROTOCOL_VERSION = 1
CURRENT_VERSION = 1

# ── ACP Message Types ──────────────────────────────────────────────


def make_response(request_id: str | int, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(request_id: str | int | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def make_notification(method: str, params: dict | None = None) -> dict:
    msg: dict = {"jsonrpc": "2.0", "method": method}
    if params:
        msg["params"] = params
    return msg


# ── ACP Server ─────────────────────────────────────────────────────


class AcpServer:
    """Minimal ACP server that bridges an editor to a Terry agent session."""

    def __init__(self, agent_factory=None):
        self._agent_factory = agent_factory
        self._sessions: dict[str, dict] = {}
        self._session_counter = 0
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def run(self):
        """Run the ACP server on stdin/stdout."""
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        self._writer = asyncio.StreamWriter(
            transport=None, protocol=None, reader=None, loop=loop  # type: ignore[arg-type]
        )

        # Use stdin/stdout directly
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout  # type: ignore[arg-type]
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, loop)

        self._reader = reader
        self._writer = writer

        await self._handle_messages()

    async def _handle_messages(self):
        """Read JSON-RPC messages line by line from stdin."""
        while True:
            try:
                line = await self._reader.readline()  # type: ignore[union-attr]
                if not line:
                    break
                await self._dispatch(json.loads(line.decode()))
            except json.JSONDecodeError:
                logger.warning("ACP: invalid JSON received")
            except Exception:
                logger.exception("ACP: dispatch error")

    async def _dispatch(self, msg: dict):
        """Route a JSON-RPC message to the appropriate handler."""
        method = msg.get("method", "")
        msg_id = msg.get("id")

        try:
            if method == "initialize":
                result = self._handle_initialize(msg.get("params", {}))
                self._send(make_response(msg_id, result))
            elif method == "session/new":
                result = self._handle_session_new(msg.get("params", {}))
                self._send(make_response(msg_id, result))
            elif method == "agent/turn":
                result = await self._handle_agent_turn(msg.get("params", {}))
                self._send(make_response(msg_id, result))
            elif method == "agent/cancel":
                result = self._handle_agent_cancel(msg.get("params", {}))
                self._send(make_response(msg_id, result))
            elif method == "session/close":
                result = self._handle_session_close(msg.get("params", {}))
                self._send(make_response(msg_id, result))
            elif method == "shutdown":
                self._send(make_response(msg_id, {"status": "ok"}))
                sys.exit(0)
            else:
                self._send(make_error(msg_id, -32601, f"Method not found: {method}"))
        except Exception as e:
            self._send(make_error(msg_id, -32603, str(e)))

    def _send(self, msg: dict):
        """Write a JSON-RPC message to stdout."""
        if self._writer:
            data = json.dumps(msg, ensure_ascii=False) + "\n"
            self._writer.write(data.encode())
            # Flush is async but we're in async context
            # Use synchronous write to stdout for simplicity
            sys.stdout.write(data)
            sys.stdout.flush()

    # ── Handlers ─────────────────────────────────────────────────

    def _handle_initialize(self, params: dict) -> dict:
        """Initialize the ACP connection."""
        client_version = params.get("protocolVersion", 1)
        negotiated = min(client_version, CURRENT_VERSION)
        if negotiated < MIN_PROTOCOL_VERSION:
            raise ValueError(
                f"Unsupported protocol version {client_version}. "
                f"Minimum required: {MIN_PROTOCOL_VERSION}"
            )

        return {
            "protocolVersion": negotiated,
            "serverInfo": {
                "name": "Terry",
                "version": self._get_version(),
            },
            "capabilities": {
                "agent": {
                    "subagents": True,
                    "backgroundTasks": True,
                },
                "tools": {
                    "bash": True,
                    "read": True,
                    "write": True,
                    "edit": True,
                    "search": True,
                },
            },
        }

    def _handle_session_new(self, params: dict) -> dict:
        """Create a new agent session."""
        self._session_counter += 1
        session_id = f"terry-{self._session_counter}"
        self._sessions[session_id] = {
            "id": session_id,
            "messages": [],
            "cwd": params.get("cwd", "."),
        }
        return {"sessionId": session_id}

    async def _handle_agent_turn(self, params: dict) -> dict:
        """Process a user message and return the agent's response."""
        session_id = params.get("sessionId", "default")
        user_message = params.get("message", "")
        if not user_message:
            raise ValueError("Missing 'message' in agent/turn params")

        session = self._sessions.get(session_id, {"id": session_id, "messages": []})

        # Use agent factory if available, otherwise return placeholder
        if self._agent_factory:
            try:
                agent = self._agent_factory()
                response = await self._run_agent_turn(agent, user_message)
            except Exception as e:
                response = f"Error: {e}"
        else:
            response = (
                f"[ACP Mode] Terry received: {user_message}\n"
                "Set ANTHROPIC_API_KEY and use 'terry acp' to enable full agent mode."
            )

        session["messages"].append({"role": "user", "content": user_message})
        session["messages"].append({"role": "assistant", "content": response})

        return {
            "sessionId": session_id,
            "stopReason": "end_turn",
            "content": response,
        }

    async def _run_agent_turn(self, agent, message: str) -> str:
        """Run a single turn with the Terry agent."""
        loop = asyncio.get_event_loop()
        # Agent.run() is synchronous, so run in executor
        result = await loop.run_in_executor(
            None, lambda: agent.run(message, stream=False)
        )
        return str(result) if result else ""

    def _handle_agent_cancel(self, params: dict) -> dict:
        """Cancel the current agent turn."""
        return {"cancelled": True}

    def _handle_session_close(self, params: dict) -> dict:
        """Close an agent session."""
        session_id = params.get("sessionId", "")
        self._sessions.pop(session_id, None)
        return {"closed": True}

    @staticmethod
    def _get_version() -> str:
        try:
            from terry import __version__
            return __version__
        except ImportError:
            return "unknown"


# ── CLI Entry Point ───────────────────────────────────────────────


def run_acp():
    """Entry point for `terry acp` — start the ACP stdio server."""
    print("Terry ACP Server starting...", file=sys.stderr)
    print(f"Protocol version: {CURRENT_VERSION}", file=sys.stderr)
    print("Waiting for editor connection...", file=sys.stderr)

    # Optional: create agent from config
    agent_factory = None
    try:
        from terry.core.config import TerryConfig
        config = TerryConfig()
        if config.model.api_key:
            from terry.core.agent import Agent

            def _make_agent():
                return Agent(config, enable_subagents=False)

            agent_factory = _make_agent
            print("Agent configured — full mode enabled", file=sys.stderr)
    except Exception as e:
        print(f"Agent not configured: {e}", file=sys.stderr)
        print("Running in passthrough mode", file=sys.stderr)

    server = AcpServer(agent_factory=agent_factory)
    asyncio.run(server.run())
