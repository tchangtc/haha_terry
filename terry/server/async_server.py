"""FastAPI/ASGI server for Terry — true async HTTP server.

Replaces WSGI-based TerryServer with FastAPI for:
- True async request handling
- WebSocket support for streaming
- Better concurrency (100+ concurrent requests)
- Modern async/await API
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from terry import __version__

# ── Request/Response Models ─────────────────────────────────────────

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: str | None = None
    stream: bool = False
    max_tokens: int | None = None


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    session_id: str
    duration_seconds: float
    tool_calls: int = 0
    tokens_used: int = 0


class ToolRequest(BaseModel):
    """Tool execution request."""
    tool_name: str
    arguments: dict[str, Any]


class ToolResponse(BaseModel):
    """Tool execution response."""
    result: str
    duration_seconds: float


class StatusResponse(BaseModel):
    """Server status response."""
    status: str
    uptime_seconds: float
    sessions: int
    version: str


class SubAgentRequest(BaseModel):
    """Sub-agent spawn request."""
    prompt: str
    timeout: float = 300.0
    pattern: str = "sequential"


class SubAgentResponse(BaseModel):
    """Sub-agent response."""
    agent_id: str
    status: str
    result: str | None = None
    error: str | None = None


# ── Async Server ────────────────────────────────────────────────────

class AsyncTerryServer:
    """Async HTTP server using FastAPI.

    Provides:
    - /chat - Chat endpoint (sync and streaming)
    - /tools/{name} - Tool execution
    - /status - Server status
    - /subagent - Sub-agent management
    - /ws - WebSocket for streaming
    """

    def __init__(
        self,
        config: Any = None,
        workdir: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 8670,
        cors_origins: list[str] | None = None,
        api_key: str | None = None,
        rate_limit: int = 100,
        rate_window: int = 60,
        enable_security: bool = True,
    ):
        self.config = config
        self.workdir = workdir or Path.cwd()
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["http://127.0.0.1:8670", "http://localhost:8670"]

        # Security middleware
        if enable_security:
            from terry.core.security import SecurityMiddleware
            self.security = SecurityMiddleware(
                rate_limit=rate_limit,
                rate_window=rate_window,
                api_key=api_key,
                cors_origins=cors_origins,
            )
        else:
            self.security = None

        self.app = FastAPI(title="Terry API", version=__version__)
        self._setup_security_middleware()
        self._setup_cors()
        self._setup_routes()

        self._start_time = time.time()
        self._sessions: dict[str, dict] = {}
        self._agent_factory: Callable | None = None
        self._sub_agent_manager: Any = None

    def _setup_security_middleware(self) -> None:
        """Setup Terry security middleware (rate limiting, auth, validation)."""
        if not self.security:
            return

        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from fastapi import HTTPException

        security_ref = self.security

        class TerrySecurityMiddleware(BaseHTTPMiddleware):
            """FastAPI middleware that delegates to Terry's SecurityMiddleware."""

            async def dispatch(self, request: Request, call_next):
                # Extract client info
                client_id = request.client.host if request.client else "unknown"
                api_key = request.headers.get("Authorization", "").replace("Bearer ", "") or None
                origin = request.headers.get("Origin")
                content_length = request.headers.get("Content-Length", "0")

                # Run security check
                allowed, err_msg, _ = security_ref.check_request(
                    client_id=client_id,
                    api_key=api_key,
                    origin=origin,
                    content_length=int(content_length) if content_length.isdigit() else 0,
                )

                if not allowed:
                    return JSONResponse(
                        status_code=429 if "Rate limit" in err_msg else 401 if "API key" in err_msg else 413,
                        content={"error": err_msg},
                    )

                return await call_next(request)

        self.app.add_middleware(TerrySecurityMiddleware)

    def _setup_cors(self) -> None:
        """Setup CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """Setup all API routes."""

        @self.app.get("/status", response_model=StatusResponse)
        async def get_status():
            """Get server status."""
            return StatusResponse(
                status="running",
                uptime_seconds=round(time.time() - self._start_time, 2),
                sessions=len(self._sessions),
                version=__version__,
            )

        @self.app.post("/chat", response_model=ChatResponse)
        async def chat(request: ChatRequest):
            """Chat with Terry (non-streaming)."""
            if not self._agent_factory:
                raise HTTPException(status_code=503, detail="Agent not initialized")

            session_id = request.session_id or str(uuid.uuid4())
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "messages": [],
                    "created_at": datetime.now().isoformat(),
                }

            start_time = time.time()

            # Get or create agent
            agent = self._agent_factory()

            # Use async if available
            if hasattr(agent, "arun"):
                response = await agent.arun(request.message)
            else:
                # Fallback to sync
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, agent.run, request.message)

            duration = time.time() - start_time

            # Get metrics
            tool_calls = 0
            tokens_used = 0
            if hasattr(agent, "get_metrics_summary"):
                metrics = agent.get_metrics_summary()
                tool_calls = metrics.get("counters", {}).get("tool_calls", 0)
                tokens_used = (
                    metrics.get("counters", {}).get("input_tokens", 0)
                    + metrics.get("counters", {}).get("output_tokens", 0)
                )

            return ChatResponse(
                response=response,
                session_id=session_id,
                duration_seconds=round(duration, 2),
                tool_calls=tool_calls,
                tokens_used=tokens_used,
            )

        @self.app.post("/chat/stream")
        async def chat_stream(request: ChatRequest):
            """Chat with Terry (streaming via SSE)."""
            if not self._agent_factory:
                raise HTTPException(status_code=503, detail="Agent not initialized")

            async def event_stream():
                agent = self._agent_factory()

                # Use async streaming if available
                if hasattr(agent, "arun_stream"):
                    async for chunk in agent.arun_stream(request.message):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    yield "data: [DONE]\n\n"
                else:
                    # Fallback: run sync and send full response
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(None, agent.run, request.message)
                    yield f"data: {json.dumps({'chunk': response})}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
            )

        @self.app.post("/tools/{tool_name}", response_model=ToolResponse)
        async def execute_tool(tool_name: str, request: ToolRequest):
            """Execute a tool."""
            if not self._agent_factory:
                raise HTTPException(status_code=503, detail="Agent not initialized")

            agent = self._agent_factory()
            start_time = time.time()

            # Execute tool
            if hasattr(agent, "tools") and hasattr(agent.tools, "execute"):
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: agent.tools.execute(tool_name, **request.arguments)
                )
            else:
                raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")

            duration = time.time() - start_time

            return ToolResponse(
                result=result,
                duration_seconds=round(duration, 2),
            )

        @self.app.post("/subagent/spawn", response_model=SubAgentResponse)
        async def spawn_subagent(request: SubAgentRequest):
            """Spawn a sub-agent."""
            if not self._sub_agent_manager:
                raise HTTPException(status_code=503, detail="Sub-agent manager not initialized")

            agent_id = await self._sub_agent_manager.spawn(
                prompt=request.prompt,
                timeout=request.timeout,
            )

            return SubAgentResponse(
                agent_id=agent_id,
                status="spawned",
            )

        @self.app.post("/subagent/{agent_id}/wait", response_model=SubAgentResponse)
        async def wait_subagent(agent_id: str, timeout: float = 300.0):
            """Wait for a sub-agent to complete."""
            if not self._sub_agent_manager:
                raise HTTPException(status_code=503, detail="Sub-agent manager not initialized")

            result = await self._sub_agent_manager.wait(agent_id, timeout)

            status = self._sub_agent_manager.get_status(agent_id)

            return SubAgentResponse(
                agent_id=agent_id,
                status=status.get("status", "unknown"),
                result=result if isinstance(result, str) else str(result),
                error=status.get("error"),
            )

        @self.app.get("/subagent/{agent_id}/status")
        async def get_subagent_status(agent_id: str):
            """Get sub-agent status."""
            if not self._sub_agent_manager:
                raise HTTPException(status_code=503, detail="Sub-agent manager not initialized")

            return self._sub_agent_manager.get_status(agent_id)

        @self.app.post("/subagent/{agent_id}/cancel")
        async def cancel_subagent(agent_id: str):
            """Cancel a sub-agent."""
            if not self._sub_agent_manager:
                raise HTTPException(status_code=503, detail="Sub-agent manager not initialized")

            success = await self._sub_agent_manager.cancel(agent_id)
            return {"success": success}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for streaming chat."""
            await websocket.accept()

            if not self._agent_factory:
                await websocket.send_json({"error": "Agent not initialized"})
                await websocket.close()
                return

            try:
                while True:
                    # Receive message
                    data = await websocket.receive_text()
                    request = json.loads(data)
                    message = request.get("message", "")

                    # Stream response
                    agent = self._agent_factory()

                    if hasattr(agent, "arun_stream"):
                        async for chunk in agent.arun_stream(message):
                            await websocket.send_json({"chunk": chunk})
                        await websocket.send_json({"done": True})
                    else:
                        # Fallback: sync
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(None, agent.run, message)
                        await websocket.send_json({"chunk": response})
                        await websocket.send_json({"done": True})

            except WebSocketDisconnect:
                pass

    def set_agent_factory(self, factory: Callable) -> None:
        """Set the agent factory.

        Args:
            factory: Callable that returns an Agent instance
        """
        self._agent_factory = factory

    def set_sub_agent_manager(self, manager: Any) -> None:
        """Set the sub-agent manager.

        Args:
            manager: AsyncSubAgentManager instance
        """
        self._sub_agent_manager = manager

    async def start(self) -> None:
        """Start the server (for programmatic use)."""
        import uvicorn
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def run(self) -> None:
        """Run the server (blocking)."""
        import uvicorn
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )


def create_async_server(
    config: Any = None,
    workdir: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8670,
) -> AsyncTerryServer:
    """Factory function to create async server.

    Args:
        config: TerryConfig instance
        workdir: Working directory
        host: Host to bind to
        port: Port to bind to

    Returns:
        AsyncTerryServer instance
    """
    return AsyncTerryServer(
        config=config,
        workdir=workdir,
        host=host,
        port=port,
    )
