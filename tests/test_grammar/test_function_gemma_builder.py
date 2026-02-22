"""Tests for FunctionGemma grammar builder."""

from structured_agents.grammar.artifacts import EBNFGrammar, StructuralTagGrammar
from structured_agents.grammar.builders.function_gemma import (
    FunctionGemmaGrammarBuilder,
)
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


def _tool(name: str) -> ToolSchema:
    return ToolSchema(name=name, description="Test tool", parameters={})


def test_supports_mode() -> None:
    builder = FunctionGemmaGrammarBuilder()
    assert builder.supports_mode("ebnf") is True
    assert builder.supports_mode("structural_tag") is True
    assert builder.supports_mode("permissive") is False
    assert builder.supports_mode("json_schema") is False


def test_build_ebnf_parallel_calls() -> None:
    builder = FunctionGemmaGrammarBuilder()
    config = GrammarConfig(mode="ebnf", allow_parallel_calls=True, args_format="json")
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "root ::= function_call+" in grammar.grammar
    assert "tool_a" in grammar.grammar
    assert "arg_body ::= (pair" in grammar.grammar


def test_build_ebnf_single_call() -> None:
    builder = FunctionGemmaGrammarBuilder()
    config = GrammarConfig(
        mode="ebnf", allow_parallel_calls=False, args_format="permissive"
    )
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "root ::= function_call" in grammar.grammar
    assert "root ::= function_call+" not in grammar.grammar
    assert "arg_body ::= [^}]*" in grammar.grammar


def test_build_ebnf_escaped_strings() -> None:
    builder = FunctionGemmaGrammarBuilder()
    config = GrammarConfig(
        mode="ebnf", allow_parallel_calls=True, args_format="escaped_strings"
    )
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert 'escaped_string ::= "<escape>"' in grammar.grammar


def test_build_ebnf_escapes_tool_names() -> None:
    builder = FunctionGemmaGrammarBuilder()
    config = GrammarConfig(
        mode="ebnf", allow_parallel_calls=True, args_format="permissive"
    )
    grammar = builder.build([_tool('tool"quote')], config)
    assert isinstance(grammar, EBNFGrammar)
    assert 'tool\\"quote' in grammar.grammar


def test_build_structural_tag() -> None:
    builder = FunctionGemmaGrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag", allow_parallel_calls=False, args_format="json"
    )
    grammar = builder.build([_tool("tool_a"), _tool("tool_b")], config)
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    assert payload["structured_outputs"]["type"] == "structural_tag"
