"""Tests for kernel tool registry resolution."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.client.protocol import CompletionResponse
from structured_agents.exceptions import KernelError
from structured_agents.kernel import AgentKernel
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
from structured_agents.types import KernelConfig, Message, TokenUsage, ToolSchema


class RecordingPlugin:
    name = "recording"
    supports_ebnf = False
    supports_structural_tags = False
    supports_json_schema = False

    def __init__(self) -> None:
        self.seen_tools: list[ToolSchema] | None = None

    def format_messages(
        self, messages: list[Message], tools: list[ToolSchema]
    ) -> list[dict[str, Any]]:
        self.seen_tools = tools
        return [message.to_openai_format() for message in messages]

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        return [tool.to_openai_format() for tool in tools]

    def build_grammar(self, tools: list[ToolSchema], config: Any) -> None:
        return None

    def to_extra_body(self, artifact: Any) -> None:
        return None

    def parse_response(
        self, content: str | None, tool_calls_raw: Any
    ) -> tuple[str | None, list[Any]]:
        return content, []


@pytest.mark.asyncio
async def test_step_resolves_tools_from_registry() -> None:
    registry = PythonRegistry()
    backend = PythonBackend(registry=registry)

    async def echo(message: str) -> str:
        return message

    registry.register("echo", echo)

    plugin = RecordingPlugin()
    tool_source = RegistryBackendToolSource(registry, backend)
    kernel = AgentKernel(
        config=KernelConfig(base_url="http://localhost:8000/v1", model="test"),
        plugin=plugin,
        tool_source=tool_source,
    )

    response = CompletionResponse(
        content="hello",
        tool_calls=None,
        usage=TokenUsage(1, 1, 2),
        finish_reason="stop",
        raw_response={},
    )
    kernel._client.chat_completion = AsyncMock(return_value=response)

    await kernel.step([Message(role="user", content="hi")], ["echo"])

    assert plugin.seen_tools is not None
    assert plugin.seen_tools[0].name == "echo"


def test_kernel_requires_tool_source() -> None:
    plugin = RecordingPlugin()
    with pytest.raises(KernelError):
        AgentKernel(
            config=KernelConfig(base_url="http://localhost:8000/v1", model="test"),
            plugin=plugin,
            tool_source=cast(RegistryBackendToolSource, None),
        )
