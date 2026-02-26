# Developer Guide: Step 3 — Models Layer

**Refactoring to v0.3.1** | **Goal**: Fix `ModelAdapter` and response parsers

---

## Overview

This step refactors the models layer — the adapter that bridges the kernel to specific model families, and the response parsers. We fix type safety issues, remove dead code, and correct bugs in tool call ID handling.

---

## Task 1: Fix `ModelAdapter` in `models/adapter.py`

### Why These Changes?

1. **Drop `frozen=True`**: The `frozen=True` + `object.__setattr__` hack is a code smell. Since we want to set defaults in `__post_init__`, just make it NOT frozen. The adapter is a configuration object, not a value type.

2. **Fix `response_parser` type**: Change `Any` → `ResponseParser` for proper type safety.

3. **Fix `grammar_builder` signature**: 
   - Second argument `Any` → `DecodingConstraint | None`
   - Make it optional (default `None`) instead of required
   - Add separate `grammar_config: DecodingConstraint | None = None` field

4. **Fix `_default_format_messages`**:
   - Replace `str(tools)` with `json.dumps` for proper serialization
   - **CRITICAL**: Remove the tool injection entirely. The `tools` parameter is misleading — tools are sent separately via the API's `tools` parameter, not appended to messages. The message formatter should ONLY format messages.

5. **Fix `format_messages` signature**: Remove the `tools` parameter since it's not needed.

### Complete Fixed File

```python
"""Model adapter for specific model families."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from structured_agents.grammar.config import DecodingConstraint
from structured_agents.models.parsers import ResponseParser
from structured_agents.types import Message, ToolSchema


@dataclass
class ModelAdapter:
    """Adapts the kernel's generic tool-call loop to a specific model family."""

    name: str
    response_parser: ResponseParser
    grammar_builder: Callable[[list[ToolSchema], DecodingConstraint | None], dict[str, Any] | None] | None = None
    grammar_config: DecodingConstraint | None = None
    format_messages: Callable[[list[Message]], list[dict[str, Any]]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict[str, Any]]] | None = None

    def __post_init__(self) -> None:
        if self.format_messages is None:
            self.format_messages = self._default_format_messages
        if self.format_tools is None:
            self.format_tools = self._default_format_tools

    @staticmethod
    def _default_format_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to OpenAI format. Tools are sent separately via the API."""
        return [msg.to_openai_format() for msg in messages]

    @staticmethod
    def _default_format_tools(tool_schemas: list[ToolSchema]) -> list[dict[str, Any]]:
        """Convert tool schemas to OpenAI tools format."""
        return [ts.to_openai_format() for ts in tool_schemas]
```

---

## Task 2: Fix BUG-2 in `models/parsers.py` — Preserve API-Provided Tool Call IDs

### Why This Change?

The model API returns tool calls with specific IDs. We **must** use those IDs in our `ToolCall` objects, or the API loses the correlation between the tool call and the tool result. Previously, `ToolCall.create()` generated a new random ID, breaking the chain.

Also add proper error handling for JSON parsing failures.

### Complete Fixed File

```python
"""Response parser implementations."""
from __future__ import annotations

import json
import re
from typing import Any, Protocol

from structured_agents.types import ToolCall


class ResponseParser(Protocol):
    def parse(self, content: str | None, tool_calls: list[dict[str, Any]] | None) -> tuple[str | None, list[ToolCall]]: ...


class QwenResponseParser:
    def parse(self, content: str | None, tool_calls: list[dict[str, Any]] | None) -> tuple[str | None, list[ToolCall]]:
        if tool_calls:
            parsed = []
            for tc in tool_calls:
                if isinstance(tc, dict) and "function" in tc:
                    func = tc["function"]
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    # Preserve the API-provided ID
                    tool_call_id = tc.get("id", "")
                    parsed.append(ToolCall(id=tool_call_id, name=func["name"], arguments=args))
            return None, parsed

        if content:
            # Fix variable shadowing - use different variable name
            parsed_xml_calls = self._parse_xml_tool_calls(content)
            if parsed_xml_calls:
                return None, parsed_xml_calls

        return content, []

    def _parse_xml_tool_calls(self, content: str) -> list[ToolCall]:
        pattern = r"<tool_call>(.*?)</tool_call>"
        tool_calls = []
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            inner = match.strip()
            try:
                data = json.loads(inner)
                name = data.get("name", "")
                args = data.get("arguments", {})
                if name:
                    tool_calls.append(ToolCall.create(name, args))
            except json.JSONDecodeError:
                pass

        return tool_calls
```

### Summary of Changes in parsers.py

| Issue | Fix |
|-------|-----|
| BUG-2: New ID generated | Use `ToolCall(id=tc["id"], ...)` to preserve API ID |
| No JSON error handling | Wrap `json.loads` in try/except, default to `{}` |
| Variable shadowing | Rename `tool_calls` → `parsed_xml_calls` |

---

## Task 3: Remove `FunctionGemmaResponseParser`

### Why?

It's dead code — it just delegates to `QwenResponseParser()` with no added behavior. Remove it to reduce confusion.

---

## Task 4: Update `models/__init__.py`

Remove `FunctionGemmaResponseParser` from exports.

### Complete Fixed File

```python
"""Models package for model-specific adapters."""

from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import ResponseParser, QwenResponseParser

__all__ = ["ModelAdapter", "ResponseParser", "QwenResponseParser"]
```

---

## Verification

After making all changes, verify with:

```bash
# Type check
mypy models/

# Run tests
pytest tests/ -v
```

Expected: No type errors, all tests pass.

---

## Dependency Note

The `format_messages` signature change (removing the `tools` parameter) will require a corresponding change in `kernel.py` (Step 5). The kernel currently passes tools to the message formatter — this call site will need to be updated to stop passing tools to the formatter.

---

## Summary of Changes

| File | Changes |
|------|---------|
| `models/adapter.py` | Drop frozen, fix types, fix format_messages signature, remove tool injection |
| `models/parsers.py` | Fix BUG-2 (preserve IDs), add JSON error handling, fix variable shadowing, remove FunctionGemmaResponseParser |
| `models/__init__.py` | Remove FunctionGemmaResponseParser export |
