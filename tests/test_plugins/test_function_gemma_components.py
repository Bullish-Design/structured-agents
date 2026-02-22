"""Unit tests for FunctionGemma plugin components."""

from structured_agents.grammar.artifacts import EBNFGrammar
from structured_agents.grammar.config import GrammarConfig
from structured_agents.plugins.function_gemma_components import (
    FunctionGemmaGrammarProvider,
    FunctionGemmaMessageFormatter,
    FunctionGemmaResponseParser,
    FunctionGemmaToolFormatter,
)
from structured_agents.types import Message, ToolSchema


def test_message_formatter_outputs_messages() -> None:
    formatter = FunctionGemmaMessageFormatter()
    messages = [Message(role="user", content="Hello")]
    formatted = formatter.format_messages(messages, [])
    assert formatted == [{"role": "user", "content": "Hello"}]


def test_tool_formatter_outputs_tools() -> None:
    formatter = FunctionGemmaToolFormatter()
    tool = ToolSchema(
        name="echo",
        description="Echo tool",
        parameters={"type": "object", "properties": {}},
    )
    formatted = formatter.format_tools([tool])
    assert formatted[0]["function"]["name"] == "echo"


def test_response_parser_reads_raw_tool_calls() -> None:
    parser = FunctionGemmaResponseParser()
    content, calls = parser.parse_response(
        "hi",
        [
            {
                "id": "call_1",
                "function": {"name": "echo", "arguments": '{"text": "hi"}'},
            }
        ],
    )
    assert content == "hi"
    assert len(calls) == 1
    assert calls[0].arguments == {"text": "hi"}


def test_grammar_provider_supports_modes_and_payload() -> None:
    provider = FunctionGemmaGrammarProvider()
    tool = ToolSchema(
        name="echo",
        description="Echo tool",
        parameters={"type": "object", "properties": {}},
    )
    assert provider.supports_mode("ebnf") is True
    assert provider.supports_mode("structural_tag") is True
    assert provider.supports_mode("json_schema") is True

    grammar = provider.build_grammar([tool], GrammarConfig(mode="json_schema"))
    assert isinstance(grammar, EBNFGrammar)
    assert provider.to_extra_body(grammar) is not None
