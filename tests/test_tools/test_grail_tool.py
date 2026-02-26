# tests/test_tools/test_grail_tool.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from structured_agents.tools.protocol import Tool
from structured_agents.tools.grail import GrailTool


@pytest.mark.asyncio
async def test_grail_tool_execute():
    mock_script = MagicMock()
    mock_script.name = "test_tool"
    mock_script.run = AsyncMock(return_value={"result": 42})

    tool = GrailTool(script=mock_script, limits=None)

    assert tool.schema.name == "test_tool"

    class MockContext:
        call_id = "call_123"

    result = await tool.execute({"a": 1}, MockContext())
    assert result.is_error == False
    assert "42" in result.output
