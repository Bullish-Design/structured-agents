"""Constraint pipeline for grammar generation."""

from __future__ import annotations
from typing import Any, Callable
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.types import ToolSchema


class ConstraintPipeline:
    """Transforms tool schemas + config into vLLM grammar constraints."""

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
        """Build grammar constraints for the given tools.

        Returns the extra_body dict for vLLM, or None if no grammar is configured.
        """
        if not tools:
            return None
        return self._builder(tools, self._config)
