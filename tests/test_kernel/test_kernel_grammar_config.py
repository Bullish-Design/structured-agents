"""Tests for kernel grammar config propagation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.client.protocol import CompletionResponse
from structured_agents.grammar.config import GrammarConfig
from structured_agents.kernel import AgentKernel
from structured_agents.types import KernelConfig, Message, TokenUsage, ToolSchema


class CapturingPlugin:
    name = "capturing"
    supports_ebnf = True
    supports_structural_tags = True
    supports_json_schema = False

    def __init__(self) -> None:
        self.seen_config: GrammarConfig | None = None

    def format_messages(
        self, messages: list[Message], tools: list[ToolSchema]
    ) -> list[dict[str, Any]]:
        return [message.to_openai_format() for message in messages]

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        return [tool.to_openai_format() for tool in tools]

    def build_grammar(self, tools: list[ToolSchema], config: GrammarConfig) -> None:
        self.seen_config = config
        return None

    def to_extra_body(self, artifact: Any) -> None:
        return None

    def parse_response(
        self, content: str | None, tool_calls_raw: Any
    ) -> tuple[str | None, list[Any]]:
        return content, []


@pytest.mark.asyncio
async def test_kernel_uses_grammar_config() -> None:
    plugin = CapturingPlugin()
    grammar_config = GrammarConfig(
        mode="structural_tag", allow_parallel_calls=False, args_format="json"
    )

    kernel = AgentKernel(
        config=KernelConfig(base_url="http://localhost:8000/v1", model="test"),
        plugin=plugin,
        backend=PythonBackend(),
        grammar_config=grammar_config,
    )

    response = CompletionResponse(
        content="hello",
        tool_calls=None,
        usage=TokenUsage(1, 1, 2),
        finish_reason="stop",
        raw_response={},
    )
    kernel._client.chat_completion = AsyncMock(return_value=response)

    tools = [ToolSchema(name="echo", description="", parameters={})]
    await kernel.step([Message(role="user", content="hi")], tools)

    assert plugin.seen_config == grammar_config
