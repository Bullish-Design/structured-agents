"""Tests for Qwen3 grammar builder."""

import json

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


def test_structural_tag_payload_uses_triggered_tags_format() -> None:
    """The structural_tag payload must use TriggeredTagsFormat with triggers,
    not bare OrFormat/TagFormat. vLLM's xgrammar backend requires 'triggers'
    in the format to correctly dispatch tool calls."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=False,
    )
    tools = [
        _tool(
            "get_weather",
            {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        ),
        _tool(
            "search",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
    ]
    grammar = builder.build(tools, config)
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    fmt = tag_json["format"]
    assert fmt["type"] == "triggered_tags", (
        f"Expected 'triggered_tags' format, got '{fmt['type']}'"
    )
    assert "triggers" in fmt, "TriggeredTagsFormat must contain 'triggers'"
    assert fmt["triggers"] == ["<function="]
    assert "tags" in fmt
    assert len(fmt["tags"]) == 2
    assert fmt["tags"][0]["begin"] == "<function=get_weather>"
    assert fmt["tags"][1]["begin"] == "<function=search>"


def test_structural_tag_single_tool_uses_triggered_tags() -> None:
    """Even a single tool must use TriggeredTagsFormat."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=False,
    )
    grammar = builder.build(
        [
            _tool(
                "get_weather",
                {"type": "object", "properties": {"city": {"type": "string"}}},
            )
        ],
        config,
    )
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    fmt = tag_json["format"]
    assert fmt["type"] == "triggered_tags"
    assert fmt["triggers"] == ["<function="]
    assert len(fmt["tags"]) == 1


def test_structural_tag_parallel_uses_triggered_tags() -> None:
    """Parallel calls should NOT stop_after_first."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    )
    tools = [_tool("tool_a"), _tool("tool_b")]
    grammar = builder.build(tools, config)
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    fmt = tag_json["format"]
    assert fmt["type"] == "triggered_tags"
    assert fmt["stop_after_first"] is False


def test_structural_tag_sequential_stops_after_first() -> None:
    """Non-parallel calls should stop_after_first."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=False,
    )
    tools = [_tool("tool_a"), _tool("tool_b")]
    grammar = builder.build(tools, config)
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    fmt = tag_json["format"]
    assert fmt["type"] == "triggered_tags"
    assert fmt["stop_after_first"] is True
