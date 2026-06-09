"""Typed tool errors — structured error messages that help LLMs self-correct.

Inspired by OpenCode's ``InvalidArgumentsError`` pattern. Instead of returning
raw strings like ``"Error: file not found"``, tools raise typed errors that
auto-generate model-facing prose — telling the LLM *what* went wrong and *how*
to fix it.

Usage in tools::

    from ..core.tool_error import InvalidArgumentsError, ExecutionError

    class ReadFileTool(BaseTool):
        def execute(self, path: str, **kwargs) -> str:
            if not path:
                raise InvalidArgumentsError(
                    tool_name=self.name,
                    detail="'path' parameter is required and must be non-empty",
                )
            try:
                return Path(path).read_text()
            except FileNotFoundError:
                raise ExecutionError(
                    tool_name=self.name,
                    detail=f"File not found: {path}",
                    suggestion=f"Check available files with 'ls' or 'glob' tools",
                ) from None
"""

from __future__ import annotations


class ToolError(Exception):
    """Base class for typed tool errors.

    Every subclass must provide a ``to_llm_message()`` that returns a
    string suitable for feeding back into the LLM conversation.

    Attributes:
        tool_name: Name of the tool that raised the error.
        detail: Human-readable error detail.
        suggestion: Optional hint for how the LLM can fix the issue.
    """

    def __init__(
        self,
        tool_name: str,
        detail: str = "",
        suggestion: str = "",
    ) -> None:
        self.tool_name = tool_name
        self.detail = detail
        self.suggestion = suggestion
        super().__init__(self.to_llm_message())

    def to_llm_message(self) -> str:
        """Generate a model-facing error message.

        The message is designed to be appended as a ``tool_result`` so the
        LLM can read it and self-correct on the next turn.
        """
        msg = f"Tool '{self.tool_name}' failed: {self.detail}"
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class InvalidArgumentsError(ToolError):
    """Raised when tool arguments fail validation.

    The LLM receives a message telling it which argument was wrong and
    what the expected schema is, so it can rewrite the call correctly.

    Example::

        raise InvalidArgumentsError(
            tool_name="read_file",
            detail="'path' must be a valid file path string",
            suggestion="Provide an absolute or relative path to an existing file",
        )
    """

    def to_llm_message(self) -> str:
        msg = (
            f"Tool '{self.tool_name}' was called with invalid arguments.\n"
            f"{self.detail}\n"
            "Please rewrite the input so it satisfies the expected schema."
        )
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class ExecutionError(ToolError):
    """Raised when a tool fails at runtime.

    This covers file-not-found, command-nonzero-exit, network-timeout, etc.
    The LLM receives structured context to help it recover.

    Attributes:
        exit_code: Optional OS-level exit code (for subprocess failures).
    """

    def __init__(
        self,
        tool_name: str,
        detail: str = "",
        suggestion: str = "",
        exit_code: int | None = None,
    ) -> None:
        self.exit_code = exit_code
        super().__init__(tool_name=tool_name, detail=detail, suggestion=suggestion)

    def to_llm_message(self) -> str:
        parts = [f"Tool '{self.tool_name}' failed during execution."]
        if self.exit_code is not None:
            parts.append(f"Exit code: {self.exit_code}")
        if self.detail:
            parts.append(self.detail)
        msg = "\n".join(parts)
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class PermissionDeniedError(ToolError):
    """Raised when the security system blocks a tool call.

    The LLM receives the reason so it can find an alternative approach
    rather than retrying the same blocked operation.
    """

    def to_llm_message(self) -> str:
        msg = (
            f"Tool '{self.tool_name}' was blocked by the security policy.\n"
            f"Reason: {self.detail}"
        )
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class RateLimitError(ToolError):
    """Raised when a tool hits a rate limit.

    The LLM receives backoff guidance so it can retry later or batch calls.
    """

    def __init__(
        self,
        tool_name: str,
        detail: str = "",
        suggestion: str = "",
        retry_after_seconds: float = 5.0,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(tool_name=tool_name, detail=detail, suggestion=suggestion)

    def to_llm_message(self) -> str:
        msg = (
            f"Tool '{self.tool_name}' is being rate-limited.\n"
            f"Retry after: {self.retry_after_seconds:.0f} seconds"
        )
        if self.detail:
            msg += f"\n{self.detail}"
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class TimeoutError(ToolError):
    """Raised when a tool exceeds its execution timeout.

    The LLM receives suggestions for breaking the work into smaller steps.
    """

    def __init__(
        self,
        tool_name: str,
        detail: str = "",
        suggestion: str = "",
        timeout_seconds: float = 120.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(tool_name=tool_name, detail=detail, suggestion=suggestion)

    def to_llm_message(self) -> str:
        msg = (
            f"Tool '{self.tool_name}' exceeded its timeout "
            f"({self.timeout_seconds:.0f}s).\n"
            "Consider breaking the operation into smaller steps or using "
            "more specific parameters."
        )
        if self.detail:
            msg += f"\n{self.detail}"
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg
