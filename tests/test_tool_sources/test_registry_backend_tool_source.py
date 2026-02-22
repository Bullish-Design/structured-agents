"""Tests for RegistryBackendToolSource."""

from __future__ import annotations

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
from structured_agents.types import ToolCall


@pytest.mark.asyncio
async def test_registry_backend_tool_source_executes() -> None:
    registry = PythonRegistry()
    backend = PythonBackend(registry=registry)

    async def echo(text: str = "") -> str:
        return text

    backend.register("echo", echo)

    tool_source = RegistryBackendToolSource(registry, backend)
    tool_schema = registry.resolve("echo")

    assert tool_schema is not None

    result = await tool_source.execute(
        ToolCall.create(name="echo", arguments={"text": "ping"}),
        tool_schema,
        context={},
    )

    assert result.is_error is False
    assert result.output == "ping"


def test_registry_backend_tool_source_resolves() -> None:
    registry = PythonRegistry()
    backend = PythonBackend(registry=registry)

    async def echo(text: str = "") -> str:
        return text

    registry.register("echo", echo)

    tool_source = RegistryBackendToolSource(registry, backend)
    tools = tool_source.list_tools()

    assert tools == ["echo"]

    schema = tool_source.resolve("echo")
    assert schema is not None
    assert schema.name == "echo"
    assert schema.backend == "python"
    assert schema.parameters["type"] == "object"

    resolved = tool_source.resolve_all(["echo", "missing"])
    assert len(resolved) == 1
    assert resolved[0].name == "echo"
