"""Tests for bundle grammar settings."""

from pathlib import Path

from structured_agents.bundles.loader import load_bundle


def test_bundle_grammar_settings_to_config(tmp_path: Path) -> None:
    bundle_yaml = tmp_path / "bundle.yaml"
    bundle_yaml.write_text(
        """
name: "grammar_bundle"
model:
  plugin: "function_gemma"
  grammar:
    mode: "structural_tag"
    allow_parallel_calls: false
    args_format: "json"
initial_context:
  system_prompt: "Test"
tools: []
""".lstrip()
    )

    bundle = load_bundle(tmp_path)
    grammar_config = bundle.get_grammar_config()

    assert grammar_config.mode == "structural_tag"
    assert grammar_config.allow_parallel_calls is False
    assert grammar_config.args_format == "json"
