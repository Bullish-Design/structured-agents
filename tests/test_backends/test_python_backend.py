"""Tests for Python backend."""

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.types import ToolCall, ToolSchema


class TestPythonBackend:
    @pytest.mark.asyncio
    async def test_execute_registered_handler(self) -> None:
        backend = PythonBackend()

        async def my_handler(x: int, y: int) -> int:
            return x + y

        backend.register("add", my_handler)

        tool_call = ToolCall(id="123", name="add", arguments={"x": 2, "y": 3})
        tool_schema = ToolSchema(name="add", description="Add numbers", parameters={})

        result = await backend.execute(tool_call, tool_schema, {})

        assert result.is_error is False
        assert result.output == "5"

    @pytest.mark.asyncio
    async def test_execute_unregistered_handler(self) -> None:
        backend = PythonBackend()

        tool_call = ToolCall(id="123", name="unknown", arguments={})
        tool_schema = ToolSchema(name="unknown", description="Unknown", parameters={})

        result = await backend.execute(tool_call, tool_schema, {})

        assert result.is_error is True
        assert "No handler registered" in result.output

    @pytest.mark.asyncio
    async def test_execute_handler_exception(self) -> None:
        backend = PythonBackend()

        async def failing_handler() -> None:
            raise ValueError("Intentional error")

        backend.register("fail", failing_handler)

        tool_call = ToolCall(id="123", name="fail", arguments={})
        tool_schema = ToolSchema(name="fail", description="Fail", parameters={})

        result = await backend.execute(tool_call, tool_schema, {})

        assert result.is_error is True
        assert "ValueError" in result.output

    @pytest.mark.asyncio
    async def test_context_merged_with_arguments(self) -> None:
        backend = PythonBackend()
        received_kwargs: dict[str, str] = {}

        async def capture_handler(**kwargs: str) -> str:
            received_kwargs.update(kwargs)
            return "ok"

        backend.register("capture", capture_handler)

        tool_call = ToolCall(id="123", name="capture", arguments={"arg1": "value1"})
        tool_schema = ToolSchema(name="capture", description="Capture", parameters={})
        context = {"ctx1": "ctx_value"}

        await backend.execute(tool_call, tool_schema, context)

        assert received_kwargs["arg1"] == "value1"
        assert received_kwargs["ctx1"] == "ctx_value"
