"""Grail tool implementation."""

from __future__ import annotations
import json
from typing import Any
from structured_agents.types import ToolSchema, ToolResult


class GrailTool:
    """A tool backed by a .pym script."""

    def __init__(self, script: Any, limits: Any = None):
        self._script = script
        self._limits = limits
        self._schema = ToolSchema(
            name=script.name,
            description=f"Tool: {script.name}",
            parameters={"type": "object", "properties": {}},
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult:
        try:
            result = await self._script.run(inputs=arguments, limits=self._limits)
            output = json.dumps(result) if not isinstance(result, str) else result
            return ToolResult(
                call_id=context.call_id if context else "unknown",
                name=self._script.name,
                output=output,
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                call_id=context.call_id if context else "unknown",
                name=self._script.name,
                output=str(e),
                is_error=True,
            )


def discover_tools(agents_dir: str):
    """Discover .pym tools in a directory."""
    # TODO: implement with grail.load()
    return []
