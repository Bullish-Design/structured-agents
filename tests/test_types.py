"""Tests for core types."""

import json

import pytest

from structured_agents.types import (
    KernelConfig,
    Message,
    ToolCall,
    ToolResult,
    ToolSchema,
)


class TestKernelConfig:
    def test_defaults(self) -> None:
        config = KernelConfig(base_url="http://localhost:8000/v1", model="test")
        assert config.api_key == "EMPTY"
        assert config.timeout == 120.0
        assert config.temperature == 0.1
        assert config.tool_choice == "auto"

    def test_custom_values(self) -> None:
        config = KernelConfig(
            base_url="http://example.com",
            model="custom-model",
            temperature=0.7,
            max_tokens=2048,
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 2048


class TestMessage:
    def test_simple_message(self) -> None:
        msg = Message(role="user", content="Hello")
        assert msg.to_openai_format() == {"role": "user", "content": "Hello"}

    def test_assistant_with_tool_calls(self) -> None:
        tc = ToolCall(id="call_123", name="read_file", arguments={"path": "/foo"})
        msg = Message(role="assistant", content=None, tool_calls=[tc])
        fmt = msg.to_openai_format()
        assert fmt["role"] == "assistant"
        assert len(fmt["tool_calls"]) == 1
        assert fmt["tool_calls"][0]["function"]["name"] == "read_file"

    def test_tool_response(self) -> None:
        msg = Message(
            role="tool",
            content="file contents",
            tool_call_id="call_123",
            name="read_file",
        )
        fmt = msg.to_openai_format()
        assert fmt["role"] == "tool"
        assert fmt["tool_call_id"] == "call_123"
        assert fmt["name"] == "read_file"


class TestToolCall:
    def test_create_auto_id(self) -> None:
        tc = ToolCall.create(name="test", arguments={"x": 1})
        assert tc.name == "test"
        assert tc.arguments == {"x": 1}
        assert tc.id.startswith("call_")
        assert len(tc.id) == 13

    def test_arguments_json(self) -> None:
        tc = ToolCall(id="123", name="test", arguments={"nested": {"a": 1}})
        parsed = json.loads(tc.arguments_json)
        assert parsed == {"nested": {"a": 1}}


class TestToolResult:
    def test_string_output(self) -> None:
        result = ToolResult(call_id="123", name="test", output="hello")
        assert result.output_str == "hello"

    def test_dict_output(self) -> None:
        result = ToolResult(call_id="123", name="test", output={"key": "value"})
        assert result.output_str == '{"key": "value"}'

    def test_to_message(self) -> None:
        result = ToolResult(call_id="123", name="test", output="output")
        msg = result.to_message()
        assert msg.role == "tool"
        assert msg.content == "output"
        assert msg.tool_call_id == "123"
        assert msg.name == "test"

    def test_error_result(self) -> None:
        result = ToolResult(
            call_id="123", name="test", output="error msg", is_error=True
        )
        assert result.is_error is True


class TestToolSchema:
    def test_to_openai_format(self) -> None:
        schema = ToolSchema(
            name="read_file",
            description="Read a file",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        fmt = schema.to_openai_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "read_file"
        assert "path" in fmt["function"]["parameters"]["properties"]
