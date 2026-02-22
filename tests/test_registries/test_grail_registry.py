"""Tests for Grail registry."""

from pathlib import Path

from structured_agents.registries.grail import GrailRegistry, GrailRegistryConfig


def _write_inputs_json(tool_dir: Path) -> None:
    inputs_dir = tool_dir / ".grail" / "sample_tool"
    inputs_dir.mkdir(parents=True)
    (inputs_dir / "inputs.json").write_text(
        """
{
  "_description": "Sample tool",
  "text": {"type": "str", "description": "Text"},
  "count": {"type": "int", "default": 2}
}
""".lstrip()
    )


def test_resolve_from_inputs_json(tmp_path: Path) -> None:
    tool_path = tmp_path / "sample_tool.pym"
    tool_path.write_text("result = {}")
    _write_inputs_json(tmp_path)

    registry = GrailRegistry(GrailRegistryConfig(agents_dir=tmp_path))

    schema = registry.resolve("sample_tool")
    assert schema is not None
    assert schema.name == "sample_tool"
    assert schema.backend == "grail"
    assert schema.description == "Sample tool"
    assert schema.parameters["properties"]["text"]["type"] == "string"
    assert schema.parameters["properties"]["count"]["default"] == 2
    assert schema.parameters["required"] == ["text"]

    assert registry.list_tools() == ["sample_tool"]


def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    registry = GrailRegistry(GrailRegistryConfig(agents_dir=tmp_path / "missing"))
    assert registry.list_tools() == []
    assert registry.resolve("anything") is None
