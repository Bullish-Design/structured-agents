"""Tests for AgentKernel."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.client.protocol import CompletionResponse
from structured_agents.kernel import AgentKernel
from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
from structured_agents.types import (
    KernelConfig,
    Message,
    TokenUsage,
    ToolResult,
    ToolSchema,
)


class TestAgentKernel:
    @pytest.fixture
    def config(self) -> KernelConfig:
        return KernelConfig(
            base_url="http://localhost:8000/v1",
            model="test-model",
        )

    @pytest.fixture
    def plugin(self) -> FunctionGemmaPlugin:
        return FunctionGemmaPlugin()

    @pytest.fixture
    def tool_source(self) -> RegistryBackendToolSource:
        registry = PythonRegistry()
        backend = PythonBackend(registry=registry)

        async def echo_handler(message: str = "") -> str:
            return f"Echo: {message}"

        async def submit_handler(summary: str = "") -> dict[str, str]:
            return {"status": "success", "summary": summary}

        backend.register("echo", echo_handler)
        backend.register("submit_result", submit_handler)
        return RegistryBackendToolSource(registry, backend)

    @pytest.fixture
    def tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="echo",
                description="Echo a message",
                parameters={
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                },
            ),
            ToolSchema(
                name="submit_result",
                description="Submit final result",
                parameters={
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_step_no_tool_calls(
        self,
        config: KernelConfig,
        plugin: FunctionGemmaPlugin,
        tool_source: RegistryBackendToolSource,
        tools: list[ToolSchema],
    ) -> None:
        kernel = AgentKernel(config=config, plugin=plugin, tool_source=tool_source)

        mock_response = CompletionResponse(
            content="Hello, world!",
            tool_calls=None,
            usage=TokenUsage(10, 5, 15),
            finish_reason="stop",
            raw_response={},
        )
        kernel._client.chat_completion = AsyncMock(return_value=mock_response)

        messages = [Message(role="user", content="Hi")]
        result = await kernel.step(messages, tools)

        assert result.response_message.content == "Hello, world!"
        assert len(result.tool_calls) == 0
        assert len(result.tool_results) == 0

    @pytest.mark.asyncio
    async def test_step_with_tool_calls(
        self,
        config: KernelConfig,
        plugin: FunctionGemmaPlugin,
        tool_source: RegistryBackendToolSource,
        tools: list[ToolSchema],
    ) -> None:
        kernel = AgentKernel(config=config, plugin=plugin, tool_source=tool_source)

        mock_response = CompletionResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_123",
                    "function": {
                        "name": "echo",
                        "arguments": '{"message": "test"}',
                    },
                }
            ],
            usage=TokenUsage(10, 5, 15),
            finish_reason="tool_calls",
            raw_response={},
        )
        kernel._client.chat_completion = AsyncMock(return_value=mock_response)

        messages = [Message(role="user", content="Echo test")]
        result = await kernel.step(messages, tools)

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "echo"
        assert len(result.tool_results) == 1
        assert "Echo: test" in str(result.tool_results[0].output)

    @pytest.mark.asyncio
    async def test_run_terminates_on_no_tool_calls(
        self,
        config: KernelConfig,
        plugin: FunctionGemmaPlugin,
        tool_source: RegistryBackendToolSource,
        tools: list[ToolSchema],
    ) -> None:
        kernel = AgentKernel(config=config, plugin=plugin, tool_source=tool_source)

        mock_response = CompletionResponse(
            content="Done!",
            tool_calls=None,
            usage=TokenUsage(10, 5, 15),
            finish_reason="stop",
            raw_response={},
        )
        kernel._client.chat_completion = AsyncMock(return_value=mock_response)

        messages = [Message(role="user", content="Hi")]
        result = await kernel.run(messages, tools, max_turns=5)

        assert result.turn_count == 1
        assert result.termination_reason == "no_tool_calls"

    @pytest.mark.asyncio
    async def test_run_terminates_on_termination_tool(
        self,
        config: KernelConfig,
        plugin: FunctionGemmaPlugin,
        tool_source: RegistryBackendToolSource,
        tools: list[ToolSchema],
    ) -> None:
        kernel = AgentKernel(config=config, plugin=plugin, tool_source=tool_source)

        call_count = 0

        async def mock_completion(*_: object, **__: object) -> CompletionResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return CompletionResponse(
                    content=None,
                    tool_calls=[
                        {
                            "id": "call_1",
                            "function": {
                                "name": "echo",
                                "arguments": '{"message": "test"}',
                            },
                        }
                    ],
                    usage=TokenUsage(10, 5, 15),
                    finish_reason="tool_calls",
                    raw_response={},
                )
            return CompletionResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_2",
                        "function": {
                            "name": "submit_result",
                            "arguments": '{"summary": "done"}',
                        },
                    }
                ],
                usage=TokenUsage(10, 5, 15),
                finish_reason="tool_calls",
                raw_response={},
            )

        kernel._client.chat_completion = mock_completion

        def is_submit(result: ToolResult) -> bool:
            return result.name == "submit_result"

        messages = [Message(role="user", content="Work")]
        result = await kernel.run(messages, tools, max_turns=10, termination=is_submit)

        assert result.turn_count == 2
        assert result.termination_reason == "termination_tool"
        assert result.final_tool_result is not None
        assert result.final_tool_result.name == "submit_result"

    @pytest.mark.asyncio
    async def test_run_respects_max_turns(
        self,
        config: KernelConfig,
        plugin: FunctionGemmaPlugin,
        tool_source: RegistryBackendToolSource,
        tools: list[ToolSchema],
    ) -> None:
        kernel = AgentKernel(config=config, plugin=plugin, tool_source=tool_source)

        mock_response = CompletionResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {
                        "name": "echo",
                        "arguments": '{"message": "loop"}',
                    },
                }
            ],
            usage=TokenUsage(10, 5, 15),
            finish_reason="tool_calls",
            raw_response={},
        )
        kernel._client.chat_completion = AsyncMock(return_value=mock_response)

        messages = [Message(role="user", content="Loop forever")]
        result = await kernel.run(messages, tools, max_turns=3)

        assert result.turn_count == 3
        assert result.termination_reason == "max_turns"
