"""Response parser implementations."""

from __future__ import annotations
from typing import Any, Protocol
from structured_agents.types import ToolCall


class ResponseParser(Protocol):
    """Parses model responses to extract tool calls."""

    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]: ...


class QwenResponseParser:
    """Parser for Qwen models."""

    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]:
        if tool_calls:
            parsed = []
            for tc in tool_calls:
                if isinstance(tc, dict) and "function" in tc:
                    func = tc["function"]
                    import json

                    args = json.loads(func.get("arguments", "{}"))
                    parsed.append(ToolCall.create(func["name"], args))
            return None, parsed
        return content, []


class FunctionGemmaResponseParser:
    """Parser for FunctionGemma models."""

    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]:
        # Similar to Qwen but handles structural tags differently
        return QwenResponseParser().parse(content, tool_calls)
