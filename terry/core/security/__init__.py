"""Security sub-package — permissions, checkpoints, and access control."""

# Runtime security middleware
import shlex
import threading
import time
from collections import defaultdict
from collections.abc import Callable

from ..checkpoint import (
    CheckpointManager,
    get_checkpoint_manager,
    reset_checkpoint_manager,
    set_checkpoint_manager,
)
from ..permissions import (
    PermissionLevel,
    PermissionRule,
    PermissionStore,
    get_permission_store,
    reset_permission_store,
    set_permission_store,
)


class RateLimiter:
    """Token bucket rate limiter for API endpoints.

    Implements a sliding window rate limit to prevent DDoS attacks.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str = "global") -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]
            if len(self._requests[client_id]) >= self.max_requests:
                return False
            self._requests[client_id].append(now)
            return True

    def get_remaining(self, client_id: str = "global") -> int:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]
            return max(0, self.max_requests - len(self._requests[client_id]))


class RequestValidator:
    """Validate and sanitize incoming requests."""

    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_PROMPT_LENGTH = 100_000
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "sudo rm",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=",
        "chmod -r 777 /",
        "| bash",
        "| sh",
    ]

    @classmethod
    def validate_body_size(cls, content_length: int) -> tuple[bool, str]:
        if content_length > cls.MAX_BODY_SIZE:
            return False, f"Request body too large: {content_length} > {cls.MAX_BODY_SIZE} bytes"
        return True, ""

    @classmethod
    def validate_prompt(cls, prompt: str) -> tuple[bool, str]:
        if len(prompt) > cls.MAX_PROMPT_LENGTH:
            return False, f"Prompt too long: {len(prompt)} > {cls.MAX_PROMPT_LENGTH} characters"
        prompt_lower = prompt.lower()
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern in prompt_lower:
                return False, f"Dangerous pattern detected: {pattern}"
        return True, ""

    @classmethod
    def sanitize_bash_command(cls, command: str) -> tuple[bool, str, str]:
        command = command.strip()
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern in command:
                return False, "", f"Blocked dangerous pattern: {pattern}"
        try:
            shlex.split(command)
        except ValueError as e:
            return False, "", f"Invalid command syntax: {e}"
        return True, command, ""


class APIKeyAuth:
    """API key authentication middleware."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def is_enabled(self) -> bool:
        return self.api_key is not None

    def validate(self, provided_key: str | None) -> bool:
        if not self.is_enabled():
            return True
        if not provided_key:
            return False
        return provided_key == self.api_key


class CORSPolicy:
    """CORS (Cross-Origin Resource Sharing) policy."""

    def __init__(
        self,
        allowed_origins: list[str] | None = None,
        allowed_methods: list[str] | None = None,
        allowed_headers: list[str] | None = None,
    ):
        self.allowed_origins = allowed_origins
        self.allowed_methods = allowed_methods or ["GET", "POST", "OPTIONS"]
        self.allowed_headers = allowed_headers or ["Content-Type", "Authorization"]

    def is_origin_allowed(self, origin: str) -> bool:
        if self.allowed_origins is None:
            return True
        return origin in self.allowed_origins

    def get_headers(self, origin: str | None = None) -> dict[str, str]:
        headers = {}
        if self.allowed_origins is None:
            headers["Access-Control-Allow-Origin"] = "*"
        elif origin and self.is_origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
        headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
        return headers


class SecurityMiddleware:
    """Combined security middleware for Terry server."""

    def __init__(
        self,
        rate_limit: int = 100,
        rate_window: int = 60,
        api_key: str | None = None,
        cors_origins: list[str] | None = None,
        max_body_size: int = 10 * 1024 * 1024,
    ):
        self.rate_limiter = RateLimiter(rate_limit, rate_window)
        self.api_auth = APIKeyAuth(api_key)
        self.cors = CORSPolicy(cors_origins)
        self.max_body_size = max_body_size

    def check_request(
        self,
        client_id: str = "global",
        api_key: str | None = None,
        origin: str | None = None,
        content_length: int = 0,
    ) -> tuple[bool, str, dict[str, str]]:
        if not self.rate_limiter.is_allowed(client_id):
            remaining = self.rate_limiter.get_remaining(client_id)
            return False, f"Rate limit exceeded. Remaining: {remaining}", {}
        if not self.api_auth.validate(api_key):
            return False, "Invalid or missing API key", {}
        if content_length > self.max_body_size:
            return False, f"Request body too large: {content_length} > {self.max_body_size}", {}
        cors_headers = self.cors.get_headers(origin)
        return True, "", cors_headers
