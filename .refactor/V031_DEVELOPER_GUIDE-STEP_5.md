You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_5.md
This is Step 5 of 7: "Kernel — Fix bugs, emit events, add error handling"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
The kernel is the core agent loop — it orchestrates model calls and tool execution. This step fixes multiple issues: BUG-3 (tool context), event emission, tool_map caching, error handling, and max_history_messages.
## Current state of kernel.py:
```python
"""AgentKernel - the core agent loop orchestrator."""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Sequence
from structured_agents.client.protocol import CompletionResponse, LLMClient
from structured_agents.events.observer import NullObserver, Observer
from structured_agents.events.types import (
    Event, KernelStartEvent, KernelEndEvent, ModelRequestEvent,
    ModelResponseEvent, ToolCallEvent, ToolResultEvent, TurnCompleteEvent,
)
from structured_agents.models.adapter import ModelAdapter
from structured_agents.tools.protocol import Tool
from structured_agents.types import (
    KernelConfig, Message, RunResult, StepResult, TokenUsage, ToolCall, ToolResult, ToolSchema,
)
@dataclass
class AgentKernel:
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
    async def step(self, messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str]) -> StepResult:
        resolved_tools = []
        for t in tools:
            if isinstance(t, ToolSchema):
                resolved_tools.append(t)
            elif isinstance(t, str):
                tool = self._tool_map().get(t)
                if tool:
                    resolved_tools.append(tool.schema)
        formatter = self.adapter.format_messages
        formatted_messages = formatter(messages, []) if formatter else []
        if resolved_tools:
            tool_formatter = self.adapter.format_tools
            formatted_tools = tool_formatter(resolved_tools) if tool_formatter else None
        else:
            formatted_tools = None
        grammar_constraint = None
        if self.adapter.grammar_builder:
            grammar_constraint = self.adapter.grammar_builder(resolved_tools, None)
        extra_body = grammar_constraint
        response = await self.client.chat_completion(
            messages=formatted_messages,
            tools=formatted_tools,
            tool_choice=self.tool_choice if resolved_tools else "none",
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            extra_body=extra_body,
        )
        content, tool_calls = self.adapter.response_parser.parse(response.content, response.tool_calls)
        response_message = Message(role="assistant", content=content, tool_calls=tool_calls if tool_calls else None)
        tool_results = []
        tool_map = self._tool_map()
        async def execute_one(tc: ToolCall):
            tool = tool_map.get(tc.name)
            if not tool:
                return ToolResult(call_id=tc.id, name=tc.name, output=f"Unknown tool: {tc.name}", is_error=True)
            return await tool.execute(tc.arguments, None)  # BUG-3: passes None instead of tc
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
    async def run(self, initial_messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str], max_turns: int = 20) -> RunResult:
        messages = list(initial_messages)
        turn_count = 0
        termination_reason = "max_turns"
        await self.observer.emit(KernelStartEvent(max_turns=max_turns, tools_count=len(self.tools), initial_messages_count=len(initial_messages)))
        while turn_count < max_turns:
            turn_count += 1
            step_result = await self.step(messages, tools)
            messages.append(step_result.response_message)
            for result in step_result.tool_results:
                messages.append(result.to_message())
            if not step_result.tool_calls:
                termination_reason = "no_tool_calls"
                break
        final_message = messages[-1] if messages else Message(role="assistant", content="")
        return RunResult(
            final_message=final_message,
            history=messages,
            turn_count=turn_count,
            termination_reason=termination_reason,
        )
    async def close(self) -> None:
        await self.client.close()
```
## Event types already defined (events/types.py — no changes needed):
```python
KernelStartEvent(max_turns, tools_count, initial_messages_count)
KernelEndEvent(turn_count, termination_reason, total_duration_ms)
ModelRequestEvent(turn, messages_count, tools_count, model)
ModelResponseEvent(turn, duration_ms, content, tool_calls_count, usage)
ToolCallEvent(turn, tool_name, call_id, arguments)
ToolResultEvent(turn, tool_name, call_id, is_error, duration_ms, output_preview)
TurnCompleteEvent(turn, tool_calls_count, tool_results_count, errors_count)
```
## What the guide should instruct the developer to do:
### 1. Fix BUG-3 — Pass ToolCall as context to tool.execute():
Change `await tool.execute(tc.arguments, None)` to `await tool.execute(tc.arguments, tc)`.
The `tc` IS the `ToolCall` object. The `Tool.execute()` protocol now expects `context: ToolCall | None` (from Step 4).
### 2. Cache the tool map:
Build it once in `__post_init__` and rebuild when tools change. Replace the `_tool_map()` method with:
```python
def __post_init__(self) -> None:
    self._tool_map: dict[str, Tool] = {t.schema.name: t for t in self.tools}
```
Then reference `self._tool_map` as an attribute, not a method call.
### 3. Emit ALL 7 event types:
Place events at the correct lifecycle points:
In `run()`:
- `KernelStartEvent` — already emitted at the start (keep it)
- `ModelRequestEvent` — before each `self.step()` call inside the loop
- `TurnCompleteEvent` — at the end of each turn inside the loop
- `KernelEndEvent` — after the loop ends, before returning RunResult
In `step()`:
- `ModelResponseEvent` — after the API call returns (time the call)
- `ToolCallEvent` — before each tool execution
- `ToolResultEvent` — after each tool execution (time each tool)
The `step()` method needs a `turn` parameter to include in events. Add it as an optional parameter: `turn: int = 0`.
### 4. Fix tool_choice when no tools:
Instead of `tool_choice="none"` (which some backends don't support), just don't send `tool_choice` at all when there are no tools. The client already handles this via kwargs (Step 2).
### 5. Implement max_history_messages:
In `run()`, before each step, trim the message history if it exceeds `max_history_messages`:
```python
if len(messages) > self.max_history_messages:
    # Keep the system prompt (first message) + most recent messages
    messages = [messages[0]] + messages[-(self.max_history_messages - 1):]
```
### 6. Fix format_messages call:
After Step 3, the `format_messages` signature changed — it no longer takes a `tools` parameter. Update the call from:
```python
formatted_messages = formatter(messages, []) if formatter else []
```
to:
```python
formatted_messages = formatter(messages) if formatter else []
```
### 7. Pass grammar_config to grammar_builder:
Instead of `self.adapter.grammar_builder(resolved_tools, None)`, pass the config:
```python
grammar_constraint = self.adapter.grammar_builder(resolved_tools, self.adapter.grammar_config)
```
### 8. Remove KernelConfig import:
KernelConfig was removed in Step 1. Remove it from the import.
### 9. Add basic error handling:
Wrap the API call in try/except to emit error events and wrap in KernelError:
```python
from structured_agents.exceptions import KernelError, ToolExecutionError
```
- If the API call fails, emit an error event and raise `KernelError`.
- Individual tool execution failures are already handled (returns ToolResult with is_error=True), but wrap asyncio.gather to isolate per-tool failures.
### 10. Fix tool_results type:
`asyncio.gather` returns `list[Any]`. Cast the result: `tool_results = list(await asyncio.gather(...))`.
## IMPORTANT NOTES:
- Show the COMPLETE final version of kernel.py.
- This is the most complex step. Take care with event placement.
- The `time` module is already imported but unused — now it will be used for duration tracking.
- Explain the step() turn parameter addition.
- Include a "Verification" section.
Return a brief (2-3 sentence) confirmation when done.