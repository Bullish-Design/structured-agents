from __future__ import annotations

from typing import Any, Callable

from structured_agents.grammar.config import DecodingConstraint
from structured_agents.types import ToolSchema

from xgrammar.structural_tag import (
    Format,
    JSONSchemaFormat,
    OrFormat,
    QwenXMLParameterFormat,
    SequenceFormat,
    StructuralTag,
    TagFormat,
)


class ConstraintPipeline:
    """Transforms tool schemas plus decoding configuration into vLLM constraints."""

    def __init__(
        self,
        builder: Callable[
            [list[ToolSchema], DecodingConstraint], dict[str, Any] | None
        ],
        config: DecodingConstraint,
    ):
        self._builder = builder
        self._config = config

    def constrain(self, tools: list[ToolSchema]) -> dict[str, Any] | None:
        """Return the extra-body payload or None when no constraint is configured."""
        if not tools:
            return None
        return self._builder(tools, self._config)


def build_structural_tag_constraint(
    tools: list[ToolSchema], config: DecodingConstraint
) -> dict[str, Any] | None:
    """Build the `structural_tag` payload that vLLM expects."""
    if config.strategy != "structural_tag":
        return None

    tool_tags: list[Format] = []

    for tool in tools:
        args_schema: JSONSchemaFormat | QwenXMLParameterFormat
        if config.send_tools_to_api:
            args_schema = JSONSchemaFormat(json_schema=tool.parameters)
        else:
            args_schema = QwenXMLParameterFormat(
                json_schema={
                    "type": "qwen_xml_parameter",
                    "json_schema": tool.parameters,
                }
            )

        tool_tags.append(
            TagFormat(
                begin=f"<function={tool.name}>",
                content=args_schema,
                end="</function>",
            )
        )

    if len(tool_tags) == 1:
        tag_choice: Format = tool_tags[0]
    else:
        tag_choice = OrFormat(elements=tool_tags)

    if config.allow_parallel_calls:
        format_spec = SequenceFormat(elements=[tag_choice])
    else:
        format_spec = tag_choice

    payload = StructuralTag(format=format_spec)

    return {"structured_outputs": {"structural_tag": payload.model_dump()}}
