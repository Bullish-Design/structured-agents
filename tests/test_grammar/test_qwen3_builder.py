"""Tests for Qwen3 grammar builder."""

from structured_agents.grammar.artifacts import (
    EBNFGrammar,
    JsonSchemaGrammar,
    StructuralTagGrammar,
)
from structured_agents.grammar.builders.qwen3 import Qwen3GrammarBuilder
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


def _tool(name: str, parameters: dict | None = None) -> ToolSchema:
    return ToolSchema(
        name=name,
        description="Test tool",
        parameters=parameters or {"type": "object", "properties": {}},
    )


def test_supports_mode() -> None:
    builder = Qwen3GrammarBuilder()
    assert builder.supports_mode("structural_tag") is True
    assert builder.supports_mode("json_schema") is True
    assert builder.supports_mode("ebnf") is True
    assert builder.supports_mode("unknown") is False


def test_build_structural_tag_single_tool() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=False,
    )
    tool = _tool(
        "get_weather",
        {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    grammar = builder.build([tool], config)
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    assert "structural_tag" in payload["structured_outputs"]


def test_build_structural_tag_multiple_tools() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    )
    tools = [
        _tool("get_weather"),
        _tool("search"),
    ]
    grammar = builder.build(tools, config)
    assert isinstance(grammar, StructuralTagGrammar)


def test_build_structural_tag_parallel_calls() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    )
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, StructuralTagGrammar)


def test_build_structural_tag_empty_tools() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    )
    grammar = builder.build([], config)
    assert grammar is None


def test_build_json_schema_single_tool() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="json_schema",
        allow_parallel_calls=False,
    )
    tool = _tool(
        "get_weather",
        {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    )
    grammar = builder.build([tool], config)
    assert isinstance(grammar, JsonSchemaGrammar)


def test_build_json_schema_multiple_tools() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="json_schema",
        allow_parallel_calls=True,
    )
    tools = [
        _tool("get_weather"),
        _tool("search"),
    ]
    grammar = builder.build(tools, config)
    assert isinstance(grammar, JsonSchemaGrammar)


def test_build_ebnf_single_tool() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="ebnf",
        allow_parallel_calls=False,
    )
    tool = _tool(
        "get_weather",
        {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    )
    grammar = builder.build([tool], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "get_weather" in grammar.grammar
    assert "<function=" in grammar.grammar


def test_build_ebnf_parallel_calls() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="ebnf",
        allow_parallel_calls=True,
    )
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "tool_call+" in grammar.grammar
