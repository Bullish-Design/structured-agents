from __future__ import annotations

import json
from typing import Any, Callable

from structured_agents.grammar.config import DecodingConstraint
from structured_agents.types import ToolSchema


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

    if not tools:
        return None

    structures: list[dict[str, Any]] = []
    triggers: set[str] = set()

    for tool in tools:
        begin_tag = f"<function={tool.name}>"
        trigger = "<function="
        triggers.add(trigger)

        args_schema: dict[str, Any]
        args_schema = tool.parameters

        structures.append(
            {
                "begin": begin_tag,
                "schema": args_schema,
                "end": "</function>",
            }
        )

    legacy_payload = {
        "type": "structural_tag",
        "structures": structures,
        "triggers": sorted(triggers),
    }

    return {"structured_outputs": {"structural_tag": json.dumps(legacy_payload)}}
