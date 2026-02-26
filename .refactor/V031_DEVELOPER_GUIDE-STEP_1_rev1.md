# Developer Guide: Step 1 — Types & Foundation

**Refactoring Version:** v0.3.1  
**Step:** 1 of 7  
**Objective:** Clean up the foundational `types.py` and `exceptions.py` files to establish a solid base for all subsequent refactoring steps.

---

## Overview

This step removes dead code, fixes inconsistencies, and establishes a clean foundation. We delete pre-v0.3.0 remnants and fix minor issues that would cause problems later.

---

## 1. Update `src/structured_agents/types.py`

### Changes Summary

| Change | Reason |
|--------|--------|
| Remove `KernelConfig` class | Plain class (not dataclass), never used. `AgentKernel` has its own fields. |
| Remove `ToolResult.output_str` | Identity property returning `self.output`. No callers exist. |
| Fix `ToolCall.create()` ID length | `hex[:8]` gives 32 bits entropy. Change to `hex[:12]` for 48 bits (safer collision resistance). |
| Add `slots=True` to `RunResult` | Only frozen dataclass missing `slots`. Inconsistent with all others. |
| Move `json` import to module level | Lazy import inside a property is unnecessary. |
| Remove `ToolSchema.backend`, `script_path`, `context_providers` | Pre-v0.3.0 leftovers. `ToolSchema` should only contain OpenAI API fields: name, description, parameters. Script path belongs on `GrailTool`, not schema. |

### Complete Final Version

```python
"""Core data types for structured-agents."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Message:
    """A conversation message in the agent loop."""

    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI API message format."""
        msg: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments_json,
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A parsed tool call from model output."""

    id: str
    name: str
    arguments: dict[str, Any]

    @property
    def arguments_json(self) -> str:
        return json.dumps(self.arguments)

    @classmethod
    def create(cls, name: str, arguments: dict[str, Any]) -> "ToolCall":
        return cls(
            id=f"call_{uuid.uuid4().hex[:12]}",
            name=name,
            arguments=arguments,
        )


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result of executing a tool."""

    call_id: str
    name: str
    output: str
    is_error: bool = False

    def to_message(self) -> Message:
        return Message(
            role="tool",
            content=self.output,
            tool_call_id=self.call_id,
            name=self.name,
        )


@dataclass(frozen=True, slots=True)
class ToolSchema:
    """Schema for a tool exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class StepResult:
    response_message: Message
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    usage: TokenUsage | None = None


@dataclass(frozen=True, slots=True)
class RunResult:
    final_message: Message
    history: list[Message]
    turn_count: int
    termination_reason: str
    final_tool_result: ToolResult | None = None
    total_usage: TokenUsage | None = None
```

---

## 2. Update `src/structured_agents/exceptions.py`

### Changes Summary

| Change | Reason |
|--------|--------|
| Remove `PluginError` | Pre-v0.3.0 concept. Plugins don't exist anymore. |
| Remove `BackendError` | Pre-v0.3.0 concept. Backends don't exist anymore. |
| Keep `StructuredAgentsError` | Base exception class. Required. |
| Keep `KernelError` | Used in Step 5 for kernel error handling. |
| Keep `ToolExecutionError` | Used in Step 5 for tool execution errors. |
| Keep `BundleError` | Used in Step 6 when fixing `load_manifest`. |
| Add `AdapterError` | New exception for model adapter parsing/formatting errors. Used in Step 3. |

### Complete Final Version

```python
"""Exception hierarchy for structured-agents."""
from __future__ import annotations


class StructuredAgentsError(Exception):
    """Base exception for all structured-agents errors."""


class KernelError(StructuredAgentsError):
    """Error in the agent kernel (execution, scheduling, etc.)."""

    def __init__(
        self, message: str, turn: int | None = None, phase: str | None = None
    ) -> None:
        super().__init__(message)
        self.turn = turn
        self.phase = phase


class ToolExecutionError(StructuredAgentsError):
    """Error executing a tool."""

    def __init__(
        self, message: str, tool_name: str, call_id: str, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.call_id = call_id
        self.code = code


class AdapterError(StructuredAgentsError):
    """Error in model adapter (parsing, formatting, etc.)."""


class BundleError(StructuredAgentsError):
    """Error loading or validating a bundle."""
```

---

## 3. Update `src/structured_agents/__init__.py`

### Changes Summary

| Change | Reason |
|--------|--------|
| Remove `KernelConfig` from imports | Class was removed from types.py. |
| Add exceptions to exports | Make exceptions available at package level. |

### Complete Final Version

```python
"""structured-agents - Structured agent execution with grammar-constrained decoding."""

from structured_agents.types import (
    Message,
    RunResult,
    StepResult,
    TokenUsage,
    ToolCall,
    ToolResult,
    ToolSchema,
)
from structured_agents.exceptions import (
    AdapterError,
    BundleError,
    KernelError,
    StructuredAgentsError,
    ToolExecutionError,
)

__all__ = [
    "Message",
    "RunResult",
    "StepResult",
    "TokenUsage",
    "ToolCall",
    "ToolResult",
    "ToolSchema",
    "AdapterError",
    "BundleError",
    "KernelError",
    "StructuredAgentsError",
    "ToolExecutionError",
]
```

---

## Verification

Run the following commands to verify the changes work correctly:

```bash
# 1. Check Python syntax and imports
python -c "from structured_agents import *; print('Imports OK')"

# 2. Run type checking
mypy src/structured_agents/types.py src/structured_agents/exceptions.py

# 3. Run linting
ruff check src/structured_agents/types.py src/structured_agents/exceptions.py
```

Expected output:
- Imports should succeed without errors
- mypy should report no errors
- ruff should report no violations

---

## Summary

This step establishes a clean foundation by:
- Removing dead code (`KernelConfig`, `output_str`, unused ToolSchema fields)
- Removing deprecated concepts (`PluginError`, `BackendError`)
- Adding new exceptions for v0.3.1 (`AdapterError`)
- Fixing inconsistencies (slots, ID entropy, import location)

All changes are backward-compatible since the removed items were either unused or deprecated.
