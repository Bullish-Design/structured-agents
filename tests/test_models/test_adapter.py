# tests/test_models/test_adapter.py
import pytest
from dataclasses import dataclass
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import ResponseParser
from structured_agents.types import ToolSchema, ToolCall, ToolResult, TokenUsage
from structured_agents.grammar.config import DecodingConstraint


@dataclass
class MockParser:
    def parse(self, content, tool_calls):
        return content, []


def test_model_adapter_creation():
    adapter = ModelAdapter(
        name="test_model",
        grammar_builder=lambda tools, config: {"grammar": "test"},
        response_parser=MockParser(),
    )
    assert adapter.name == "test_model"
    assert adapter.grammar_builder is not None


def test_model_adapter_format_messages_default():
    adapter = ModelAdapter(
        name="test",
        grammar_builder=lambda t, c: None,
        response_parser=MockParser(),
    )
    from structured_agents.types import Message

    msg = Message(role="user", content="hello")
    result = adapter.format_messages([msg], [])
    assert result[0]["role"] == "user"
