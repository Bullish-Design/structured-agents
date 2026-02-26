You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_4.md
This is Step 4 of 7: "Tools Layer — Fix GrailTool, implement discover_tools, fix protocol"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
The structured-agents library uses Grail (.pym scripts) as its tool execution backend. Grail is a sandboxed Python interpreter — scripts declare `Input()` values and `@external` functions. The structured-agents library needs to:
1. Load .pym scripts via `grail.load()`
2. Build OpenAI tool schemas from the script's `Input()` declarations (these are what the LLM fills in)
3. Execute scripts via `script.run(inputs=..., limits=...)`
### Key Grail API (from vendored docs):
```python
# Loading
from grail import load, Limits
script = load("path/to/script.pym")  # Returns GrailScript
# GrailScript attributes:
script.name        # str - script name (filename without .pym)
script.inputs      # dict[str, InputSpec] - declared Input() values
script.externals   # dict[str, ExternalSpec] - declared @external functions
# InputSpec has:
#   .type_annotation: str (e.g. "int", "float", "str")
#   .required: bool
#   .default: Any | None
# ExternalSpec has:
#   .parameters: list[ParamSpec]  (each has .name, .type_annotation)
#   .return_type: str
#   .is_async: bool
# Execution (async):
result = await script.run(
    inputs={"x": 1, "y": 2},      # Values for Input() declarations
    externals={...},                # Implementations for @external functions
    limits=Limits.default(),        # Optional resource limits
)
# grail.Limits:
Limits.default()     # 16MB, 2s, 200 recursion
Limits.strict()      # 8MB, 500ms, 120 recursion
Limits(max_memory="32mb", max_duration="1.5s")
```
## Current state of files:
### tools/protocol.py:
```python
"""Tool protocol definition."""
from __future__ import annotations
from typing import Protocol, Any
from structured_agents.types import ToolSchema, ToolResult
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...
    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult: ...
```
### tools/grail.py:
```python
"""Grail tool implementation."""
from __future__ import annotations
import json
from typing import Any
from structured_agents.types import ToolSchema, ToolResult
class GrailTool:
    def __init__(self, script: Any, limits: Any = None):
        self._script = script
        self._limits = limits
        self._schema = ToolSchema(
            name=script.name,
            description=f"Tool: {script.name}",
            parameters={"type": "object", "properties": {}},
        )
    @property
    def schema(self) -> ToolSchema:
        return self._schema
    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult:
        try:
            result = await self._script.run(inputs=arguments, limits=self._limits)
            output = json.dumps(result) if not isinstance(result, str) else result
            return ToolResult(
                call_id=context.call_id if context else "unknown",
                name=self._script.name,
                output=output,
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                call_id=context.call_id if context else "unknown",
                name=self._script.name,
                output=str(e),
                is_error=True,
            )
def discover_tools(agents_dir: str):
    """Discover .pym tools in a directory."""
    # TODO: implement with grail.load()
    return []
```
### tools/__init__.py:
```python
"""Tools package."""
from structured_agents.tools.protocol import Tool
from structured_agents.tools.grail import GrailTool, discover_tools
__all__ = ["Tool", "GrailTool", "discover_tools"]
```
## What the guide should instruct the developer to do:
### 1. Fix Tool protocol — type the `context` parameter:
Instead of `context: Any`, the context should be a `ToolCall` object (the same `ToolCall` from types.py). This is what the kernel passes as context (we'll fix the kernel in Step 5 to actually pass it). The tool needs the `call_id` from it.
```python
from structured_agents.types import ToolCall, ToolSchema, ToolResult
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...
    async def execute(self, arguments: dict[str, Any], context: ToolCall | None) -> ToolResult: ...
```
### 2. Fix GrailTool — proper typing and schema generation:
The current GrailTool:
- Uses `Any` for script and limits types
- Hardcodes empty parameters and generic description
- Never builds a real schema from the script's inputs
The fixed version should:
- Import and use `grail.GrailScript` and `grail.Limits` as proper types (import grail at module level since it's a required dependency per AGENTS.md)
- Build the parameter schema from `script.inputs` — each Input() becomes a property in the JSON Schema
- Use the script's name as both name and description (or construct a better description)
- Map grail type annotations to JSON Schema types
Build parameters from script.inputs like this:
```python
def _build_parameters(script: grail.GrailScript) -> dict[str, Any]:
    """Build JSON Schema parameters from script Input() declarations."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    
    for name, spec in script.inputs.items():
        prop: dict[str, Any] = {}
        # Map Python type annotations to JSON Schema types
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
        }
        type_str = spec.type_annotation
        prop["type"] = type_map.get(type_str, "string")
        properties[name] = prop
        if spec.required:
            required.append(name)
    
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema
```
### 3. Fix GrailTool.execute — use ToolCall context properly:
Change `context: Any` to `context: ToolCall | None` and use `context.id` (not `context.call_id` — `ToolCall` has `id` field, not `call_id`).
```python
async def execute(self, arguments: dict[str, Any], context: ToolCall | None) -> ToolResult:
    call_id = context.id if context else "unknown"
    try:
        result = await self._script.run(inputs=arguments, limits=self._limits)
        output = json.dumps(result) if not isinstance(result, str) else result
        return ToolResult(call_id=call_id, name=self._script.name, output=output, is_error=False)
    except Exception as e:
        return ToolResult(call_id=call_id, name=self._script.name, output=str(e), is_error=True)
```
### 4. Implement discover_tools:
```python
def discover_tools(agents_dir: str, limits: grail.Limits | None = None) -> list[GrailTool]:
    """Discover and load .pym tools from a directory."""
    import logging
    logger = logging.getLogger(__name__)
    
    tools: list[GrailTool] = []
    agents_path = Path(agents_dir)
    
    if not agents_path.exists():
        logger.warning("Agents directory does not exist: %s", agents_dir)
        return tools
    
    for pym_file in sorted(agents_path.glob("*.pym")):
        try:
            script = grail.load(str(pym_file), grail_dir=None)
            tools.append(GrailTool(script, limits=limits))
            logger.debug("Loaded tool: %s from %s", script.name, pym_file)
        except Exception as e:
            logger.warning("Failed to load %s: %s", pym_file, e)
            continue
    
    return tools
```
Note: We pass `grail_dir=None` to skip artifact generation — we don't need .grail/ directories cluttering the agent's workspace.
### 5. Update tools/__init__.py:
Keep exports the same but ensure `discover_tools` return type is explicit.
## IMPORTANT NOTES:
- Show COMPLETE final versions of each file.
- After Step 1 cleaned up ToolSchema (removed backend, script_path, context_providers), the schema here uses the cleaned version.
- Note that `grail` is a required dependency (per AGENTS.md), so import it at module level. No try/except fallback needed.
- Explain the relationship between grail's Input() declarations and the tool's parameter schema for the LLM.
Return a brief (2-3 sentence) confirmation when done.