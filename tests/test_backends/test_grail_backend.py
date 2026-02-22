"""Tests for Grail backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from structured_agents.backends.grail import GrailBackend, GrailBackendConfig
from structured_agents.types import ToolCall, ToolSchema

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "grail_tools"


class TestGrailBackend:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self) -> None:
        backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))

        tool_call = ToolCall(id="123", name="add_numbers", arguments={"x": 2, "y": 5})
        tool_schema = ToolSchema(
            name="add_numbers",
            description="Add two numbers",
            parameters={},
            script_path=FIXTURES_DIR / "add_numbers.pym",
        )

        try:
            result = await backend.execute(tool_call, tool_schema, {})
        finally:
            backend.shutdown()

        assert result.is_error is False
        assert result.output == '{"sum": 7}'

    @pytest.mark.asyncio
    async def test_context_provider_output_is_combined(self) -> None:
        backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))

        tool_call = ToolCall(id="123", name="add_numbers", arguments={"x": 1, "y": 1})
        tool_schema = ToolSchema(
            name="add_numbers",
            description="Add two numbers",
            parameters={},
            script_path=FIXTURES_DIR / "add_numbers.pym",
            context_providers=(FIXTURES_DIR / "context_info.pym",),
        )

        try:
            result = await backend.execute(
                tool_call, tool_schema, {"context_name": "demo"}
            )
        finally:
            backend.shutdown()

        assert result.is_error is False
        assert isinstance(result.output, str)
        parts = result.output.split("\n")
        assert json.loads(parts[0]) == {"context_name": "demo"}
        assert json.loads(parts[1]) == {"sum": 2}
