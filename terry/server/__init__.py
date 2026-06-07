"""FastAPI server for Terry - HTTP API, background tasks, and daemon mode."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from ..core.agent import Agent
from ..core.config import TerryConfig
from ..core.security import SecurityMiddleware


class TerryServer:
    """HTTP API server wrapping the Terry agent.

    Provides REST endpoints for chat, tool execution, status, and background tasks.
    Can run as a daemon with periodic scheduling.
    """

    def __init__(
        self,
        config: TerryConfig | None = None,
        workdir: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 8670,
        enable_daemon: bool = False,
        api_key: str | None = None,
        rate_limit: int = 100,
        rate_window: int = 60,
        cors_origins: list[str] | None = None,
        max_body_size: int = 10 * 1024 * 1024,
    ):
        self.config = config or TerryConfig()
        self.workdir = workdir or Path.cwd()
        self.host = host
        self.port = port
        self.enable_daemon = enable_daemon

        # Security middleware
        self.security = SecurityMiddleware(
            config=config,
            rate_limit=rate_limit,
            rate_window=rate_window,
            api_key=api_key,
            cors_origins=cors_origins,
            max_body_size=max_body_size,
        )

        self.agent: Agent | None = None
        self._background_tasks: dict[str, dict] = {}
        self._task_counter = 0
        self._running = False
        self._daemon_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the server and agent."""
        self.agent = Agent(
            config=self.config,
            workdir=self.workdir,
            enable_subagents=False,
        )
        self._running = True

        if self.enable_daemon:
            self._daemon_thread = threading.Thread(
                target=self._daemon_loop, daemon=True
            )
            self._daemon_thread.start()

    def stop(self) -> None:
        """Stop the server."""
        self._running = False

    def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        """Process a chat message and return the response.

        Args:
            message: User message
            session_id: Optional session identifier

        Returns:
            Dict with response, session_id, and metadata
        """
        if not self.agent:
            return {"error": "Server not started"}

        start_time = time.time()
        try:
            response = self.agent.run(message)
            duration = time.time() - start_time

            return {
                "response": response,
                "session_id": self.agent.session.session_id if self.agent.session else None,
                "duration_seconds": round(duration, 2),
                "tool_calls": self.agent.tool_call_count,
            }
        except Exception as e:
            return {"error": str(e)}

    def execute_tool(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """Execute a tool directly via the API.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Dict with result
        """
        if not self.agent:
            return {"error": "Server not started"}

        try:
            result = self.agent.tools.execute(tool_name, **arguments)
            return {"result": result, "tool": tool_name}
        except Exception as e:
            return {"error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """Get server and agent status."""
        if not self.agent:
            return {"status": "stopped"}

        status = self.agent.get_status()
        status["server_running"] = self._running
        status["background_tasks"] = len(self._background_tasks)
        return status

    def start_background_task(self, prompt: str, interval_minutes: int = 0) -> str:
        """Start a background task.

        Args:
            prompt: Task prompt
            interval_minutes: Repeat interval (0 = run once)

        Returns:
            Task ID
        """
        self._task_counter += 1
        task_id = f"bg_{self._task_counter}"

        self._background_tasks[task_id] = {
            "id": task_id,
            "prompt": prompt,
            "interval": interval_minutes,
            "status": "running",
            "last_run": None,
            "result": None,
        }

        # Run in background thread
        thread = threading.Thread(
            target=self._run_background_task,
            args=(task_id,),
            daemon=True,
        )
        thread.start()

        return task_id

    def _run_background_task(self, task_id: str) -> None:
        """Run a background task, optionally on a schedule."""
        task = self._background_tasks.get(task_id)
        if not task:
            return

        while self._running and task["status"] == "running":
            try:
                result = self.chat(task["prompt"])
                task["last_run"] = time.time()
                task["result"] = result
            except Exception as e:
                task["result"] = {"error": str(e)}

            if task["interval"] <= 0:
                task["status"] = "completed"
                break

            time.sleep(task["interval"] * 60)

    def _daemon_loop(self) -> None:
        """Daemon loop: periodically check for scheduled tasks."""
        while self._running:
            # Placeholder for cron-like scheduling
            time.sleep(60)

    def create_app(self):
        """Create a FastAPI/WSGI app for the server.

        Returns:
            A simple WSGI-compatible app
        """
        server = self  # Capture reference

        def app(environ: dict, start_response: callable) -> list[bytes]:
            """Simple WSGI app with security middleware."""
            path = environ.get("PATH_INFO", "/")
            method = environ.get("REQUEST_METHOD", "GET")

            # Extract security-relevant headers
            client_id = environ.get("REMOTE_ADDR", "global")
            api_key = environ.get("HTTP_AUTHORIZATION", "").replace("Bearer ", "")
            origin = environ.get("HTTP_ORIGIN")
            content_length = int(environ.get("CONTENT_LENGTH", 0))

            # Apply security middleware
            is_allowed, error_msg, cors_headers = server.security.check_request(
                client_id=client_id,
                api_key=api_key,
                origin=origin,
                content_length=content_length,
            )

            # Build response headers with CORS
            headers = [
                ("Content-Type", "application/json"),
            ]
            for key, value in cors_headers.items():
                headers.append((key, value))

            # Reject request if security check failed
            if not is_allowed:
                start_response("403 Forbidden", headers)
                return [json.dumps({"error": error_msg}).encode()]

            if method == "OPTIONS":
                start_response("204 No Content", headers)
                return []

            if path == "/status" and method == "GET":
                status = server.get_status()
                start_response("200 OK", headers)
                return [json.dumps(status).encode()]

            if path == "/chat" and method == "POST":
                try:
                    body = environ["wsgi.input"].read(content_length)
                    data = json.loads(body)
                    message = data.get("message", "")
                    result = server.chat(message)
                    start_response("200 OK", headers)
                    return [json.dumps(result).encode()]
                except Exception as e:
                    start_response("400 Bad Request", headers)
                    return [json.dumps({"error": str(e)}).encode()]

            if path.startswith("/tools/") and method == "POST":
                tool_name = path.split("/tools/", 1)[1]
                try:
                    body = environ["wsgi.input"].read(content_length)
                    data = json.loads(body)
                    result = server.execute_tool(tool_name, data)
                    start_response("200 OK", headers)
                    return [json.dumps(result).encode()]
                except Exception as e:
                    start_response("400 Bad Request", headers)
                    return [json.dumps({"error": str(e)}).encode()]

            start_response("404 Not Found", headers)
            return [json.dumps({"error": "Not found"}).encode()]

        return app


# Global instance
_server_instance: TerryServer | None = None


def get_server(
    config: TerryConfig | None = None,
    workdir: Path | None = None,
) -> TerryServer:
    """Get or create the global server instance."""
    global _server_instance
    if _server_instance is None:
        _server_instance = TerryServer(
            config=config,
            workdir=workdir,
        )
    return _server_instance


def set_server(instance: TerryServer) -> None:
    """Inject a custom server instance."""
    global _server_instance
    _server_instance = instance


def reset_server() -> None:
    """Reset server instance."""
    global _server_instance
    _server_instance = None
