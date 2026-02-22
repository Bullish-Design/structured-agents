"""Integration tests for FunctionGemma plugin with vLLM."""

from __future__ import annotations

import os

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.grammar.config import GrammarConfig
from structured_agents.kernel import AgentKernel
from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
from structured_agents.types import KernelConfig, Message, ToolSchema


@pytest.mark.asyncio
async def test_function_gemma_tool_execution() -> None:
    base_url = os.getenv("VLLM_BASE_URL")
    model = os.getenv("FUNCTION_GEMMA_MODEL")
    if not base_url or not model:
        pytest.skip("VLLM_BASE_URL and FUNCTION_GEMMA_MODEL are required")

    registry = PythonRegistry()
    backend = PythonBackend(registry=registry)

    async def echo(text: str = "") -> str:
        return text

    backend.register("echo", echo)

    tool_source = RegistryBackendToolSource(registry, backend)
    kernel = AgentKernel(
        config=KernelConfig(base_url=base_url, model=model),
        plugin=FunctionGemmaPlugin(),
        tool_source=tool_source,
        grammar_config=GrammarConfig(mode="json_schema", allow_parallel_calls=False),
    )

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
            content='Call the echo tool with JSON arguments {"text": "ping"}.',
        )
    ]

    result = await kernel.step(messages, tools)

    assert result.tool_calls
    assert result.tool_results
    assert result.tool_calls[0].name == "echo"
    assert result.tool_results[0].name == "echo"
    assert result.tool_results[0].is_error is False
    assert isinstance(result.tool_results[0].output, str)

    await kernel.close()
