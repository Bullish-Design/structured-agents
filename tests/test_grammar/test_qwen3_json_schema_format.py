"""Tests for Qwen3 QwenXMLParameterFormat."""

import json
import pytest
from structured_agents.grammar.builders.qwen3 import Qwen3GrammarBuilder
from structured_agents.grammar.config import GrammarConfig
from structured_agents.grammar.artifacts import StructuralTagGrammar
from structured_agents.types import ToolSchema


def test_structural_tag_uses_qwen_xml_parameter_format():
    """Test that structural_tag mode uses QwenXMLParameterFormat inside TriggeredTagsFormat."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(mode="structural_tag", allow_parallel_calls=False)

    tool = ToolSchema(
        name="calculator",
        description="Calculator tool",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["add", "subtract"]},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
        },
    )

    grammar = builder.build([tool], config)
    assert grammar is not None
    assert isinstance(grammar, StructuralTagGrammar)

    # Check that it uses TriggeredTagsFormat with QwenXMLParameterFormat content
    tag_json = grammar.tag.model_dump_json()
    tag_dict = json.loads(tag_json)

    format_spec = tag_dict.get("format", {})
    assert format_spec.get("type") == "triggered_tags"
    tags = format_spec.get("tags", [])
    assert len(tags) == 1
    content = tags[0].get("content", {})
    assert content.get("type") == "qwen_xml_parameter", (
        f"Expected qwen_xml_parameter format, got {content.get('type')}"
    )
    assert "json_schema" in content, "Should have json_schema field"


def test_structural_tag_multiple_tools():
    """Test structural_tag with multiple tools uses TriggeredTagsFormat."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(mode="structural_tag", allow_parallel_calls=True)

    tools = [
        ToolSchema(
            name="add",
            description="Add two numbers",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
        ),
        ToolSchema(
            name="subtract",
            description="Subtract two numbers",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
        ),
    ]

    grammar = builder.build(tools, config)
    assert grammar is not None
    assert isinstance(grammar, StructuralTagGrammar)

    tag_json = grammar.tag.model_dump_json()
    tag_dict = json.loads(tag_json)

    # With allow_parallel_calls=True, should have TriggeredTagsFormat with both tools
    format_spec = tag_dict.get("format", {})
    assert format_spec.get("type") == "triggered_tags"
    assert format_spec.get("triggers") == ["<function="]
    assert format_spec.get("stop_after_first") is False
    tags = format_spec.get("tags", [])
    assert len(tags) == 2
    assert tags[0]["begin"] == "<function=add>"
    assert tags[1]["begin"] == "<function=subtract>"
