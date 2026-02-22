"""Tests for schema-aware FunctionGemma grammar builder."""

from structured_agents.grammar.artifacts import EBNFGrammar
from structured_agents.grammar.builders.schema_aware_function_gemma import (
    FunctionGemmaSchemaGrammarBuilder,
)
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


def test_schema_builder_supports_mode() -> None:
    builder = FunctionGemmaSchemaGrammarBuilder()
    assert builder.supports_mode("json_schema") is True
    assert builder.supports_mode("ebnf") is False


def test_schema_builder_emits_schema_rules() -> None:
    builder = FunctionGemmaSchemaGrammarBuilder()
    tool = ToolSchema(
        name="summarize",
        description="Summarize input",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"},
                "mode": {"enum": ["fast", "slow"]},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text", "mode"],
        },
    )
    config = GrammarConfig(mode="json_schema", allow_parallel_calls=False)
    grammar = builder.build([tool], config)

    assert isinstance(grammar, EBNFGrammar)
    assert "summarize" in grammar.grammar
    assert '\\"text\\"' in grammar.grammar
    assert '\\"mode\\"' in grammar.grammar
    assert '"fast"' in grammar.grammar
    assert '"["' in grammar.grammar
