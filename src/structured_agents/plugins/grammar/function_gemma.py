"""EBNF grammar builder for FunctionGemma format."""

from __future__ import annotations

from structured_agents.types import ToolSchema


def build_functiongemma_grammar(tools: list[ToolSchema]) -> str:
    """Build EBNF grammar for FunctionGemma tool calling format.

    FunctionGemma uses a specific format:
        <start_function_call>call:tool_name{arg1:value1,arg2:value2}<end_function_call>

    This grammar ensures the model output follows this format exactly.

    Args:
        tools: Available tool schemas.

    Returns:
        EBNF grammar string for XGrammar.
    """
    if not tools:
        return ""

    tool_names = [tool.name for tool in tools]
    tool_name_rule = " | ".join(f'"{name}"' for name in tool_names)

    grammar = f"""
root ::= function_call

function_call ::= "<start_function_call>" "call:" tool_name "{{" arg_body "}}" "<end_function_call>"

tool_name ::= {tool_name_rule}

arg_body ::= arg_char*

arg_char ::= [^}}]
"""
    return grammar.strip()
