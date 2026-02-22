from __future__ import annotations

import json
import logging
import re
from typing import Any

from structured_agents.grammar.artifacts import (
    EBNFGrammar,
    GrammarArtifact,
    StructuralTagGrammar,
)
from structured_agents.grammar.builders.function_gemma import (
    FunctionGemmaGrammarBuilder,
)
from structured_agents.grammar.builders.schema_aware_function_gemma import (
    FunctionGemmaSchemaGrammarBuilder,
)
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import Message, ToolCall, ToolSchema

logger = logging.getLogger(__name__)


class FunctionGemmaPlugin:
    """Plugin for Google's FunctionGemma models."""

    name = "function_gemma"
    supports_ebnf = True
    supports_structural_tags = True
    supports_json_schema = True

    _TOOL_CALL_PATTERN = re.compile(
        r"<start_function_call>call:([a-zA-Z_][a-zA-Z0-9_-]*)\{([^}]*)\}<end_function_call>"
    )

    def __init__(self) -> None:
        self._grammar_builder = FunctionGemmaGrammarBuilder()
        self._schema_grammar_builder = FunctionGemmaSchemaGrammarBuilder()

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

    def build_grammar(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> GrammarArtifact:
        """Build grammar artifact for FunctionGemma."""
        if config.mode == "json_schema":
            return self._schema_grammar_builder.build(tools, config)
        return self._grammar_builder.build(tools, config)

    def to_extra_body(self, artifact: GrammarArtifact) -> dict[str, Any] | None:
        """Convert grammar artifact to vLLM payload."""
        if artifact is None:
            return None

        if isinstance(artifact, (EBNFGrammar, StructuralTagGrammar)):
            return artifact.to_vllm_payload()

        raise ValueError(f"Unsupported artifact type: {type(artifact)}")

    def parse_response(
        self,
        content: str | None,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Parse FunctionGemma response."""
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
        """Parse FunctionGemma argument format."""
        args: dict[str, Any] = {}

        if not args_str.strip():
            return args

        try:
            json_str = (
                "{" + args_str + "}" if not args_str.startswith("{") else args_str
            )
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        escape_pattern = re.compile(r"(\w+):(?:<escape>([^<]*)<escape>|([^,}]+))")

        for match in escape_pattern.finditer(args_str):
            key = match.group(1)
            value = match.group(2) if match.group(2) is not None else match.group(3)

            try:
                args[key] = json.loads(value)
            except json.JSONDecodeError:
                args[key] = value.strip().strip("\"'")

        return args
