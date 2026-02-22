"""Tests for client factory helpers."""

from structured_agents.client import build_client
from structured_agents.client.openai_compat import OpenAICompatibleClient
from structured_agents.types import KernelConfig


def test_build_client_returns_openai_client() -> None:
    config = KernelConfig(base_url="http://localhost:8000/v1", model="test")
    client = build_client(config)
    assert isinstance(client, OpenAICompatibleClient)
