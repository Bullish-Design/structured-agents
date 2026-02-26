# Developer Guide: Step 2 — Client Layer Fixes

## Overview

This step fixes bugs, consolidates duplicate code, and cleans up the client layer — the OpenAI-compatible HTTP client that talks to vLLM.

---

## Issue Summary

| Issue | File | Line | Description |
|-------|------|------|-------------|
| BUG-1 | `client/openai.py` | ~82 | Uses `.to_dict()` instead of `.model_dump()` — crashes every LLM call |
| Bug-2 | `client/openai.py` | N/A | Passes `tools=None` to SDK — some versions don't handle this gracefully |
| Duplicate | `client/factory.py` | All | Duplicates `build_client` function already in `openai.py` |
| Wrong import | `agent.py` | N/A | Imports from deleted `factory.py` module |
| Type annotation | `client/openai.py` | ~95 | Return type should be more specific |

---

## 1. Fix BUG-1: Replace `.to_dict()` with `.model_dump()`

**File:** `client/openai.py`

**Why:** The OpenAI SDK uses Pydantic v2. The `.to_dict()` method doesn't exist — this crashes every LLM call with `AttributeError`. Pydantic v2 uses `.model_dump()` instead.

**Change:**

```python
# Before (line 82)
raw_response=response.to_dict(),  # BUG-1: should be model_dump()

# After
raw_response=response.model_dump(),
```

---

## 2. Fix tools=None Issue: Build kwargs Conditionally

**File:** `client/openai.py`

**Why:** When `tools` is `None`, some SDK versions don't handle it gracefully. It's safer to only pass `tools` and `tool_choice` when they are actually provided.

**Change:** Replace the direct `.create()` call with a kwargs-building pattern.

```python
# Before
response = await self._client.chat.completions.create(
    model=model or self.model,
    messages=messages,
    tools=tools,
    tool_choice=tool_choice,
    max_tokens=max_tokens,
    temperature=temperature,
    extra_body=extra_body,
)

# After
kwargs: dict[str, Any] = {
    "model": model or self.model,
    "messages": messages,
    "max_tokens": max_tokens,
    "temperature": temperature,
}
if tools is not None:
    kwargs["tools"] = tools
    kwargs["tool_choice"] = tool_choice
if extra_body is not None:
    kwargs["extra_body"] = extra_body
response = await self._client.chat.completions.create(**kwargs)
```

---

## 3. Delete Duplicate: client/factory.py

**File:** `client/factory.py`

**Why:** This file is a complete duplicate of the `build_client` function already defined in `client/openai.py`. Additionally, its return type annotation is wrong (returns `OpenAICompatibleClient` instead of the protocol `LLMClient`).

**Action:** Delete the entire file.

```bash
rm client/factory.py
```

---

## 4. Update client/__init__.py

**File:** `client/__init__.py`

**Why:** The import from `factory.py` will break now that the file is deleted. The `build_client` is already correctly imported from `openai.py`.

**Before:**

```python
"""Client package for LLM connections."""
from __future__ import annotations

from typing import Any

from structured_agents.client.openai import OpenAICompatibleClient, build_client
from structured_agents.client.protocol import CompletionResponse, LLMClient

__all__ = ["CompletionResponse", "LLMClient", "OpenAICompatibleClient", "build_client"]
```

**After:**

```python
"""Client package for LLM connections."""
from __future__ import annotations

from structured_agents.client.openai import OpenAICompatibleClient, build_client
from structured_agents.client.protocol import CompletionResponse, LLMClient

__all__ = ["CompletionResponse", "LLMClient", "OpenAICompatibleClient", "build_client"]
```

---

## 5. Fix Import in agent.py (Quick One-Liner)

**File:** `agent.py`

**Why:** The agent.py currently imports from `factory.py` which is being deleted. This import must be updated now, even though agent.py will be fully rewritten in Step 6.

**Before:**

```python
from structured_agents.client.factory import build_client
```

**After:**

```python
from structured_agents.client import build_client
```

---

## 6. Fix Return Type Annotation on build_client

**File:** `client/openai.py`

**Why:** The return type annotation `-> LLMClient` is too generic. Since this function returns an `OpenAICompatibleClient` instance, the annotation should reflect that. Protocol conformance is checked structurally by type checkers anyway.

**Before:**

```python
def build_client(config: dict[str, Any]) -> LLMClient:
```

**After:**

```python
def build_client(config: dict[str, Any]) -> OpenAICompatibleClient:
```

---

## Complete Final Versions

### client/openai.py

```python
"""OpenAI-compatible LLM client."""
from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from structured_agents.client.protocol import CompletionResponse, LLMClient
from structured_agents.types import TokenUsage


class OpenAICompatibleClient:
    """OpenAI-compatible client for vLLM and similar backends."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "EMPTY",
        model: str = "default",
        timeout: float = 120.0,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout
        )

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        extra_body: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> CompletionResponse:
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools is not None:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        if extra_body is not None:
            kwargs["extra_body"] = extra_body
        response = await self._client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        message = choice.message
        content = message.content
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        return CompletionResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason,
            raw_response=response.model_dump(),
        )

    async def close(self) -> None:
        await self._client.close()


def build_client(config: dict[str, Any]) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=config.get("base_url", "http://localhost:8000/v1"),
        api_key=config.get("api_key", "EMPTY"),
        model=config.get("model", "default"),
        timeout=config.get("timeout", 120.0),
    )
```

### client/__init__.py

```python
"""Client package for LLM connections."""
from __future__ import annotations

from structured_agents.client.openai import OpenAICompatibleClient, build_client
from structured_agents.client.protocol import CompletionResponse, LLMClient

__all__ = ["CompletionResponse", "LLMClient", "OpenAICompatibleClient", "build_client"]
```

---

## Verification

After making all changes, verify the following:

1. **Syntax check:** Run Python syntax validation on modified files.

```bash
python -m py_compile client/openai.py client/__init__.py
```

2. **Import check:** Ensure all imports work correctly.

```bash
python -c "from structured_agents.client import build_client, OpenAICompatibleClient, LLMClient, CompletionResponse"
```

3. **Type check:** Run mypy to verify type annotations are correct.

```bash
python -m mypy client/ --strict
```

4. **No factory references:** Ensure no references to the deleted factory module remain.

```bash
rg "from.*factory" . --type py
rg "import.*factory" . --type py
```

---

## Summary

| Action | File |
|--------|------|
| Fix BUG-1: `.to_dict()` → `.model_dump()` | `client/openai.py` |
| Fix tools=None: conditional kwargs | `client/openai.py` |
| Fix return type: `LLMClient` → `OpenAICompatibleClient` | `client/openai.py` |
| Delete duplicate | `client/factory.py` (deleted) |
| Remove stale import | `client/__init__.py` |
| Fix import path | `agent.py` |

---

## Next Step

Proceed to **Step 3: Protocol Layer — Refine interfaces and types**.
