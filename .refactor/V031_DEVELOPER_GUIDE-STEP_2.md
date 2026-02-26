You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_2.md
This is Step 2 of 7: "Client Layer — Fix bugs, consolidate, clean up"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
The structured-agents library is being refactored to v0.3.1. This step fixes the client layer — the OpenAI-compatible HTTP client that talks to vLLM.
## Current state of files:
### client/openai.py:
```python
"""OpenAI-compatible LLM client."""
from __future__ import annotations
from typing import Any
from openai import AsyncOpenAI
from structured_agents.client.protocol import CompletionResponse, LLMClient
from structured_agents.types import TokenUsage
class OpenAICompatibleClient:
    """OpenAI-compatible client for vLLM and similar backends."""
    def __init__(self, base_url: str, api_key: str = "EMPTY", model: str = "default", timeout: float = 120.0):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    async def chat_completion(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto", max_tokens: int = 4096, temperature: float = 0.1,
        extra_body: dict[str, Any] | None = None, model: str | None = None,
    ) -> CompletionResponse:
        response = await self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body=extra_body,
        )
        choice = response.choices[0]
        message = choice.message
        content = message.content
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in message.tool_calls
            ]
        usage = None
        if response.usage:
            usage = TokenUsage(prompt_tokens=response.usage.prompt_tokens, completion_tokens=response.usage.completion_tokens, total_tokens=response.usage.total_tokens)
        return CompletionResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason,
            raw_response=response.to_dict(),  # BUG-1: should be model_dump()
        )
    async def close(self) -> None:
        await self._client.close()
def build_client(config: dict[str, Any]) -> LLMClient:
    return OpenAICompatibleClient(
        base_url=config.get("base_url", "http://localhost:8000/v1"),
        api_key=config.get("api_key", "EMPTY"),
        model=config.get("model", "default"),
        timeout=config.get("timeout", 120.0),
    )
```
### client/factory.py (DUPLICATE — to be deleted):
```python
"""Client factory helpers."""
from __future__ import annotations
from typing import Any
from structured_agents.client.openai import OpenAICompatibleClient
def build_client(config: dict[str, Any]) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=config.get("base_url", "http://localhost:8000/v1"),
        api_key=config.get("api_key", "EMPTY"),
        model=config.get("model", "default"),
        timeout=config.get("timeout", 120.0),
    )
```
### client/protocol.py:
```python
"""LLM client protocol definition."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
from structured_agents.types import TokenUsage
@dataclass
class CompletionResponse:
    content: str | None
    tool_calls: list[dict[str, Any]] | None
    usage: TokenUsage | None
    finish_reason: str | None
    raw_response: dict[str, Any]
class LLMClient(Protocol):
    async def chat_completion(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto", max_tokens: int = 4096, temperature: float = 0.1,
        extra_body: dict[str, Any] | None = None, model: str | None = None,
    ) -> CompletionResponse: ...
    async def close(self) -> None: ...
```
### client/__init__.py:
```python
"""Client package for LLM connections."""
from structured_agents.client.protocol import CompletionResponse, LLMClient
from structured_agents.client.openai import OpenAICompatibleClient, build_client
__all__ = ["CompletionResponse", "LLMClient", "OpenAICompatibleClient", "build_client"]
```
## What the guide should instruct the developer to do:
### 1. Fix BUG-1 in openai.py:
- Change `response.to_dict()` to `response.model_dump()` on line 82
- The OpenAI SDK uses Pydantic v2. The `.to_dict()` method doesn't exist — this crashes every LLM call with `AttributeError`.
### 2. Fix tools=None issue in openai.py:
- When `tools` is `None`, don't pass it to the SDK at all. Some SDK versions don't handle `tools=None` gracefully.
- Build kwargs dict conditionally:
```python
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
### 3. Delete client/factory.py entirely:
- It's a duplicate of the `build_client` function already in `client/openai.py`.
- The return type annotation is wrong (returns `OpenAICompatibleClient` instead of `LLMClient`).
- Delete the file.
### 4. Update client/__init__.py:
- Remove the import from factory.py (since it's deleted).
- The `build_client` is already imported from `openai.py`.
### 5. Fix imports in agent.py:
- Change `from structured_agents.client.factory import build_client` to `from structured_agents.client import build_client`
- (Just note this for the developer — the full agent.py rewrite is in Step 6)
### 6. Fix return type annotation on build_client in openai.py:
- Change return type from `LLMClient` to `OpenAICompatibleClient` — it's more specific and correct. The protocol conformance is checked structurally by type checkers.
## IMPORTANT NOTES FOR THE GUIDE:
- Show the COMPLETE final version of each modified file.
- Explain WHY each change is made.
- Include a "Verification" section.
- Note that agent.py import fix is a quick one-liner that should be done now even though agent.py is fully rewritten in Step 6.
Return a brief (2-3 sentence) confirmation when done.