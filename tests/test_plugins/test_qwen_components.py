"""Unit tests for Qwen plugin components."""

from structured_agents.grammar.config import GrammarConfig
from structured_agents.plugins.qwen_components import (
    QwenGrammarProvider,
    QwenMessageFormatter,
    QwenResponseParser,
    QwenToolFormatter,
)
from structured_agents.types import Message, ToolSchema


def test_message_formatter_outputs_messages() -> None:
    formatter = QwenMessageFormatter()
    messages = [Message(role="user", content="Hello")]
    formatted = formatter.format_messages(messages, [])
    assert formatted == [{"role": "user", "content": "Hello"}]


def test_tool_formatter_outputs_tools() -> None:
    formatter = QwenToolFormatter()
    tool = ToolSchema(
        name="echo",
        description="Echo tool",
        parameters={"type": "object", "properties": {}},
    )
    formatted = formatter.format_tools([tool])
    assert formatted[0]["function"]["name"] == "echo"


def test_response_parser_handles_invalid_args() -> None:
    parser = QwenResponseParser()
    _, calls = parser.parse_response(
        None,
        [{"id": "call_1", "function": {"name": "echo", "arguments": "oops"}}],
    )
    assert calls[0].arguments == {}


def test_grammar_provider_supports_no_modes() -> None:
    provider = QwenGrammarProvider()
    assert provider.supports_mode("ebnf") is False
    assert provider.build_grammar([], GrammarConfig()) is None
    assert provider.to_extra_body(None) is None
