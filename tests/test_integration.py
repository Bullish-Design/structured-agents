"""Integration tests for the complete system."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from structured_agents import (
    AgentKernel,
    FunctionGemmaPlugin,
    KernelConfig,
    Message,
    PythonBackend,
    ToolResult,
    ToolSchema,
)
from structured_agents.client.protocol import CompletionResponse
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
from structured_agents.types import TokenUsage


class RecordingObserver:
    """Observer that records events for testing."""

    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    async def on_kernel_start(self, event: object) -> None:
        self.events.append(("kernel_start", event))

    async def on_model_request(self, event: object) -> None:
        self.events.append(("model_request", event))

    async def on_model_response(self, event: object) -> None:
        self.events.append(("model_response", event))

    async def on_tool_call(self, event: object) -> None:
        self.events.append(("tool_call", event))

    async def on_tool_result(self, event: object) -> None:
        self.events.append(("tool_result", event))

    async def on_turn_complete(self, event: object) -> None:
        self.events.append(("turn_complete", event))

    async def on_kernel_end(self, event: object) -> None:
        self.events.append(("kernel_end", event))

    async def on_error(self, error: Exception, context: str | None = None) -> None:
        self.events.append(("error", error, context))


class TestFullAgentLoop:
    """Test complete agent workflows."""

    @pytest.fixture
    def tool_source(self) -> RegistryBackendToolSource:
        registry = PythonRegistry()
        backend = PythonBackend(registry=registry)

        async def analyze_code(code: str = "") -> dict[str, object]:
            return {
                "lines": len(code.split("\n")),
                "has_docstring": '"""' in code or "'''" in code,
            }

        async def write_docstring(
            docstring: str = "",
            function_name: str = "",
        ) -> dict[str, object]:
            return {
                "success": True,
                "function": function_name,
                "docstring": docstring,
            }

        async def submit_result(
            summary: str = "",
            status: str = "success",
        ) -> dict[str, str]:
            return {
                "status": status,
                "summary": summary,
            }

        backend.register("analyze_code", analyze_code)
        backend.register("write_docstring", write_docstring)
        backend.register("submit_result", submit_result)
        return RegistryBackendToolSource(registry, backend)

    @pytest.fixture
    def tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="analyze_code",
                description="Analyze Python code",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                    },
                },
            ),
            ToolSchema(
                name="write_docstring",
                description="Write a docstring",
                parameters={
                    "type": "object",
                    "properties": {
                        "docstring": {"type": "string"},
                        "function_name": {"type": "string"},
                    },
                },
            ),
            ToolSchema(
                name="submit_result",
                description="Submit final result",
                parameters={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_multi_turn_agent_loop(
        self,
        tool_source: RegistryBackendToolSource,
        tools: list[ToolSchema],
    ) -> None:
        config = KernelConfig(base_url="http://localhost:8000/v1", model="test")
        plugin = FunctionGemmaPlugin()
        observer = RecordingObserver()

        kernel = AgentKernel(
            config=config,
            plugin=plugin,
            tool_source=tool_source,
            observer=observer,
        )

        turn = 0

        async def mock_completion(*_: object, **__: object) -> CompletionResponse:
            nonlocal turn
            turn += 1

            if turn == 1:
                return CompletionResponse(
                    content=None,
                    tool_calls=[
                        {
                            "id": "call_1",
                            "function": {
                                "name": "analyze_code",
                                "arguments": '{"code": "def foo():\\n    pass"}',
                            },
                        }
                    ],
                    usage=TokenUsage(50, 20, 70),
                    finish_reason="tool_calls",
                    raw_response={},
                )
            if turn == 2:
                return CompletionResponse(
                    content=None,
                    tool_calls=[
                        {
                            "id": "call_2",
                            "function": {
                                "name": "write_docstring",
                                "arguments": '{"docstring": "A foo function.", "function_name": "foo"}',
                            },
                        }
                    ],
                    usage=TokenUsage(80, 30, 110),
                    finish_reason="tool_calls",
                    raw_response={},
                )
            return CompletionResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_3",
                        "function": {
                            "name": "submit_result",
                            "arguments": '{"summary": "Added docstring to foo", "status": "success"}',
                        },
                    }
                ],
                usage=TokenUsage(100, 25, 125),
                finish_reason="tool_calls",
                raw_response={},
            )

        kernel._client.chat_completion = AsyncMock(side_effect=mock_completion)

        def is_submit(result: ToolResult) -> bool:
            return result.name == "submit_result"

        messages = [
            Message(role="system", content="You are a docstring writer."),
            Message(role="user", content="Add a docstring to: def foo(): pass"),
        ]

        result = await kernel.run(
            initial_messages=messages,
            tools=tools,
            max_turns=10,
            termination=is_submit,
        )

        assert result.turn_count == 3
        assert result.termination_reason == "termination_tool"
        assert result.final_tool_result is not None
        assert result.final_tool_result.name == "submit_result"

        assert len(result.history) > 2

        event_types = [event[0] for event in observer.events]
        assert "kernel_start" in event_types
        assert "kernel_end" in event_types
        assert event_types.count("model_request") == 3
        assert event_types.count("tool_result") == 3

        assert result.total_usage is not None
        assert result.total_usage.total_tokens == 70 + 110 + 125
