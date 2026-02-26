# tests/test_grammar/test_pipeline.py
import pytest
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.grammar.pipeline import ConstraintPipeline
from structured_agents.types import ToolSchema


def test_decoding_constraint_defaults():
    constraint = DecodingConstraint()
    assert constraint.strategy == "ebnf"
    assert constraint.allow_parallel_calls == False
    assert constraint.send_tools_to_api == False


def test_constraint_pipeline_returns_none_when_no_tools():
    # Mock builder that returns None
    mock_builder = lambda tools, config: None
    pipeline = ConstraintPipeline(builder=mock_builder, config=DecodingConstraint())

    result = pipeline.constrain([])
    assert result is None
