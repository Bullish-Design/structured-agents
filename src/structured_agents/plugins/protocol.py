"""Model plugin protocol definition."""

from __future__ import annotations

from typing import Any, Protocol

from structured_agents.types import Message, ToolCall, ToolSchema


class ModelPlugin(Protocol):
    """Protocol for model-specific formatting and parsing.

    Different models have different expectations for:
    - How messages are formatted
    - How tool calls are represented in output
    - What grammar constraints to apply

    Implementations handle these model-specific quirks.
    """

    @property
    def name(self) -> str:
        """Plugin identifier (e.g., 'function_gemma', 'qwen')."""
        ...

    def format_messages(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> list[dict[str, Any]]:
        """Convert messages to model-specific API format.

        Args:
            messages: Conversation history.
            tools: Available tools (may affect formatting).

        Returns:
            List of message dicts ready for the API.
        """
        ...

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Convert tool schemas to API format.

        Args:
            tools: Tool schemas.

        Returns:
            List of tool dicts ready for the API.
        """
        ...

    def build_grammar(self, tools: list[ToolSchema]) -> str | None:
        """Build XGrammar EBNF for constrained decoding.

        Args:
            tools: Available tools.

        Returns:
            EBNF grammar string, or None to disable grammar enforcement.
        """
        ...

    def parse_response(
        self,
        content: str | None,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Parse model response into content and tool calls.

        Args:
            content: Response text content (may be None).
            tool_calls_raw: Raw tool calls from API (may be None).

        Returns:
            Tuple of (text_content, list_of_tool_calls).
        """
        ...

    def extra_body(self, grammar: str | None) -> dict[str, Any] | None:
        """Build extra_body for vLLM structured outputs.

        Args:
            grammar: EBNF grammar string (may be None).

        Returns:
            Dict to pass as extra_body to the API, or None.
        """
        ...
