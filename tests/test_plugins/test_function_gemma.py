"""Tests for FunctionGemma plugin."""

from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.plugins.grammar.function_gemma import build_functiongemma_grammar
from structured_agents.types import Message, ToolSchema


class TestFunctionGemmaGrammar:
    def test_empty_tools_returns_empty(self) -> None:
        grammar = build_functiongemma_grammar([])
        assert grammar == ""

    def test_single_tool(self) -> None:
        tools = [
            ToolSchema(name="read_file", description="Read a file", parameters={}),
        ]
        grammar = build_functiongemma_grammar(tools)
        assert "read_file" in grammar
        assert "<start_function_call>" in grammar
        assert "<end_function_call>" in grammar

    def test_multiple_tools(self) -> None:
        tools = [
            ToolSchema(name="read_file", description="Read", parameters={}),
            ToolSchema(name="write_file", description="Write", parameters={}),
        ]
        grammar = build_functiongemma_grammar(tools)
        assert "read_file" in grammar
        assert "write_file" in grammar


class TestFunctionGemmaPlugin:
    def test_name(self) -> None:
        plugin = FunctionGemmaPlugin()
        assert plugin.name == "function_gemma"

    def test_format_messages(self) -> None:
        plugin = FunctionGemmaPlugin()
        messages = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
        ]
        formatted = plugin.format_messages(messages, [])
        assert len(formatted) == 2
        assert formatted[0]["role"] == "system"
        assert formatted[1]["content"] == "Hello"

    def test_parse_standard_tool_calls(self) -> None:
        plugin = FunctionGemmaPlugin()
        tool_calls_raw = [
            {
                "id": "call_123",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "/test.txt"}',
                },
            }
        ]
        content, calls = plugin.parse_response(None, tool_calls_raw)
        assert content is None
        assert len(calls) == 1
        assert calls[0].name == "read_file"
        assert calls[0].arguments == {"path": "/test.txt"}

    def test_parse_grammar_format(self) -> None:
        plugin = FunctionGemmaPlugin()
        content = (
            "<start_function_call>call:read_file{path:/test.txt}<end_function_call>"
        )
        result_content, calls = plugin.parse_response(content, None)
        assert result_content is None
        assert len(calls) == 1
        assert calls[0].name == "read_file"

    def test_extra_body_with_grammar(self) -> None:
        plugin = FunctionGemmaPlugin()
        result = plugin.extra_body("some grammar")
        assert result == {"guided_grammar": "some grammar"}

    def test_extra_body_without_grammar(self) -> None:
        plugin = FunctionGemmaPlugin()
        result = plugin.extra_body(None)
        assert result is None
