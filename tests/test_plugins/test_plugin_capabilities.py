"""Tests for plugin capability flags."""

from structured_agents.plugins import FunctionGemmaPlugin, QwenPlugin


def test_function_gemma_capabilities() -> None:
    plugin = FunctionGemmaPlugin()
    assert plugin.supports_ebnf is True
    assert plugin.supports_structural_tags is True
    assert plugin.supports_json_schema is True


def test_qwen_capabilities() -> None:
    plugin = QwenPlugin()
    assert plugin.supports_ebnf is False
    assert plugin.supports_structural_tags is False
    assert plugin.supports_json_schema is False
