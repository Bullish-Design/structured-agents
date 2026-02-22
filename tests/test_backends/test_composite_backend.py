"""Tests for composite backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from structured_agents.backends.composite import CompositeBackend
from structured_agents.backends.protocol import Snapshot
from structured_agents.types import ToolCall, ToolResult, ToolSchema


@dataclass
class FakeBackend:
    name: str
    supports_snapshots_flag: bool = False
    snapshot_state: dict[str, Any] | None = None
    restored: list[Snapshot] | None = None

    async def execute(
        self,
        tool_call: ToolCall,
        tool_schema: ToolSchema,
        context: dict[str, Any],
    ) -> ToolResult:
        return ToolResult(call_id=tool_call.id, name=tool_call.name, output=context)

    async def run_context_providers(
        self, providers: list[Any], context: dict[str, Any]
    ) -> list[str]:
        return ["context"]

    def supports_snapshots(self) -> bool:
        return self.supports_snapshots_flag

    def create_snapshot(self) -> Snapshot | None:
        if not self.supports_snapshots_flag:
            return None
        return Snapshot(
            id=self.name, backend_type=self.name, state=self.snapshot_state or {}
        )

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        if self.restored is None:
            self.restored = []
        self.restored.append(snapshot)


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
    assert result.output == {"key": "value"}


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


def test_snapshot_supports_all_backends() -> None:
    backend = CompositeBackend()
    backend.register("python", FakeBackend(name="python", supports_snapshots_flag=True))
    backend.register("grail", FakeBackend(name="grail", supports_snapshots_flag=True))

    assert backend.supports_snapshots() is True
    snapshot = backend.create_snapshot()
    assert snapshot is not None
    assert snapshot.backend_type == "composite"
    assert set(snapshot.state.keys()) == {"python", "grail"}


def test_snapshot_returns_none_when_unsupported() -> None:
    backend = CompositeBackend()
    backend.register("python", FakeBackend(name="python", supports_snapshots_flag=True))
    backend.register("grail", FakeBackend(name="grail", supports_snapshots_flag=False))

    assert backend.supports_snapshots() is False
    assert backend.create_snapshot() is None


def test_restore_snapshot_dispatches() -> None:
    backend = CompositeBackend()
    python_backend = FakeBackend(name="python", supports_snapshots_flag=True)
    grail_backend = FakeBackend(name="grail", supports_snapshots_flag=True)
    backend.register("python", python_backend)
    backend.register("grail", grail_backend)

    snapshot = Snapshot(
        id="composite",
        backend_type="composite",
        state={
            "python": Snapshot(id="py", backend_type="python", state={"a": 1}),
            "grail": Snapshot(id="gr", backend_type="grail", state={"b": 2}),
        },
    )

    backend.restore_snapshot(snapshot)

    assert python_backend.restored is not None
    assert grail_backend.restored is not None
    assert python_backend.restored[0].backend_type == "python"
    assert grail_backend.restored[0].backend_type == "grail"
