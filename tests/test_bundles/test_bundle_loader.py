"""Tests for bundle loading and schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from structured_agents.bundles.loader import AgentBundle, load_bundle
from structured_agents.bundles.schema import (
    BundleManifest,
    InitialContext,
    ToolReference,
)
from structured_agents.exceptions import BundleError
from structured_agents.types import Message, ToolSchema

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_bundle"


class TestBundleLoader:
    def test_load_bundle_success(self) -> None:
        bundle = load_bundle(FIXTURE_DIR)
        assert isinstance(bundle, AgentBundle)
        assert bundle.name == "sample_bundle"
        assert bundle.max_turns == 3
        assert bundle.termination_tool == "submit_result"

    def test_load_bundle_missing(self) -> None:
        with pytest.raises(BundleError):
            load_bundle(Path(__file__).parent / "missing")

    def test_unknown_registry_raises(self, tmp_path: Path) -> None:
        bundle_yaml = tmp_path / "bundle.yaml"
        bundle_yaml.write_text(
            """
name: "bad_bundle"
initial_context:
  system_prompt: "Test"
tools:
  - name: "missing"
    registry: "unknown"
registries:
  - "unknown"
""".lstrip()
        )

        with pytest.raises(BundleError):
            load_bundle(tmp_path)

    def test_unknown_tool_raises(self, tmp_path: Path) -> None:
        (tmp_path / "tools").mkdir()
        bundle_yaml = tmp_path / "bundle.yaml"
        bundle_yaml.write_text(
            """
name: "tool_bundle"
initial_context:
  system_prompt: "Test"
tools:
  - name: "missing_tool"
    registry: "grail"
registries:
  - "grail"
""".lstrip()
        )

        bundle = load_bundle(tmp_path)
        with pytest.raises(BundleError):
            _ = bundle.tool_schemas

    def test_tool_schemas(self) -> None:
        bundle = load_bundle(FIXTURE_DIR)
        schemas = bundle.tool_schemas
        assert len(schemas) == 2
        assert schemas[0].name == "echo"
        assert schemas[1].name == "submit_result"

        echo_schema = schemas[0]
        assert isinstance(echo_schema, ToolSchema)
        assert echo_schema.script_path is not None
        assert echo_schema.script_path.name == "echo.pym"

    def test_build_initial_messages(self) -> None:
        bundle = load_bundle(FIXTURE_DIR)
        messages = bundle.build_initial_messages({"input": "hello"})
        assert len(messages) == 2
        assert messages[0] == Message(role="system", content="You are a test agent.")
        assert messages[1] == Message(role="user", content="Handle: hello")

    def test_get_system_prompt(self) -> None:
        bundle = load_bundle(FIXTURE_DIR)
        prompt = bundle.get_system_prompt({"input": "ignored"})
        assert prompt == "You are a test agent."


class TestBundleManifest:
    def test_duplicate_tool_names(self) -> None:
        with pytest.raises(ValueError):
            BundleManifest(
                name="dup",
                initial_context=InitialContext(system_prompt="Test"),
                tools=[
                    ToolReference(name="a"),
                    ToolReference(name="a"),
                ],
            )
