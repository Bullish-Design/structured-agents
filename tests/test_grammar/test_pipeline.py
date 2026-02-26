from structured_agents.grammar.pipeline import (
    ConstraintPipeline,
    build_structural_tag_constraint,
)
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.types import ToolSchema


def test_decoding_constraint_defaults() -> None:
    constraint = DecodingConstraint()
    assert constraint.strategy == "ebnf"
    assert not constraint.allow_parallel_calls
    assert not constraint.send_tools_to_api


def test_constraint_pipeline_returns_none_without_tools() -> None:
    pipeline = ConstraintPipeline(
        lambda tools, config: {"payload": True}, DecodingConstraint()
    )
    assert pipeline.constrain([]) is None


def test_constraint_pipeline_invokes_builder() -> None:
    observed: list[list[ToolSchema]] = []

    def builder(tools: list[ToolSchema], config: DecodingConstraint) -> dict[str, bool]:
        observed.append(tools)
        return {"evaluated": True}

    pipeline = ConstraintPipeline(builder, DecodingConstraint())
    result = pipeline.constrain(
        [
            ToolSchema(
                name="add",
                description="Add numbers",
                parameters={"type": "object", "properties": {"a": {"type": "number"}}},
            )
        ]
    )

    assert result == {"evaluated": True}
    assert len(observed) == 1
    assert observed[0][0].name == "add"


def test_build_structural_tag_constraint() -> None:
    constraint = DecodingConstraint(
        strategy="structural_tag", allow_parallel_calls=True
    )
    tools = [
        ToolSchema(
            name="echo",
            description="Echo tool",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        )
    ]

    payload = build_structural_tag_constraint(tools, constraint)
    assert payload is not None
    structured = payload["structured_outputs"]
    assert "structural_tag" in structured
    tag = structured["structural_tag"]
    assert tag["type"] == "structural_tag"
    assert tag["format"]["type"] == "sequence"

    # when only one tool and allow_parallel_calls=False expect tag directly
    payload_single = build_structural_tag_constraint(
        tools,
        DecodingConstraint(strategy="structural_tag", allow_parallel_calls=False),
    )
    assert payload_single is not None
    format_type = payload_single["structured_outputs"]["structural_tag"]["format"][
        "type"
    ]
    assert format_type in {"tag", "or"}
