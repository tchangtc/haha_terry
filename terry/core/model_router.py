"""Model router - route tasks to appropriate models based on complexity."""

from __future__ import annotations

from typing import Any


class ModelRouter:
    """Routes tasks to different models based on complexity analysis.

    Simple tasks (file reading, basic search) → cheap model (saves cost)
    Complex tasks (refactoring, debugging, planning) → powerful model
    """

    # Keywords that indicate complex tasks
    COMPLEX_KEYWORDS = [
        "refactor", "restructure", "debug", "optimize", "analyze",
        "security", "vulnerability", "review", "audit", "migrate",
        "architecture", "design", "implement", "create", "build",
        "deploy", "configure", "integrate", "fix bug", "resolve",
        "explain why", "how does", "what is the best",
    ]

    # Keywords that indicate simple tasks
    SIMPLE_KEYWORDS = [
        "read", "show", "list", "what file", "find", "search",
        "cat", "ls", "display", "check", "get", "status",
        "where is", "which file", "look at",
    ]

    def __init__(
        self,
        complex_client: Any = None,
        simple_client: Any = None,
    ):
        """Initialize model router.

        Args:
            complex_client: LLM client for complex tasks (e.g., Claude Sonnet 4)
            simple_client: LLM client for simple tasks (e.g., Claude Haiku)
        """
        self.complex_client = complex_client
        self.simple_client = simple_client

    def analyze_complexity(self, user_input: str) -> str:
        """Analyze user input to determine task complexity.

        Returns:
            "simple", "complex", or "medium"
        """
        text_lower = user_input.lower()

        complex_score = sum(
            1 for kw in self.COMPLEX_KEYWORDS if kw in text_lower
        )
        simple_score = sum(
            1 for kw in self.SIMPLE_KEYWORDS if kw in text_lower
        )
        text_length = len(user_input)

        # Length-based heuristic
        if text_length > 200:
            complex_score += 1
        elif text_length < 50:
            simple_score += 1

        if complex_score > simple_score:
            return "complex"
        elif simple_score > complex_score:
            return "simple"
        return "medium"

    def route(self, user_input: str) -> Any:
        """Route to appropriate client based on task complexity.

        Returns:
            The appropriate LLM client
        """
        if self.simple_client is None:
            return self.complex_client
        if self.complex_client is None:
            return self.simple_client

        complexity = self.analyze_complexity(user_input)

        if complexity == "complex":
            return self.complex_client
        elif complexity == "simple":
            return self.simple_client
        else:
            # Medium complexity: use complex client (safer)
            return self.complex_client

    def get_estimated_savings(self, messages: list[dict]) -> dict[str, Any]:
        """Estimate cost savings from using simple model for simple tasks.

        Returns:
            Dictionary with estimated savings info
        """
        simple_ratio = sum(
            1 for msg in messages
            if msg.get("role") == "user" and
            self.analyze_complexity(str(msg.get("content", ""))) == "simple"
        ) / max(len(messages), 1)

        return {
            "simple_task_ratio": simple_ratio,
            "potential_savings_pct": int(simple_ratio * 80),  # Haiku is ~80% cheaper
        }
