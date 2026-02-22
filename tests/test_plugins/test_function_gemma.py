"""Tests for FunctionGemma plugin."""

from structured_agents.grammar.artifacts import EBNFGrammar
from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.types import Message


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
        result = plugin.to_extra_body(EBNFGrammar(grammar="some grammar"))
        assert result == {
            "structured_outputs": {"type": "grammar", "grammar": "some grammar"}
        }

    def test_extra_body_without_grammar(self) -> None:
        plugin = FunctionGemmaPlugin()
        result = plugin.to_extra_body(None)
        assert result is None
