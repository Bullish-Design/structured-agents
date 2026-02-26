"""AgentKernel - the core agent loop orchestrator."""

from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Sequence
from structured_agents.client.protocol import CompletionResponse, LLMClient
from structured_agents.events.observer import NullObserver, Observer
from structured_agents.events.types import (
    Event,
    KernelStartEvent,
    KernelEndEvent,
    ModelRequestEvent,
    ModelResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnCompleteEvent,
)
from structured_agents.models.adapter import ModelAdapter
from structured_agents.tools.protocol import Tool
from structured_agents.types import (
    KernelConfig,
    Message,
    RunResult,
    StepResult,
    TokenUsage,
    ToolCall,
    ToolResult,
    ToolSchema,
)


@dataclass
class AgentKernel:
    """The core agent loop orchestrator."""

    client: LLMClient
    adapter: ModelAdapter
    tools: list[Tool] = field(default_factory=list)
    observer: Observer = field(default_factory=NullObserver)
    max_history_messages: int = 50
    max_concurrency: int = 1
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_choice: str = "auto"

    def _tool_map(self) -> dict[str, Tool]:
        return {t.schema.name: t for t in self.tools}

    async def step(
        self,
        messages: list[Message],
        tools: Sequence[ToolSchema] | Sequence[str],
    ) -> StepResult:
        """Execute a single turn: model call + tool execution."""
        # Resolve tools
        resolved_tools = []
        for t in tools:
            if isinstance(t, ToolSchema):
                resolved_tools.append(t)
            elif isinstance(t, str):
                tool = self._tool_map().get(t)
                if tool:
                    resolved_tools.append(tool.schema)

        # Format for model
        formatter = self.adapter.format_messages
        formatted_messages = formatter(messages, []) if formatter else []
        if resolved_tools:
            tool_formatter = self.adapter.format_tools
            formatted_tools = tool_formatter(resolved_tools) if tool_formatter else None
        else:
            formatted_tools = None

        # Build grammar constraint
        grammar_constraint = None
        if self.adapter.grammar_builder:
            grammar_constraint = self.adapter.grammar_builder(resolved_tools, None)

        extra_body = grammar_constraint

        # Make API call
        response = await self.client.chat_completion(
            messages=formatted_messages,
            tools=formatted_tools,
            tool_choice=self.tool_choice if resolved_tools else "none",
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            extra_body=extra_body,
        )

        # Parse response
        content, tool_calls = self.adapter.response_parser.parse(
            response.content, response.tool_calls
        )

        response_message = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls if tool_calls else None,
        )

        # Execute tools
        tool_results = []
        tool_map = self._tool_map()

        async def execute_one(tc: ToolCall):
            tool = tool_map.get(tc.name)
            if not tool:
                return ToolResult(
                    call_id=tc.id,
                    name=tc.name,
                    output=f"Unknown tool: {tc.name}",
                    is_error=True,
                )
            return await tool.execute(tc.arguments, None)

        if tool_calls:
            if self.max_concurrency <= 1:
                tool_results = [await execute_one(tc) for tc in tool_calls]
            else:
                sem = asyncio.Semaphore(self.max_concurrency)

                async def bounded(tc):
                    async with sem:
                        return await execute_one(tc)

                tool_results = await asyncio.gather(*[bounded(tc) for tc in tool_calls])

        return StepResult(
            response_message=response_message,
            tool_calls=list(tool_calls) if tool_calls else [],
            tool_results=tool_results,
            usage=response.usage,
        )

    async def run(
        self,
        initial_messages: list[Message],
        tools: Sequence[ToolSchema] | Sequence[str],
        max_turns: int = 20,
    ) -> RunResult:
        """Execute the full agent loop."""
        messages = list(initial_messages)
        turn_count = 0
        termination_reason = "max_turns"

        await self.observer.emit(
            KernelStartEvent(
                max_turns=max_turns,
                tools_count=len(self.tools),
                initial_messages_count=len(initial_messages),
            )
        )

        while turn_count < max_turns:
            turn_count += 1

            step_result = await self.step(messages, tools)

            messages.append(step_result.response_message)
            for result in step_result.tool_results:
                messages.append(result.to_message())

            if not step_result.tool_calls:
                # TODO: Termination reason naming is ambiguous.
                #
                # Issue: "no_tool_calls" is misleading because:
                #   - It could mean "no tools were ever called" (never made any tool calls)
                #   - It actually means "model stopped making tool calls" (completed tool use)
                #
                # Option 1 - Clearer naming:
                #   - "text_response"     = model returned text without calling tools
                #   - "tools_exhausted"   = model called tools until done, then returned text
                #   - "max_turns"         = hit turn limit
                #   - "error"             = encountered an error
                #
                # Option 2 - Add metadata to RunResult:
                #   - Add field like `tools_called_count: int` to TrackResult
                #   - Or add `had_tool_calls: bool` to RunResult
                #   - Then caller can distinguish:
                #       if result.termination_reason == "no_tool_calls" and result.tools_called_count > 0:
                #           # Successfully called tools until done
                #
                # For now, current behavior is:
                #   - "no_tool_calls" means model returned text (either never called tools OR finished calling them)
                #   - This is the standard pattern: agent loop continues until model stops making tool calls
                termination_reason = "no_tool_calls"
                break

        final_message = (
            messages[-1] if messages else Message(role="assistant", content="")
        )

        return RunResult(
            final_message=final_message,
            history=messages,
            turn_count=turn_count,
            termination_reason=termination_reason,
        )

    async def close(self) -> None:
        await self.client.close()
