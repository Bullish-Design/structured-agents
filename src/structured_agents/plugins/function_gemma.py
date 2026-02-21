"""FunctionGemma model plugin implementation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from structured_agents.plugins.grammar.function_gemma import build_functiongemma_grammar
from structured_agents.types import Message, ToolCall, ToolSchema

logger = logging.getLogger(__name__)


class FunctionGemmaPlugin:
    """Plugin for Google's FunctionGemma models.

    FunctionGemma uses a specific output format:
        <start_function_call>call:tool_name{arg1:value1}<end_function_call>

    This plugin handles:
    - Building the appropriate grammar for constrained decoding
    - Parsing tool calls from the constrained output
    - Formatting messages in the expected format
    """

    name = "function_gemma"

    _TOOL_CALL_PATTERN = re.compile(
        r"<start_function_call>call:(\w+)\{([^}]*)\}<end_function_call>"
    )
    _ARG_PATTERN = re.compile(r"(\w+):([^,}]+(?:,[^,}]+)*)")

    def format_messages(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> list[dict[str, Any]]:
        """Format messages for FunctionGemma."""
        return [msg.to_openai_format() for msg in messages]

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Format tools for the API."""
        return [tool.to_openai_format() for tool in tools]

    def build_grammar(self, tools: list[ToolSchema]) -> str | None:
        """Build EBNF grammar for FunctionGemma format."""
        if not tools:
            return None
        return build_functiongemma_grammar(tools)

    def parse_response(
        self,
        content: str | None,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Parse FunctionGemma response.

        FunctionGemma can output tool calls in two ways:
        1. Standard OpenAI format (tool_calls_raw)
        2. Grammar-constrained format in content

        We check both and prefer standard format if present.
        """
        tool_calls: list[ToolCall] = []

        if tool_calls_raw:
            for tc in tool_calls_raw:
                try:
                    func = tc.get("function", {})
                    args_str = func.get("arguments", "{}")
                    args = (
                        json.loads(args_str) if isinstance(args_str, str) else args_str
                    )
                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", f"call_{id(tc)}"),
                            name=func.get("name", "unknown"),
                            arguments=args,
                        )
                    )
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Failed to parse tool call: %s", exc)
            return content, tool_calls

        if content:
            matches = self._TOOL_CALL_PATTERN.findall(content)
            for name, args_str in matches:
                args = self._parse_arguments(args_str)
                tool_calls.append(ToolCall.create(name=name, arguments=args))

            if tool_calls:
                return None, tool_calls

        return content, tool_calls

    def _parse_arguments(self, args_str: str) -> dict[str, Any]:
        """Parse FunctionGemma argument format.

        Format: key1:value1,key2:value2
        Values may be JSON or plain strings.
        """
        args: dict[str, Any] = {}

        if not args_str.strip():
            return args

        try:
            if not args_str.strip().startswith("{"):
                args_str_json = "{" + args_str + "}"
            else:
                args_str_json = args_str
            return json.loads(args_str_json)
        except json.JSONDecodeError:
            pass

        for match in self._ARG_PATTERN.finditer(args_str):
            key, value = match.groups()
            try:
                args[key] = json.loads(value)
            except json.JSONDecodeError:
                args[key] = value.strip().strip("\"'")

        return args

    def extra_body(self, grammar: str | None) -> dict[str, Any] | None:
        """Build extra_body for vLLM structured outputs."""
        if not grammar:
            return None

        return {
            "structured_outputs": {
                "grammar": grammar,
            }
        }
