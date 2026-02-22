"""Integration tests for grammar constraints with vLLM."""

from __future__ import annotations

import os

import pytest

from structured_agents.client.openai_compat import OpenAICompatibleClient
from structured_agents.grammar.config import GrammarConfig
from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.types import KernelConfig, Message, ToolSchema


@pytest.mark.asyncio
async def test_vllm_grammar_acceptance() -> None:
    base_url = os.getenv("VLLM_BASE_URL")
    model = os.getenv("FUNCTION_GEMMA_MODEL")
    if not base_url or not model:
        pytest.skip("VLLM_BASE_URL and FUNCTION_GEMMA_MODEL are required")

    plugin = FunctionGemmaPlugin()
    tools = [
        ToolSchema(
            name="echo",
            description="Echo input",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
    ]
    messages = [
        Message(
            role="user",
            content="Call the echo tool with text 'hello'.",
        )
    ]

    grammar_config = GrammarConfig(
        mode="json_schema", allow_parallel_calls=False, args_format="json"
    )
    grammar = plugin.build_grammar(tools, grammar_config)
    extra_body = plugin.to_extra_body(grammar)

    client = OpenAICompatibleClient(KernelConfig(base_url=base_url, model=model))
    try:
        response = await client.chat_completion(
            messages=plugin.format_messages(messages, tools),
            tools=plugin.format_tools(tools),
            tool_choice="auto",
            extra_body=extra_body,
        )
    finally:
        await client.close()

    _, tool_calls = plugin.parse_response(response.content, response.tool_calls)
    assert tool_calls
    assert tool_calls[0].name == "echo"
