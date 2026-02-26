"""Model adapter for specific model families."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from structured_agents.types import Message, ToolSchema


@dataclass(frozen=True)
class ModelAdapter:
    """Adapts the kernel's generic tool-call loop to a specific model family."""

    name: str
    grammar_builder: Callable[[list[ToolSchema], Any], dict[str, Any] | None]
    response_parser: Any  # ResponseParser
    format_messages: Callable[[list[Message], list[dict]], list[dict]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict]] | None = None

    def __post_init__(self):
        # Set defaults if not provided
        if self.format_messages is None:
            object.__setattr__(self, "format_messages", self._default_format_messages)
        if self.format_tools is None:
            object.__setattr__(self, "format_tools", self._default_format_tools)

    @staticmethod
    def _default_format_messages(
        messages: list[Message], tools: list[dict]
    ) -> list[dict]:
        result = []
        for msg in messages:
            msg_dict = msg.to_openai_format()
            result.append(msg_dict)
        if tools:
            result.append(
                {"role": "system", "content": "Available tools: " + str(tools)}
            )
        return result

    @staticmethod
    def _default_format_tools(tool_schemas: list[ToolSchema]) -> list[dict]:
        return [ts.to_openai_format() for ts in tool_schemas]
