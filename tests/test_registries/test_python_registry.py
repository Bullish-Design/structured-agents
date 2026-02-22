"""Tests for Python registry."""

from structured_agents.registries.python import PythonRegistry


def test_register_and_resolve_schema() -> None:
    registry = PythonRegistry()

    def greet(name: str, excited: bool = False) -> str:
        """Greet someone."""
        suffix = "!" if excited else "."
        return f"Hello {name}{suffix}"

    registry.register("greet", greet)

    schema = registry.resolve("greet")
    assert schema is not None
    assert schema.name == "greet"
    assert schema.backend == "python"
    assert schema.parameters["properties"]["name"]["type"] == "string"
    assert schema.parameters["properties"]["excited"]["default"] is False
    assert schema.parameters["required"] == ["name"]
    assert schema.description == "Greet someone."


def test_get_callable() -> None:
    registry = PythonRegistry()

    def echo(message: str) -> str:
        return message

    registry.register("echo", echo)
    assert registry.get_callable("echo") is echo
    assert registry.get_callable("missing") is None
