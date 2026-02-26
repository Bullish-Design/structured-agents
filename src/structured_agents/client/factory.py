"""Client factory helpers."""

from __future__ import annotations

from typing import Any

from structured_agents.client.openai import OpenAICompatibleClient


def build_client(config: dict[str, Any]) -> OpenAICompatibleClient:
    """Build an OpenAI-compatible client from config dict."""
    return OpenAICompatibleClient(
        base_url=config.get("base_url", "http://localhost:8000/v1"),
        api_key=config.get("api_key", "EMPTY"),
        model=config.get("model", "default"),
        timeout=config.get("timeout", 120.0),
    )
