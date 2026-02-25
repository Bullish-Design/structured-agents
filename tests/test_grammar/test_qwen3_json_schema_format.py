"""Tests for Qwen3 JSONSchemaFormat with qwen_xml style."""

import json
import pytest
from structured_agents.grammar.builders.qwen3 import Qwen3GrammarBuilder
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


def test_structural_tag_uses_json_schema_format():
    """Test that structural_tag mode uses JSONSchemaFormat with qwen_xml style."""
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

    # Check that it uses JSON schema with qwen_xml style
    tag_json = grammar.tag.model_dump_json()
    tag_dict = json.loads(tag_json)

    # Verify the structure uses JSONSchemaFormat
    format = tag_dict.get("format", {})
    content = format.get("content", {})
    assert content.get("type") == "json_schema", (
        f"Expected json_schema format, got {content.get('type')}"
    )
