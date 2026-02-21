"""LLM client implementations."""

from structured_agents.client.openai_compat import OpenAICompatibleClient
from structured_agents.client.protocol import CompletionResponse, LLMClient

__all__ = [
    "LLMClient",
    "CompletionResponse",
    "OpenAICompatibleClient",
]
