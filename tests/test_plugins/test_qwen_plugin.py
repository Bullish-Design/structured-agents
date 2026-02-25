"""Tests for Qwen plugin."""

from structured_agents.grammar.config import GrammarConfig
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


def test_parse_response_raw_content_with_qwen_format() -> None:
    plugin = QwenPlugin()
    content = "Hello <function=get_weather><parameter=city>London</parameter></function> world"
    tool_calls_raw = None

    parsed_content, tool_calls = plugin.parse_response(content, tool_calls_raw)
    assert parsed_content is None
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "get_weather"
    assert tool_calls[0].arguments == {"city": "London"}


def test_parse_response_raw_content_with_json_args() -> None:
    plugin = QwenPlugin()
    content = (
        '<function=search><parameter=query>{"query": "python"}</parameter></function>'
    )
    tool_calls_raw = None

    parsed_content, tool_calls = plugin.parse_response(content, tool_calls_raw)
    assert parsed_content is None
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "search"
    assert tool_calls[0].arguments == {"query": {"query": "python"}}


def test_default_grammar_config() -> None:
    plugin = QwenPlugin()
    config = plugin.default_grammar_config
    assert config.mode == "structural_tag"
    assert config.allow_parallel_calls is True
    assert config.args_format == "permissive"


def test_to_extra_body_none() -> None:
    plugin = QwenPlugin()
    assert plugin.to_extra_body(None) is None
