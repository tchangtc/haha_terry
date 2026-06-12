"""Terry WebUI — full-featured HTTP server with SSE streaming, REST API, and mobile-ready frontend.

Provides a complete web-based interface for Terry with:
- Real-time chat via Server-Sent Events (SSE)
- Conversation history management
- Tool execution monitoring
- System status dashboard
- Mobile-responsive design
- PWA support (offline-capable)

Usage:
    terry webui              # Start on default port 8670
    terry webui --port 9000  # Custom port
    terry webui --host 0.0.0.0 --port 8670  # Allow LAN access
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from terry import __version__

if TYPE_CHECKING:
    from terry.core.typing_protocols import AgentLike

import logging

logger = logging.getLogger(__name__)


class ChatSession:
    """Manages a single WebUI chat session."""

    def __init__(self, session_id: str):
        self.id = session_id
        self.messages: list[dict] = []
        self.created_at = time.time()

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "messages": self.messages[-50:],  # Last 50
            "message_count": len(self.messages),
        }


class SSEConnection:
    """Represents an active SSE connection to a client."""

    def __init__(self):
        self.queue: queue.Queue[str] = queue.Queue()
        self.active = True

    def send(self, event: str, data: Any) -> None:
        if self.active:
            payload = json.dumps(data)
            self.queue.put(f"event: {event}\ndata: {payload}\n\n")

    def close(self) -> None:
        self.active = False
        self.queue.put("")  # Sentinel to unblock


class WebUIServer:
    """Full Terry WebUI server with REST API, SSE streaming, and static file serving."""

    STATIC_DIR = Path(__file__).parent / "static"

    def __init__(
        self,
        agent_factory: AgentLike | None = None,
        host: str = "127.0.0.1",
        port: int = 8670,
        api_key: str | None = None,
        rate_limit: int | None = None,
        rate_window: int | None = None,
        cors_origins: list[str] | None = None,
        enable_security: bool = True,
        config: Any = None,
    ):
        self.agent_factory = agent_factory
        self.host = host
        self.port = port
        self.sessions: dict[str, ChatSession] = {}
        self.sse_connections: dict[str, SSEConnection] = {}
        self._server: HTTPServer | None = None
        self._running = False

        # Security middleware (optional — enabled by default for production safety)
        if enable_security:
            from terry.core.security import SecurityMiddleware
            self.security = SecurityMiddleware(
                config=config,
                rate_limit=rate_limit,
                rate_window=rate_window,
                api_key=api_key,
                cors_origins=cors_origins,
            )
        else:
            self.security = None

    def _get_or_create_session(self, sid: str | None = None) -> ChatSession:
        sid = sid or str(uuid.uuid4())[:8]
        if sid not in self.sessions:
            self.sessions[sid] = ChatSession(sid)
        return self.sessions[sid]

    def start(self) -> None:
        """Start the WebUI server in a background thread."""
        if self._running:
            return

        server_instance = self

        class TerryHTTPHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(WebUIServer.STATIC_DIR), **kwargs)

            def log_message(self, format, *args):
                pass  # Suppress HTTP logs

            def do_GET(self):
                # === Security check ===
                allowed, err_msg, _ = self._check_security()
                if not allowed:
                    self._json_response({"error": err_msg}, 429)
                    return

                parsed = urlparse(self.path)
                path = parsed.path
                params = parse_qs(parsed.query)

                # API: Health check
                if path == "/api/health":
                    self._json_response({"status": "ok", "version": __version__})
                    return

                # API: Get sessions
                if path == "/api/sessions":
                    sessions = [
                        {"id": s.id, "message_count": len(s.messages)}
                        for s in server_instance.sessions.values()
                    ]
                    self._json_response({"sessions": sessions})
                    return

                # API: Get session messages
                if path.startswith("/api/sessions/") and "/messages" in path:
                    sid = path.split("/")[3]
                    session = server_instance.sessions.get(sid)
                    if session:
                        self._json_response(session.to_dict())
                    else:
                        self._json_response({"error": "Session not found"}, 404)
                    return

                # API: SSE stream
                if path == "/api/stream":
                    session_id = params.get("session", ["default"])[0]
                    self._handle_sse(session_id)
                    return

                # API: Status
                if path == "/api/status":
                    if server_instance.agent_factory:
                        try:
                            agent = server_instance.agent_factory()
                            status = agent.get_status()
                            tool_count = len(agent.tools.list_tools())
                            self._json_response({
                                **status,
                                "tools_available": tool_count,
                                "sessions": len(server_instance.sessions),
                            })
                        except Exception as e:
                            self._json_response({"error": str(e)}, 500)
                    else:
                        self._json_response({"status": "no agent"})
                    return

                # API: Tools list
                if path == "/api/tools":
                    if server_instance.agent_factory:
                        agent = server_instance.agent_factory()
                        tools = [
                            {"name": t.name, "description": t.description}
                            for t in agent.tools.list_tools()
                        ]
                        self._json_response({"tools": tools})
                    else:
                        self._json_response({"tools": []})
                    return

                # API: Background tasks
                if path == "/api/tasks":
                    from terry.core.background_registry import get_background_registry
                    status_filter = params.get("status", [None])[0]
                    tasks = get_background_registry().list(status=status_filter)
                    self._json_response({"tasks": [t.to_dict() for t in tasks]})
                    return

                # API: Agents list
                if path == "/api/agents":
                    from terry.core.background_registry import get_background_registry
                    reg = get_background_registry()
                    tasks = reg.list(limit=200)
                    agents_data = []
                    for t in tasks:
                        agents_data.append({
                            "id": t.id, "description": t.description[:120], "system": t.system,
                            "status": t.status, "parent_id": t.parent_id, "depth": t.depth,
                            "children": t.children, "error": (t.error or "")[:200],
                            "created": t.created_at if hasattr(t, "created_at") else "",
                        })
                    self._json_response({"agents": agents_data, "total": len(agents_data)})
                    return

                # API: Routines
                if path == "/api/routines":
                    from terry.core.scheduler import CronScheduler
                    s = CronScheduler()
                    self._json_response({"routines": s.list_tasks()})
                    return

                # Static files
                if path == "/" or path == "":
                    path = "/index.html"
                self.path = path
                try:
                    super().do_GET()
                except Exception:
                    self.send_error(404)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path

                # === Security check (with body size validation) ===
                content_length = int(self.headers.get("Content-Length", 0))
                allowed, err_msg, _ = self._check_security(content_length=content_length)
                if not allowed:
                    self._json_response({"error": err_msg}, 429)
                    return

                # API: Chat
                if path == "/api/chat":
                    body = self.rfile.read(content_length)
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        self._json_response({"error": "Invalid JSON"}, 400)
                        return

                    message = data.get("message", "")
                    session_id = data.get("session_id", str(uuid.uuid4())[:8])

                    if not message:
                        self._json_response({"error": "Message required"}, 400)
                        return

                    session = server_instance._get_or_create_session(session_id)
                    session.add_message("user", message)

                    # Notify SSE clients
                    server_instance._broadcast_sse("user_message", {
                        "session_id": session_id,
                        "message": message,
                    })

                    # Run agent
                    if server_instance.agent_factory:
                        try:
                            agent = server_instance.agent_factory()
                            response = agent.run(message)
                            session.add_message("assistant", response)

                            server_instance._broadcast_sse("assistant_message", {
                                "session_id": session_id,
                                "message": response,
                            })

                            self._json_response({
                                "session_id": session_id,
                                "response": response,
                                "tool_calls": agent.tool_call_count,
                            })
                        except Exception as e:
                            self._json_response({
                                "session_id": session_id,
                                "error": str(e),
                            }, 500)
                    else:
                        self._json_response({
                            "session_id": session_id,
                            "response": f"[No agent configured] Echo: {message}",
                        })

                # API: Feedback
                elif path == "/api/feedback":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        data = json.loads(body)
                        rating = data.get("rating", "skip")
                        if server_instance.agent_factory:
                            agent = server_instance.agent_factory()
                            agent.feedback.record_direct(
                                rating=rating,
                                session_id=data.get("session_id", ""),
                                user_message=data.get("user_message", ""),
                                assistant_response_preview=data.get("assistant_preview", ""),
                            )
                            self._json_response({"status": "recorded", "rating": rating})
                        else:
                            self._json_response({"status": "recorded", "rating": rating})
                    except json.JSONDecodeError:
                        self._json_response({"error": "Invalid JSON"}, 400)

                # API: Clear session
                elif path == "/api/sessions/clear":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        data = json.loads(body)
                        sid = data.get("session_id", "")
                        if sid in server_instance.sessions:
                            del server_instance.sessions[sid]
                            self._json_response({"status": "cleared"})
                        else:
                            self._json_response({"error": "Session not found"}, 404)
                    except json.JSONDecodeError:
                        self._json_response({"error": "Invalid JSON"}, 400)

                else:
                    self._json_response({"error": "Not found"}, 404)

            def do_OPTIONS(self):
                self.send_response(204)
                self._security_headers()
                self._cors_headers()
                self.end_headers()

            def _security_headers(self):
                """Send standard security headers on every response."""
                from terry.core.security_headers import SECURITY_HEADERS
                for key, value in SECURITY_HEADERS.items():
                    self.send_header(key, value)

            def _cors_headers(self):
                if server_instance.security:
                    cors_headers = server_instance.security.cors.get_headers(
                        self.headers.get("Origin")
                    )
                    for key, value in cors_headers.items():
                        self.send_header(key, value)
                else:
                    self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

            def _check_security(self, content_length: int = 0) -> tuple[bool, str, dict]:
                """Check request against security middleware.

                Returns (allowed, error_message, cors_headers).
                """
                if not server_instance.security:
                    return True, "", {}
                client_id = self.client_address[0]
                api_key = self.headers.get("Authorization", "").replace("Bearer ", "") or None
                origin = self.headers.get("Origin")
                return server_instance.security.check_request(
                    client_id=client_id,
                    api_key=api_key,
                    origin=origin,
                    content_length=content_length,
                )

            def _json_response(self, data: dict, status: int = 200):
                self.send_response(status)
                self._security_headers()
                self._cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

            def _handle_sse(self, session_id: str):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self._security_headers()
                self._cors_headers()
                self.end_headers()

                conn = SSEConnection()
                conn_id = f"{session_id}_{id(conn)}"
                server_instance.sse_connections[conn_id] = conn

                # Send welcome event
                conn.send("connected", {"session_id": session_id})

                try:
                    while conn.active:
                        try:
                            msg = conn.queue.get(timeout=15)
                            if not msg:
                                break
                            self.wfile.write(msg.encode())
                            self.wfile.flush()
                        except queue.Empty:
                            # Send keepalive comment
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    conn.close()
                    server_instance.sse_connections.pop(conn_id, None)

        self._server = HTTPServer((self.host, self.port), TerryHTTPHandler)
        self._running = True

        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()

        logger.info("Terry WebUI started at http://%s:%s", self.host, self.port)
        logger.info("Open in browser to start chatting!")

    def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.shutdown()

    def _broadcast_sse(self, event: str, data: dict) -> None:
        for conn in list(self.sse_connections.values()):
            try:
                conn.send(event, data)
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Client disconnected — normal, remove silently
                pass


def start_webui(agent_factory=None, host="127.0.0.1", port=8670,
                api_key=None, enable_security=True, config=None):
    """Convenience function to start the WebUI.

    Args:
        agent_factory: Factory function to create agent instances
        host: Bind address
        port: Bind port
        api_key: Optional API key for authentication
        enable_security: Enable runtime security middleware (rate limiting, CORS, auth)
        config: Optional TerryConfig for config-driven settings
    """
    import webbrowser
    server = WebUIServer(
        agent_factory=agent_factory,
        host=host,
        port=port,
        api_key=api_key,
        enable_security=enable_security,
        config=config,
    )
    server.start()
    # Auto-open browser
    webbrowser.open(f"http://{host}:{port}")
    return server
