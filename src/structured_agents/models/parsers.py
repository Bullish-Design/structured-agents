"""Response parser implementations."""

from __future__ import annotations
import json
import re
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
                    args = json.loads(func.get("arguments", "{}"))
                    parsed.append(ToolCall.create(func["name"], args))
            return None, parsed

        # Try to parse XML-style tool calls from content
        if content:
            tool_calls = self._parse_xml_tool_calls(content)
            if tool_calls:
                return None, tool_calls

        return content, []

    def _parse_xml_tool_calls(self, content: str) -> list[ToolCall]:
        """Parse XML-style tool calls from content."""
        # Pattern: <tool_call>{...}</tool_call>
        pattern = r"<tool_call>(.*?)</tool_call>"

        tool_calls = []
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            inner = match.strip()
            try:
                data = json.loads(inner)
                name = data.get("name", "")
                args = data.get("arguments", {})
                if name:
                    tool_calls.append(ToolCall.create(name, args))
            except json.JSONDecodeError:
                pass

        return tool_calls


class FunctionGemmaResponseParser:
    """Parser for FunctionGemma models."""

    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]:
        # Similar to Qwen but handles structural tags differently
        return QwenResponseParser().parse(content, tool_calls)
