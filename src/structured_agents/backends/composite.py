from __future__ import annotations

from typing import Any

from structured_agents.backends.protocol import Snapshot, ToolBackend
from structured_agents.types import ToolCall, ToolResult, ToolSchema


class CompositeBackend:
    """Backend that routes execution to appropriate sub-backends."""

    def __init__(self) -> None:
        self._backends: dict[str, ToolBackend] = {}

    def register(self, backend_name: str, backend: ToolBackend) -> None:
        """Register a backend for a given type."""
        self._backends[backend_name] = backend

    async def execute(
        self,
        tool_call: ToolCall,
        tool_schema: ToolSchema,
        context: dict[str, Any],
    ) -> ToolResult:
        """Execute tool using appropriate backend."""
        backend = self._backends.get(tool_schema.backend)

        if not backend:
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                output=f"No backend registered for: {tool_schema.backend}",
                is_error=True,
            )

        return await backend.execute(tool_call, tool_schema, context)

    async def run_context_providers(
        self,
        providers: list[Any],
        context: dict[str, Any],
    ) -> list[str]:
        """Run context providers using Grail backend."""
        grail_backend = self._backends.get("grail")
        if grail_backend:
            return await grail_backend.run_context_providers(providers, context)
        return []

    def supports_snapshots(self) -> bool:
        return all(backend.supports_snapshots() for backend in self._backends.values())

    def create_snapshot(self) -> Snapshot | None:
        if not self.supports_snapshots():
            return None

        snapshots = {
            name: backend.create_snapshot() for name, backend in self._backends.items()
        }
        return Snapshot(id="composite", backend_type="composite", state=snapshots)

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        if snapshot.backend_type != "composite":
            return

        state = snapshot.state
        if not isinstance(state, dict):
            return

        for name, sub_snapshot in state.items():
            if name in self._backends and isinstance(sub_snapshot, Snapshot):
                self._backends[name].restore_snapshot(sub_snapshot)
