"""Tests for AgentKernel."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.client.protocol import CompletionResponse
from structured_agents.kernel import AgentKernel
from structured_agents.observer import ToolCallEvent, ToolResultEvent
from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import ContextProvider, RegistryBackendToolSource
from structured_agents.types import (
    KernelConfig,
    Message,
    TokenUsage,
    ToolCall,
    ToolExecutionStrategy,
    ToolResult,
    ToolSchema,
)


class RecordingObserver:
    def __init__(self) -> None:
        self.tool_calls: list[ToolCallEvent] = []
        self.tool_results: list[ToolResultEvent] = []

    async def on_kernel_start(self, *_: object, **__: object) -> None:
        return None

    async def on_model_request(self, *_: object, **__: object) -> None:
        return None

    async def on_model_response(self, *_: object, **__: object) -> None:
        return None

    async def on_tool_call(self, event: ToolCallEvent) -> None:
        self.tool_calls.append(event)

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        self.tool_results.append(event)

    async def on_turn_complete(self, *_: object, **__: object) -> None:
        return None

    async def on_kernel_end(self, *_: object, **__: object) -> None:
        return None

    async def on_error(self, *_: object, **__: object) -> None:
        return None


class TrackingToolSource:
    def __init__(self, tools: list[ToolSchema], delays: dict[str, float]) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._delays = delays
        self._lock = asyncio.Lock()
        self._in_flight = 0
        self.max_in_flight = 0

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def resolve(self, tool_name: str) -> ToolSchema | None:
        return self._tools.get(tool_name)

    def resolve_all(self, tool_names: list[str]) -> list[ToolSchema]:
        return [self._tools[name] for name in tool_names if name in self._tools]

    async def execute(
        self, tool_call: ToolCall, tool_schema: ToolSchema, context: dict[str, Any]
    ) -> ToolResult:
        async with self._lock:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)

        await asyncio.sleep(self._delays.get(tool_call.name, 0.0))

        async with self._lock:
            self._in_flight -= 1

        return ToolResult(
            call_id=tool_call.id,
            name=tool_call.name,
            output=f"{tool_call.name} done",
        )

    def context_providers(self) -> list[ContextProvider]:
        return []


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
    async def test_concurrent_tool_execution_orders_events_and_limits(
        self, plugin: FunctionGemmaPlugin
    ) -> None:
        tool_schemas = [
            ToolSchema(
                name="first",
                description="First tool",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSchema(
                name="second",
                description="Second tool",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSchema(
                name="third",
                description="Third tool",
                parameters={"type": "object", "properties": {}},
            ),
        ]
        tool_source = TrackingToolSource(
            tool_schemas, delays={"first": 0.05, "second": 0.0, "third": 0.01}
        )
        observer = RecordingObserver()
        config = KernelConfig(
            base_url="http://localhost:8000/v1",
            model="test-model",
            tool_execution_strategy=ToolExecutionStrategy(
                mode="concurrent", max_concurrency=2
            ),
        )
        kernel = AgentKernel(
            config=config,
            plugin=plugin,
            tool_source=tool_source,
            observer=observer,
        )

        mock_response = CompletionResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {"name": "first", "arguments": "{}"},
                },
                {
                    "id": "call_2",
                    "function": {"name": "second", "arguments": "{}"},
                },
                {
                    "id": "call_3",
                    "function": {"name": "third", "arguments": "{}"},
                },
            ],
            usage=TokenUsage(10, 5, 15),
            finish_reason="tool_calls",
            raw_response={},
        )
        kernel._client.chat_completion = AsyncMock(return_value=mock_response)

        messages = [Message(role="user", content="Run tools")]
        result = await kernel.step(messages, tool_schemas)

        assert tool_source.max_in_flight == 2
        assert [event.tool_name for event in observer.tool_calls] == [
            "first",
            "second",
            "third",
        ]
        assert [event.tool_name for event in observer.tool_results] == [
            "first",
            "second",
            "third",
        ]
        assert [result.name for result in result.tool_results] == [
            "first",
            "second",
            "third",
        ]

    @pytest.mark.asyncio
    async def test_sequential_tool_execution_respects_strategy(
        self, plugin: FunctionGemmaPlugin
    ) -> None:
        tool_schemas = [
            ToolSchema(
                name="alpha",
                description="Alpha tool",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSchema(
                name="beta",
                description="Beta tool",
                parameters={"type": "object", "properties": {}},
            ),
        ]
        tool_source = TrackingToolSource(
            tool_schemas, delays={"alpha": 0.01, "beta": 0.0}
        )
        observer = RecordingObserver()
        config = KernelConfig(
            base_url="http://localhost:8000/v1",
            model="test-model",
            tool_execution_strategy=ToolExecutionStrategy(
                mode="sequential", max_concurrency=10
            ),
        )
        kernel = AgentKernel(
            config=config,
            plugin=plugin,
            tool_source=tool_source,
            observer=observer,
        )

        mock_response = CompletionResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {"name": "alpha", "arguments": "{}"},
                },
                {
                    "id": "call_2",
                    "function": {"name": "beta", "arguments": "{}"},
                },
            ],
            usage=TokenUsage(10, 5, 15),
            finish_reason="tool_calls",
            raw_response={},
        )
        kernel._client.chat_completion = AsyncMock(return_value=mock_response)

        messages = [Message(role="user", content="Run tools")]
        result = await kernel.step(messages, tool_schemas)

        assert tool_source.max_in_flight == 1
        assert [event.tool_name for event in observer.tool_results] == [
            "alpha",
            "beta",
        ]
        assert [result.name for result in result.tool_results] == [
            "alpha",
            "beta",
        ]

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
    async def test_run_passes_model_override_from_context(
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
        mock_client = AsyncMock(return_value=mock_response)
        kernel._client.chat_completion = mock_client

        async def provide_context() -> dict[str, Any]:
            return {"model_override": "adapter-model"}

        messages = [Message(role="user", content="Hi")]
        await kernel.run(messages, tools, max_turns=1, context_provider=provide_context)

        assert mock_client.await_args is not None
        assert mock_client.await_args.kwargs["model"] == "adapter-model"

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
