"""Tool backend protocol definition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from structured_agents.types import ToolCall, ToolResult, ToolSchema


@dataclass
class Snapshot:
    """Snapshot of backend state for pause/resume functionality."""

    id: str
    backend_type: str
    state: dict[str, Any]


class ToolBackend(Protocol):
    """Protocol for tool execution backends.

    Backends handle the actual execution of tools. The default implementation
    uses Grail .pym scripts, but backends can use any execution strategy.
    """

    async def execute(
        self,
        tool_call: ToolCall,
        tool_schema: ToolSchema,
        context: dict[str, Any],
    ) -> ToolResult:
        """Execute a single tool call.

        Args:
            tool_call: The parsed tool call with name and arguments.
            tool_schema: Schema for the tool (may include script path).
            context: Additional context to merge with arguments.

        Returns:
            ToolResult with output or error.
        """
        ...

    async def run_context_providers(
        self,
        providers: list[Path],
        context: dict[str, Any],
    ) -> list[str]:
        """Execute context provider scripts before tool execution.

        Context providers inject domain-specific context (e.g., reading
        project config files) that gets prepended to tool results.

        Args:
            providers: Paths to context provider scripts.
            context: Base context for provider execution.

        Returns:
            List of serialized provider outputs.
        """
        ...

    def supports_snapshots(self) -> bool:
        """Check if this backend supports pause/resume via snapshots."""
        ...

    def create_snapshot(self) -> Snapshot | None:
        """Create a snapshot of current backend state.

        Returns:
            Snapshot object for pause/resume, or None if not supported.
        """
        ...

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        """Restore backend state from a snapshot."""
        ...
