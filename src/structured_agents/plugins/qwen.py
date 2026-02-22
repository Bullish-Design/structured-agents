from __future__ import annotations

import json
import logging
from typing import Any

from structured_agents.grammar.artifacts import GrammarArtifact
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import Message, ToolCall, ToolSchema

logger = logging.getLogger(__name__)


class QwenPlugin:
    """Plugin for Qwen/Qwen2.5 instruction-tuned models."""

    name = "qwen"
    supports_ebnf = False
    supports_structural_tags = False
    supports_json_schema = False

    def format_messages(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> list[dict[str, Any]]:
        """Format messages for Qwen."""
        return [msg.to_openai_format() for msg in messages]

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Format tools for the API."""
        return [tool.to_openai_format() for tool in tools]

    def build_grammar(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> GrammarArtifact:
        """Qwen uses standard tool calling, no grammar needed."""
        return None

    def to_extra_body(self, artifact: GrammarArtifact) -> dict[str, Any] | None:
        """Qwen doesn't use grammar constraints."""
        return None

    def parse_response(
        self,
        content: str | None,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Parse Qwen response (standard OpenAI format)."""
        tool_calls: list[ToolCall] = []

        if tool_calls_raw:
            for tc in tool_calls_raw:
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = (
                        json.loads(args_str) if isinstance(args_str, str) else args_str
                    )
                except json.JSONDecodeError:
                    args = {}
                    logger.warning("Failed to parse arguments: %s", args_str)

                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", f"call_{id(tc)}"),
                        name=func.get("name", "unknown"),
                        arguments=args,
                    )
                )

        return content, tool_calls
