from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GrammarConfig:
    """Configuration for grammar generation."""

    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = True
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"
    send_tools_to_api: bool = True
    """Whether to send tools to the API.
    
    When True (default), tools are sent to vLLM which may override
    the grammar constraint with its own JSON schema for tool calling.
    
    When False, tools are NOT sent to vLLM. This is needed for EBNF
    mode to work properly, as vLLM otherwise overrides our grammar.
    The response parser will still extract tool calls from the model's
    constrained output.
    """
