"""Tests for composite registry."""

from structured_agents.registries.composite import CompositeRegistry
from structured_agents.registries.python import PythonRegistry


def test_list_tools_deduplicates() -> None:
    primary = PythonRegistry()
    secondary = PythonRegistry()

    def tool_a() -> None:
        """Tool A."""
        return None

    def tool_b() -> None:
        """Tool B."""
        return None

    primary.register("tool_a", tool_a)
    primary.register("tool_b", tool_b)
    secondary.register("tool_b", tool_b)

    registry = CompositeRegistry([primary, secondary])
    assert registry.list_tools() == ["tool_a", "tool_b"]


def test_resolve_prefers_first_registry() -> None:
    primary = PythonRegistry()
    secondary = PythonRegistry()

    def tool_b() -> None:
        """Primary B."""
        return None

    def tool_b_alt() -> None:
        """Secondary B."""
        return None

    primary.register("tool_b", tool_b)
    secondary.register("tool_b", tool_b_alt)

    registry = CompositeRegistry([primary, secondary])
    schema = registry.resolve("tool_b")
    assert schema is not None
    assert schema.description == "Primary B."


def test_resolve_all_preserves_order() -> None:
    registry = CompositeRegistry()
    python_registry = PythonRegistry()

    def tool_a() -> None:
        """Tool A."""
        return None

    def tool_c() -> None:
        """Tool C."""
        return None

    python_registry.register("tool_a", tool_a)
    python_registry.register("tool_c", tool_c)
    registry.add(python_registry)

    schemas = registry.resolve_all(["tool_c", "tool_a", "missing"])
    assert [schema.name for schema in schemas] == ["tool_c", "tool_a"]
