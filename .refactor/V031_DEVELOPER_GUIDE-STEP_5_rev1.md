# Developer Guide: Step 5 — Kernel Fixes, Events, and Error Handling

**Previous Steps:** Steps 1-4 completed | **Next Step:** Step 6

---

## Overview

This step addresses critical bugs and adds comprehensive event emission to the kernel. The kernel is the core agent loop — it orchestrates model calls and tool execution. We'll fix multiple issues identified in the codebase.

---

## Changes Required

### 1. Fix BUG-3 — Pass ToolCall as Context to tool.execute()

**File:** `src/structured_agents/kernel.py`

**Bug:** The `execute_one` function passes `None` instead of the `ToolCall` object as context.

**Before:**
```python
return await tool.execute(tc.arguments, None)  # BUG-3: passes None instead of tc
```

**After:**
```python
return await tool.execute(tc.arguments, tc)
```

The `tc` variable IS the `ToolCall` object. The `Tool.execute()` protocol expects `context: ToolCall | None` (from Step 4).

---

### 2. Cache the Tool Map

**Problem:** The `_tool_map()` method is called multiple times per step, rebuilding the dictionary each time.

**Solution:** Build it once in `__post_init__` and reference it as an attribute.

**Add to `AgentKernel` class:**
```python
def __post_init__(self) -> None:
    self._tool_map: dict[str, Tool] = {t.schema.name: t for t in self.tools}
```

**Replace the `_tool_map()` method with direct attribute access:**
- Change `self._tool_map().get(t)` to `self._tool_map.get(t)`
- Change `tool_map = self._tool_map()` to `tool_map = self._tool_map`

---

### 3. Emit ALL 7 Event Types

The kernel must emit events at key lifecycle points. We'll emit:

| Event Type | Where to Emit | Purpose |
|------------|---------------|---------|
| `KernelStartEvent` | `run()` — start of method | Log kernel initialization |
| `ModelRequestEvent` | `run()` — before each `step()` | Log model request details |
| `ModelResponseEvent` | `step()` — after API call returns | Log response with duration |
| `ToolCallEvent` | `step()` — before each tool execution | Log tool invocation |
| `ToolResultEvent` | `step()` — after each tool execution | Log tool result with duration |
| `TurnCompleteEvent` | `run()` — end of each turn | Log turn completion |
| `KernelEndEvent` | `run()` — after loop ends | Log kernel termination |

#### Add `turn` Parameter to `step()`

The `step()` method needs a `turn` parameter to include in events.

**Signature change:**
```python
async def step(self, messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str], turn: int = 0) -> StepResult:
```

---

### 4. Fix tool_choice When No Tools

**Problem:** Some backends don't support `tool_choice="none"`.

**Solution:** Don't send `tool_choice` at all when there are no tools.

**Before:**
```python
tool_choice=self.tool_choice if resolved_tools else "none"
```

**After:**
```python
tool_choice=self.tool_choice if resolved_tools else None
```

Then, only include it in the API call if it's not `None`.

---

### 5. Implement max_history_messages

**File:** `src/structured_agents/kernel.py`

Add message history trimming in the `run()` method before each step:

```python
if len(messages) > self.max_history_messages:
    # Keep the system prompt (first message) + most recent messages
    messages = [messages[0]] + messages[-(self.max_history_messages - 1):]
```

---

### 6. Fix format_messages Call

**Problem:** After Step 3, the `format_messages` signature changed — it no longer takes a `tools` parameter.

**Before:**
```python
formatted_messages = formatter(messages, []) if formatter else []
```

**After:**
```python
formatted_messages = formatter(messages) if formatter else []
```

---

### 7. Pass grammar_config to grammar_builder

**Before:**
```python
grammar_constraint = self.adapter.grammar_builder(resolved_tools, None)
```

**After:**
```python
grammar_constraint = self.adapter.grammar_builder(resolved_tools, self.adapter.grammar_config)
```

---

### 8. Remove KernelConfig Import

**File:** `src/structured_agents/kernel.py`

**Remove from imports:**
```python
from structured_agents.types import (
    KernelConfig,  # <-- REMOVE THIS
    Message, RunResult, StepResult, TokenUsage, ToolCall, ToolResult, ToolSchema,
)
```

---

### 9. Add Basic Error Handling

**Add imports:**
```python
from structured_agents.exceptions import KernelError, ToolExecutionError
```

#### API Call Error Handling

Wrap the API call in try/except:

```python
try:
    response = await self.client.chat_completion(
        messages=formatted_messages,
        tools=formatted_tools,
        tool_choice=...,
        max_tokens=self.max_tokens,
        temperature=self.temperature,
        extra_body=extra_body,
    )
except Exception as e:
    raise KernelError(f"Model API call failed: {e}") from e
```

#### Tool Execution Error Handling

For `asyncio.gather`, use `return_exceptions=True` to isolate per-tool failures:

```python
tool_results = list(await asyncio.gather(*[bounded(tc) for tc in tool_calls], return_exceptions=True))
```

Then convert any exceptions to error `ToolResult` objects:

```python
for i, result in enumerate(tool_results):
    if isinstance(result, Exception):
        tool_calls_ = tool_calls[i] if tool_calls else None
        tool_results[i] = ToolResult(
            call_id=tool_calls_.id if tool_calls_ else "",
            name=tool_calls_.name if tool_calls_ else "unknown",
            output=str(result),
            is_error=True,
        )
```

---

### 10. Fix tool_results Type

`asyncio.gather` returns `list[Any]`. Cast the result:

**Before:**
```python
tool_results = await asyncio.gather(*[bounded(tc) for tc in tool_calls])
```

**After:**
```python
tool_results = list(await asyncio.gather(*[bounded(tc) for tc in tool_calls], return_exceptions=True))
```

---

## Complete Final Version of kernel.py

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
from structured_agents.exceptions import KernelError, ToolExecutionError
from structured_agents.models.adapter import ModelAdapter
from structured_agents.tools.protocol import Tool
from structured_agents.types import (
    Message, RunResult, StepResult, TokenUsage, ToolCall, ToolResult, ToolSchema,
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

    def __post_init__(self) -> None:
        self._tool_map: dict[str, Tool] = {t.schema.name: t for t in self.tools}

    async def step(
        self, messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str], turn: int = 0
    ) -> StepResult:
        resolved_tools = []
        for t in tools:
            if isinstance(t, ToolSchema):
                resolved_tools.append(t)
            elif isinstance(t, str):
                tool = self._tool_map.get(t)
                if tool:
                    resolved_tools.append(tool.schema)

        formatter = self.adapter.format_messages
        formatted_messages = formatter(messages) if formatter else []

        if resolved_tools:
            tool_formatter = self.adapter.format_tools
            formatted_tools = tool_formatter(resolved_tools) if tool_formatter else None
        else:
            formatted_tools = None

        grammar_constraint = None
        if self.adapter.grammar_builder:
            grammar_constraint = self.adapter.grammar_builder(
                resolved_tools, self.adapter.grammar_config
            )

        extra_body = grammar_constraint

        request_start = time.perf_counter()
        tool_choice_value = self.tool_choice if resolved_tools else None

        try:
            response = await self.client.chat_completion(
                messages=formatted_messages,
                tools=formatted_tools,
                tool_choice=tool_choice_value,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                extra_body=extra_body,
            )
        except Exception as e:
            raise KernelError(f"Model API call failed: {e}") from e

        request_duration = int((time.perf_counter() - request_start) * 1000)

        await self.observer.emit(
            ModelResponseEvent(
                turn=turn,
                duration_ms=request_duration,
                content=response.content,
                tool_calls_count=len(response.tool_calls) if response.tool_calls else 0,
                usage=response.usage,
            )
        )

        content, tool_calls = self.adapter.response_parser.parse(
            response.content, response.tool_calls
        )
        response_message = Message(
            role="assistant", content=content, tool_calls=tool_calls if tool_calls else None
        )

        tool_results = []

        async def execute_one(tc: ToolCall):
            call_start = time.perf_counter()
            await self.observer.emit(
                ToolCallEvent(turn=turn, tool_name=tc.name, call_id=tc.id, arguments=tc.arguments)
            )

            tool = self._tool_map.get(tc.name)
            if not tool:
                result = ToolResult(
                    call_id=tc.id,
                    name=tc.name,
                    output=f"Unknown tool: {tc.name}",
                    is_error=True,
                )
            else:
                try:
                    result = await tool.execute(tc.arguments, tc)
                except Exception as e:
                    result = ToolResult(
                        call_id=tc.id,
                        name=tc.name,
                        output=f"Tool execution failed: {e}",
                        is_error=True,
                    )

            duration = int((time.perf_counter() - call_start) * 1000)
            await self.observer.emit(
                ToolResultEvent(
                    turn=turn,
                    tool_name=result.name,
                    call_id=result.call_id,
                    is_error=result.is_error,
                    duration_ms=duration,
                    output_preview=result.output[:100] if result.output else "",
                )
            )
            return result

        if tool_calls:
            if self.max_concurrency <= 1:
                tool_results = [await execute_one(tc) for tc in tool_calls]
            else:
                sem = asyncio.Semaphore(self.max_concurrency)

                async def bounded(tc: ToolCall):
                    async with sem:
                        return await execute_one(tc)

                results = await asyncio.gather(
                    *[bounded(tc) for tc in tool_calls], return_exceptions=True
                )
                tool_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        tc = tool_calls[i]
                        tool_results.append(
                            ToolResult(
                                call_id=tc.id,
                                name=tc.name,
                                output=str(result),
                                is_error=True,
                            )
                        )
                    else:
                        tool_results.append(result)

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
        messages = list(initial_messages)
        turn_count = 0
        termination_reason = "max_turns"
        start_time = time.perf_counter()

        await self.observer.emit(
            KernelStartEvent(
                max_turns=max_turns,
                tools_count=len(self.tools),
                initial_messages_count=len(initial_messages),
            )
        )

        while turn_count < max_turns:
            turn_count += 1

            if len(messages) > self.max_history_messages:
                messages = [messages[0]] + messages[-(self.max_history_messages - 1) :]

            await self.observer.emit(
                ModelRequestEvent(
                    turn=turn_count,
                    messages_count=len(messages),
                    tools_count=len(self.tools),
                    model=getattr(self.client, "model", "unknown"),
                )
            )

            step_result = await self.step(messages, tools, turn=turn_count)

            messages.append(step_result.response_message)

            for result in step_result.tool_results:
                messages.append(result.to_message())

            errors_count = sum(1 for r in step_result.tool_results if r.is_error)
            await self.observer.emit(
                TurnCompleteEvent(
                    turn=turn_count,
                    tool_calls_count=len(step_result.tool_calls),
                    tool_results_count=len(step_result.tool_results),
                    errors_count=errors_count,
                )
            )

            if not step_result.tool_calls:
                termination_reason = "no_tool_calls"
                break

        total_duration_ms = int((time.perf_counter() - start_time) * 1000)

        await self.observer.emit(
            KernelEndEvent(
                turn_count=turn_count,
                termination_reason=termination_reason,
                total_duration_ms=total_duration_ms,
            )
        )

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

---

## Key Implementation Details

### The `turn` Parameter

The `step()` method now accepts an optional `turn` parameter:

```python
async def step(self, messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str], turn: int = 0) -> StepResult:
```

This parameter is:
- **Default value:** `0` — for backward compatibility when calling `step()` directly
- **Passed from `run()`:** The current turn number (1-indexed)
- **Used in events:** All events include `turn` to correlate with the conversation flow

### Event Timing

We use `time.perf_counter()` for high-resolution timing:
- `ModelResponseEvent.duration_ms` — measures API call time
- `ToolResultEvent.duration_ms` — measures individual tool execution time

### Error Handling Strategy

1. **API errors:** Raise `KernelError` to halt execution
2. **Tool errors:** Capture in `ToolResult` with `is_error=True`, continue execution
3. **Gather exceptions:** Use `return_exceptions=True` to prevent one tool failure from crashing the entire turn

---

## Verification

After implementing these changes, verify:

1. **Import check:**
   ```bash
   python -c "from structured_agents.kernel import AgentKernel; print('OK')"
   ```

2. **Type check:**
   ```bash
   mypy src/structured_agents/kernel.py --strict
   ```

3. **Basic instantiation:**
   ```bash
   python -c "
   from structured_agents.kernel import AgentKernel
   from structured_agents.models.adapter import ModelAdapter
   from structured_agents.client.protocol import LLMClient
   from dataclasses import dataclass
   
   @dataclass
   class MockClient:
       model: str = 'test'
       async def chat_completion(self, **kwargs): pass
       async def close(self): pass
   
   @dataclass 
   class MockAdapter:
       format_messages = None
       format_tools = None
       grammar_builder = None
       grammar_config = None
       response_parser = None
   
   kernel = AgentKernel(client=MockClient(), adapter=MockAdapter())
   print('AgentKernel instantiated successfully')
   "
   ```

4. **Event emission (if observer tests exist):**
   ```bash
   pytest tests/ -k "kernel" -v
   ```

---

## Summary

This step implements:
- BUG-3 fix: Pass `ToolCall` as context
- Tool map caching for performance
- All 7 event types with proper timing
- `tool_choice` handling for no-tools case
- Message history trimming
- `format_messages` signature fix
- `grammar_config` passing
- Error handling with proper exceptions
- Type fixes for async operations

**Next Step:** Step 6 — Continue the refactoring journey.
