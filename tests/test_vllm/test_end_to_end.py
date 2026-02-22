"""End-to-end vLLM integration tests."""

from __future__ import annotations

import os

import pytest

from structured_agents.backends import PythonBackend
from structured_agents.kernel import AgentKernel
from structured_agents.plugins import FunctionGemmaPlugin
from structured_agents.registries.python import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
from structured_agents.types import KernelConfig, Message, ToolResult, ToolSchema


@pytest.mark.asyncio
async def test_end_to_end_tool_flow() -> None:
    base_url = os.getenv("VLLM_BASE_URL")
    model = os.getenv("FUNCTION_GEMMA_MODEL")
    if not base_url or not model:
        pytest.skip("VLLM_BASE_URL and FUNCTION_GEMMA_MODEL are required")

    registry = PythonRegistry()
    backend = PythonBackend(registry=registry)

    async def echo(text: str) -> str:
        return text

    async def submit_result(summary: str) -> dict[str, str]:
        return {"summary": summary}

    backend.register("echo", echo)
    backend.register("submit_result", submit_result)

    tool_source = RegistryBackendToolSource(registry, backend)
    kernel = AgentKernel(
        config=KernelConfig(base_url=base_url, model=model),
        plugin=FunctionGemmaPlugin(),
        tool_source=tool_source,
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
        ),
        ToolSchema(
            name="submit_result",
            description="Submit final result",
            parameters={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        ),
    ]

    messages = [
        Message(
            role="user",
            content="Call echo with 'done', then call submit_result with the same text.",
        )
    ]

    def is_submit(result: ToolResult) -> bool:
        return result.name == "submit_result"

    result = await kernel.run(messages, tools, max_turns=5, termination=is_submit)

    assert result.final_tool_result is not None
    assert result.final_tool_result.name == "submit_result"
    assert result.termination_reason == "termination_tool"

    await kernel.close()
