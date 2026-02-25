"""Tests for grammar artifacts."""

from xgrammar import StructuralTag
from xgrammar.structural_tag import GrammarFormat, TagFormat

from structured_agents.grammar.artifacts import (
    EBNFGrammar,
    JsonSchemaGrammar,
    StructuralTagGrammar,
)


def test_ebnf_payload() -> None:
    grammar = EBNFGrammar(grammar='root ::= "ok"')
    payload = grammar.to_vllm_payload()
    assert payload == {
        "structured_outputs": {"type": "grammar", "grammar": 'root ::= "ok"'}
    }


def test_structural_tag_payload() -> None:
    tag = StructuralTag(
        format=TagFormat(
            begin="<start>",
            content=GrammarFormat(grammar="arg_body ::= [^}]*"),
            end="</start>",
        )
    )
    grammar = StructuralTagGrammar(tag=tag)
    payload = grammar.to_vllm_payload()
    assert payload["structured_outputs"]["type"] == "structural_tag"
    assert "structural_tag" in payload["structured_outputs"]
    assert payload["structured_outputs"]["structural_tag"] == tag.model_dump_json()


def test_json_schema_payload() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    grammar = JsonSchemaGrammar(schema=schema)
    payload = grammar.to_vllm_payload()
    assert payload["structured_outputs"]["type"] == "json"
    assert payload["structured_outputs"]["json"]["json_schema"] == schema
