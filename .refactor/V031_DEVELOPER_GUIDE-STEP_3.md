You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_3.md
This is Step 3 of 7: "Models Layer — Fix ModelAdapter and parsers"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
The structured-agents library is being refactored to v0.3.1. This step fixes the models layer — the adapter that bridges the kernel to specific model families, and the response parsers.
## Current state of files:
### models/adapter.py:
```python
"""Model adapter for specific model families."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from structured_agents.types import Message, ToolSchema
@dataclass(frozen=True)
class ModelAdapter:
    """Adapts the kernel's generic tool-call loop to a specific model family."""
    name: str
    grammar_builder: Callable[[list[ToolSchema], Any], dict[str, Any] | None]
    response_parser: Any  # ResponseParser
    format_messages: Callable[[list[Message], list[dict]], list[dict]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict]] | None = None
    def __post_init__(self):
        if self.format_messages is None:
            object.__setattr__(self, "format_messages", self._default_format_messages)
        if self.format_tools is None:
            object.__setattr__(self, "format_tools", self._default_format_tools)
    @staticmethod
    def _default_format_messages(messages: list[Message], tools: list[dict]) -> list[dict]:
        result = []
        for msg in messages:
            msg_dict = msg.to_openai_format()
            result.append(msg_dict)
        if tools:
            result.append({"role": "system", "content": "Available tools: " + str(tools)})
        return result
    @staticmethod
    def _default_format_tools(tool_schemas: list[ToolSchema]) -> list[dict]:
        return [ts.to_openai_format() for ts in tool_schemas]
```
### models/parsers.py:
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
                    args = json.loads(func.get("arguments", "{}"))
                    parsed.append(ToolCall.create(func["name"], args))  # BUG-2: generates new ID!
            return None, parsed
        if content:
            tool_calls = self._parse_xml_tool_calls(content)  # variable shadowing!
            if tool_calls:
                return None, tool_calls
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
class FunctionGemmaResponseParser:
    def parse(self, content: str | None, tool_calls: list[dict[str, Any]] | None) -> tuple[str | None, list[ToolCall]]:
        return QwenResponseParser().parse(content, tool_calls)
```
### models/__init__.py:
```python
"""Models package for model-specific adapters."""
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import ResponseParser, QwenResponseParser, FunctionGemmaResponseParser
__all__ = ["ModelAdapter", "ResponseParser", "QwenResponseParser", "FunctionGemmaResponseParser"]
```
## What the guide should instruct the developer to do:
### 1. Fix ModelAdapter — drop frozen, fix __post_init__:
The `frozen=True` + `object.__setattr__` hack is a code smell. Since we want to set defaults in `__post_init__`, just make it NOT frozen. The adapter is a configuration object, not a value type.
Also fix these issues:
- Type `response_parser: Any` → `response_parser: ResponseParser`
- Type `grammar_builder` second arg `Any` → `DecodingConstraint | None`
- `grammar_builder` should be optional (default `None`), not required
- Add `grammar_config: DecodingConstraint | None = None` field
- Fix `_default_format_messages` — replace `str(tools)` with `json.dumps` for proper serialization
- The `_default_format_messages` method receives `tools: list[dict]` but this is misleading. It should NOT append tool info to messages — the tools are sent separately via the API's `tools` parameter. Remove the tool injection from the message formatter entirely. The message formatter should ONLY format messages.
The CLEAN version:
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
### 2. Fix BUG-2 in parsers.py — preserve API-provided tool call IDs:
- In `QwenResponseParser.parse()`, change `ToolCall.create(func["name"], args)` to `ToolCall(id=tc["id"], name=func["name"], arguments=args)` to preserve the API-provided ID.
- The model returns a tool call with an ID. We must use THAT ID in the tool result, or the API loses the correlation.
- Also add `json.loads` error handling (wrap in try/except JSONDecodeError, default to empty dict on failure).
### 3. Fix variable shadowing in parsers.py:
- Change `tool_calls = self._parse_xml_tool_calls(content)` to `parsed_xml_calls = self._parse_xml_tool_calls(content)` to avoid shadowing the `tool_calls` parameter.
### 4. Remove FunctionGemmaResponseParser:
- It's dead code — just delegates to `QwenResponseParser()` with no added behavior.
- Remove it entirely.
### 5. Update models/__init__.py:
- Remove `FunctionGemmaResponseParser` from exports.
- Keep `ResponseParser`, `QwenResponseParser`, `ModelAdapter`.
## IMPORTANT NOTES:
- Show COMPLETE final versions of each file.
- Explain WHY each change is made.
- Include a "Verification" section.
- Note: The format_messages signature change (removing the `tools` parameter) will require a corresponding change in kernel.py (Step 5). Just note this dependency.
Return a brief (2-3 sentence) confirmation when done.