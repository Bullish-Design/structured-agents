You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_1.md
This is Step 1 of 7: "Types & Foundation — Clean the type layer"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
The structured-agents library is being refactored to v0.3.1. This step cleans up the foundational types.py and exceptions.py files to establish a clean base for all other steps.
## Current state of types.py (the file the developer will be editing):
```python
"""Core data types for structured-agents."""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
class KernelConfig:
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_choice: str = "auto"
    max_concurrency: int = 1
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
        import json
        return json.dumps(self.arguments)
    @classmethod
    def create(cls, name: str, arguments: dict[str, Any]) -> "ToolCall":
        return cls(
            id=f"call_{uuid.uuid4().hex[:8]}",
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
    @property
    def output_str(self) -> str:
        """Output as string."""
        return self.output
    def to_message(self) -> Message:
        return Message(
            role="tool",
            content=self.output,
            tool_call_id=self.call_id,
            name=self.name,
        )
@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]
    backend: str = "python"
    script_path: Path | None = None
    context_providers: tuple[Path, ...] = ()
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
@dataclass(frozen=True)
class RunResult:
    final_message: Message
    history: list[Message]
    turn_count: int
    termination_reason: str
    final_tool_result: ToolResult | None = None
    total_usage: TokenUsage | None = None
```
## Current state of exceptions.py:
```python
"""Exception hierarchy for structured-agents."""
from __future__ import annotations
class StructuredAgentsError(Exception):
    """Base exception for all structured-agents errors."""
class KernelError(StructuredAgentsError):
    def __init__(self, message: str, turn: int | None = None, phase: str | None = None) -> None:
        super().__init__(message)
        self.turn = turn
        self.phase = phase
class ToolExecutionError(StructuredAgentsError):
    def __init__(self, message: str, tool_name: str, call_id: str, code: str | None = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.call_id = call_id
        self.code = code
class PluginError(StructuredAgentsError):
    """Error in model plugin (parsing, formatting, etc.)."""
class BundleError(StructuredAgentsError):
    """Error loading or validating a bundle."""
class BackendError(StructuredAgentsError):
    """Error in tool backend."""
```
## What the guide should instruct the developer to do:
### 1. types.py changes:
1. **Remove `KernelConfig`** — it's a plain class (not even a dataclass), never used anywhere. `AgentKernel` has its own fields.
2. **Remove `ToolResult.output_str`** — identity property that just returns `self.output`. No callers.
3. **Fix `ToolCall.create()` ID length** — change `hex[:8]` to `hex[:12]` for more entropy (32 bits → 48 bits).
4. **Add `slots=True` to `RunResult`** — it's the only frozen dataclass missing it, inconsistent with all others.
5. **Move `json` import to module level** in `ToolCall.arguments_json` — lazy import inside a property is unnecessary.
6. **Remove `ToolSchema.backend`, `ToolSchema.script_path`, `ToolSchema.context_providers`** — these are pre-v0.3.0 leftovers. `ToolSchema` should only contain what the OpenAI API needs: name, description, parameters. The script path belongs on `GrailTool` itself, not on the schema.
### 2. exceptions.py changes:
1. **Remove `PluginError`** — pre-v0.3.0 concept (plugins don't exist). Replace with `AdapterError` for model adapter issues.
2. **Remove `BackendError`** — pre-v0.3.0 concept (backends don't exist).  
3. **Keep `StructuredAgentsError`** — base class.
4. **Keep `KernelError`** — will be used in Step 5 when we add error handling to the kernel.
5. **Keep `ToolExecutionError`** — will be used in Step 5.
6. **Keep `BundleError`** — will be used in Step 6 when we fix `load_manifest`.
7. **Add `AdapterError`** — for model adapter parsing/formatting errors. Will be used in Step 3.
### 3. __init__.py changes:
Update the top-level `__init__.py` exports to reflect these changes. Remove `KernelConfig` from types import (if it was there). Add exceptions to exports.
## IMPORTANT NOTES FOR THE GUIDE:
- Show the COMPLETE final version of each file, not just diffs. A junior developer needs to see the whole picture.
- Explain WHY each change is made.
- Include a "Verification" section at the end with commands to verify the changes work.
- Use clear section headers.
- Do NOT include any changes to files that belong to other steps.
Return a brief (2-3 sentence) confirmation when done.