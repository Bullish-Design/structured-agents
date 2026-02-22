"""Tests for composite backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import pytest

from structured_agents.backends.composite import CompositeBackend
from structured_agents.types import ToolCall, ToolResult, ToolSchema


@dataclass
class FakeBackend:
    name: str

    async def execute(
        self,
        tool_call: ToolCall,
        tool_schema: ToolSchema,
        context: dict[str, Any],
    ) -> ToolResult:
        return ToolResult(
            call_id=tool_call.id,
            name=tool_call.name,
            output=json.dumps(context),
        )

    async def run_context_providers(
        self, providers: list[Path], context: dict[str, Any]
    ) -> list[str]:
        return ["context"]


@pytest.mark.asyncio
async def test_execute_routes_to_backend() -> None:
    backend = CompositeBackend()
    python_backend = FakeBackend(name="python")
    backend.register("python", python_backend)

    tool_call = ToolCall(id="call_1", name="echo", arguments={})
    tool_schema = ToolSchema(
        name="echo", description="", parameters={}, backend="python"
    )

    result = await backend.execute(tool_call, tool_schema, {"key": "value"})
    assert result.is_error is False
    assert result.output == '{"key": "value"}'


@pytest.mark.asyncio
async def test_execute_missing_backend() -> None:
    backend = CompositeBackend()
    tool_call = ToolCall(id="call_2", name="echo", arguments={})
    tool_schema = ToolSchema(
        name="echo", description="", parameters={}, backend="missing"
    )

    result = await backend.execute(tool_call, tool_schema, {})
    assert result.is_error is True
    assert "No backend registered" in str(result.output)


@pytest.mark.asyncio
async def test_run_context_providers_uses_grail() -> None:
    backend = CompositeBackend()
    grail_backend = FakeBackend(name="grail")
    backend.register("grail", grail_backend)

    outputs = await backend.run_context_providers([], {})
    assert outputs == ["context"]
