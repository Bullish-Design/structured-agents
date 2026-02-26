from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DecodingConstraint:
    """How to constrain the model's output to valid tool calls."""

    strategy: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = False
    send_tools_to_api: bool = False
