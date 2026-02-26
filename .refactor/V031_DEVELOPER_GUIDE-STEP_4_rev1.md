# Developer Guide: Step 4 — Tools Layer

## Fix GrailTool, implement discover_tools, fix protocol

This step completes the Tools layer by fixing type annotations, generating proper tool schemas from Grail's Input() declarations, and implementing tool discovery.

---

## 1. Why This Matters

Grail scripts declare `Input()` values that the LLM must fill in. The tool schema translates these Input() declarations into OpenAI JSON Schema format so the LLM knows what parameters to provide. This is the bridge between Grail's sandbox and the LLM's tool-calling capability.

---

## 2. Fix the Tool Protocol

**File:** `tools/protocol.py`

The protocol currently uses `Any` for context, which loses type safety. The kernel passes a `ToolCall` object (from `types.py`) containing the call ID.

```python
"""Tool protocol definition."""
from __future__ import annotations
from typing import Protocol
from structured_agents.types import ToolCall, ToolSchema, ToolResult


class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...

    async def execute(
        self, arguments: dict[str, object], context: ToolCall | None
    ) -> ToolResult: ...
```

Key changes:
- Import `ToolCall` from types
- Change `context: Any` to `context: ToolCall | None`
- Use `object` instead of `Any` for arguments (stricter)

---

## 3. Fix GrailTool — Proper Typing and Schema Generation

**File:** `tools/grail.py`

The current implementation uses `Any` everywhere and hardcodes empty parameters. We need to:
1. Import grail properly (required dependency per AGENTS.md)
2. Type the script and limits parameters
3. Build parameter schema from `script.inputs` — each Input() becomes a JSON Schema property
4. Use correct context field (`context.id`, not `context.call_id`)

### Complete implementation:

```python
"""Grail tool implementation."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import grail

from structured_agents.types import ToolCall, ToolSchema, ToolResult


logger = logging.getLogger(__name__)


def _build_parameters(script: grail.GrailScript) -> dict[str, Any]:
    """Build JSON Schema parameters from script Input() declarations.

    Each Input() in the Grail script becomes a property in the OpenAI tool schema.
    The LLM uses this schema to know what arguments to provide.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    type_map = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
    }

    for name, spec in script.inputs.items():
        prop: dict[str, Any] = {}

        type_str = spec.type_annotation
        prop["type"] = type_map.get(type_str, "string")

        if spec.default is not None:
            prop["default"] = spec.default

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


class GrailTool:
    """Tool implementation that wraps a Grail script.

    The script's Input() declarations become the tool's parameter schema.
    Execution runs the script in Grail's sandbox with the provided inputs.
    """

    def __init__(
        self, script: grail.GrailScript, limits: grail.Limits | None = None
    ) -> None:
        self._script = script
        self._limits = limits
        self._schema = ToolSchema(
            name=script.name,
            description=f"Grail tool: {script.name}",
            parameters=_build_parameters(script),
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(
        self, arguments: dict[str, object], context: ToolCall | None
    ) -> ToolResult:
        call_id = context.id if context else "unknown"

        try:
            result = await self._script.run(inputs=arguments, limits=self._limits)

            output = json.dumps(result) if not isinstance(result, str) else result

            return ToolResult(
                call_id=call_id,
                name=self._script.name,
                output=output,
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                call_id=call_id,
                name=self._script.name,
                output=str(e),
                is_error=True,
            )


def discover_tools(
    agents_dir: str, limits: grail.Limits | None = None
) -> list[GrailTool]:
    """Discover and load .pym tools from a directory.

    Loads all .pym files in the given directory as Grail tools.
    Uses grail_dir=None to skip artifact generation (.grail/ directories).

    Args:
        agents_dir: Path to directory containing .pym scripts
        limits: Optional resource limits for tool execution

    Returns:
        List of GrailTool instances, one per .pym file found
    """
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

### Key implementation details:

**Schema generation from Input():**
- `script.inputs` is a dict mapping input name to `InputSpec`
- `InputSpec.type_annotation` gives the Python type (e.g., "int", "str")
- Map these to JSON Schema types (`integer`, `string`, etc.)
- Mark required inputs based on `InputSpec.required`

**Context usage:**
- `ToolCall` has an `id` field, not `call_id`
- Pass `context.id` to `ToolResult.call_id`

**Tool discovery:**
- Scan directory for `*.pym` files
- Use `grail_dir=None` to skip artifact generation
- Return list of loaded `GrailTool` instances

---

## 4. Update Package Exports

**File:** `tools/__init__.py`

Ensure the exports match the updated implementation:

```python
"""Tools package."""
from structured_agents.tools.protocol import Tool
from structured_agents.tools.grail import GrailTool, discover_tools

__all__ = ["Tool", "GrailTool", "discover_tools"]
```

---

## 5. Verification

Run type checking:

```bash
cd /home/andrew/Documents/Projects/structured-agents
mypy tools/
```

Ensure no type errors in the tools module.

---

## Summary

| Change | File | Description |
|--------|------|-------------|
| Protocol fix | `tools/protocol.py` | Use `ToolCall \| None` instead of `Any` |
| Schema generation | `tools/grail.py` | Build parameters from `script.inputs` |
| Context field | `tools/grail.py` | Use `context.id` not `context.call_id` |
| Tool discovery | `tools/grail.py` | Implement `discover_tools()` with grail.load() |
| Exports | `tools/__init__.py` | Keep exports, ensure types are correct |
