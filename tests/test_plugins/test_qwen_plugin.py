"""Tests for Qwen plugin."""

from structured_agents.plugins.qwen import QwenPlugin


def test_parse_response_with_tool_calls() -> None:
    plugin = QwenPlugin()
    tool_calls_raw = [
        {
            "id": "call_1",
            "function": {"name": "echo", "arguments": '{"text": "hi"}'},
        }
    ]

    content, tool_calls = plugin.parse_response("hello", tool_calls_raw)
    assert content == "hello"
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "echo"
    assert tool_calls[0].arguments == {"text": "hi"}


def test_parse_response_with_invalid_arguments() -> None:
    plugin = QwenPlugin()
    tool_calls_raw = [
        {
            "id": "call_2",
            "function": {"name": "echo", "arguments": "not-json"},
        }
    ]

    _, tool_calls = plugin.parse_response(None, tool_calls_raw)
    assert len(tool_calls) == 1
    assert tool_calls[0].arguments == {}


def test_to_extra_body_none() -> None:
    plugin = QwenPlugin()
    assert plugin.to_extra_body(None) is None
