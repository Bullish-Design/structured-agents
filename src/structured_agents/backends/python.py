"""Simple Python function backend for testing and simple use cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from structured_agents.backends.protocol import Snapshot
from structured_agents.types import ToolCall, ToolResult, ToolSchema


class PythonBackend:
    """Backend that executes Python functions directly.

    This is useful for:
    - Testing without Grail dependencies
    - Simple tools that don't need sandboxing
    - Wrapping existing Python functions as tools
    """

    def __init__(
        self,
        handlers: dict[str, Callable[..., Awaitable[Any]]] | None = None,
    ) -> None:
        """Initialize with optional tool handlers.

        Args:
            handlers: Dict mapping tool names to async handler functions.
                      Handler signature: async def handler(**kwargs) -> Any
        """
        self._handlers = handlers or {}

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[Any]],
    ) -> None:
        """Register a tool handler.

        Args:
            name: Tool name.
            handler: Async function to handle the tool.
        """
        self._handlers[name] = handler

    async def execute(
        self,
        tool_call: ToolCall,
        tool_schema: ToolSchema,
        context: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool using the registered handler."""
        handler = self._handlers.get(tool_call.name)

        if not handler:
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                output=f"No handler registered for tool: {tool_call.name}",
                is_error=True,
            )

        try:
            kwargs = {**context, **tool_call.arguments}
            result = await handler(**kwargs)

            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                output=result,
                is_error=False,
            )
        except Exception as exc:
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                output=f"{type(exc).__name__}: {exc}",
                is_error=True,
            )

    async def run_context_providers(
        self,
        providers: list[Path],
        context: dict[str, Any],
    ) -> list[str]:
        """Python backend doesn't support context providers."""
        return []

    def supports_snapshots(self) -> bool:
        return False

    def create_snapshot(self) -> Snapshot | None:
        return None

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        pass
