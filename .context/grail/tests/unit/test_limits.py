"""Test resource limits parsing."""

import pytest

from grail.limits import (
    DEFAULT,
    PERMISSIVE,
    STRICT,
    merge_limits,
    parse_duration_string,
    parse_limits,
    parse_memory_string,
)


def test_parse_memory_string() -> None:
    """Test memory string parsing."""
    assert parse_memory_string("16mb") == 16 * 1024 * 1024
    assert parse_memory_string("1gb") == 1 * 1024 * 1024 * 1024
    assert parse_memory_string("512kb") == 512 * 1024
    assert parse_memory_string("1MB") == 1 * 1024 * 1024


def test_parse_duration_string() -> None:
    """Test duration string parsing."""
    assert parse_duration_string("500ms") == 0.5
    assert parse_duration_string("2s") == 2.0
    assert parse_duration_string("1.5s") == 1.5


def test_invalid_memory_format() -> None:
    """Invalid memory format should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid memory format"):
        parse_memory_string("16")

    with pytest.raises(ValueError):
        parse_memory_string("invalid")


def test_invalid_duration_format() -> None:
    """Invalid duration format should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration_string("2")

    with pytest.raises(ValueError):
        parse_duration_string("invalid")


def test_parse_limits() -> None:
    """Test parsing full limits dict."""
    raw = {
        "max_memory": "16mb",
        "max_duration": "2s",
        "max_recursion": 200,
    }
    parsed = parse_limits(raw)

    assert parsed["max_memory"] == 16 * 1024 * 1024
    assert parsed["max_duration_secs"] == 2.0
    assert parsed["max_recursion_depth"] == 200


def test_merge_limits() -> None:
    """Test merging limits dicts."""
    base = {"max_memory": "16mb", "max_recursion": 200}
    override = {"max_duration": "5s"}

    merged = merge_limits(base, override)

    assert merged["max_memory"] == 16 * 1024 * 1024
    assert merged["max_duration_secs"] == 5.0
    assert merged["max_recursion_depth"] == 200


def test_presets_are_dicts() -> None:
    """Presets should be plain dicts."""
    assert isinstance(STRICT, dict)
    assert isinstance(DEFAULT, dict)
    assert isinstance(PERMISSIVE, dict)

    assert STRICT["max_memory"] == "8mb"
    assert DEFAULT["max_memory"] == "16mb"
    assert PERMISSIVE["max_memory"] == "64mb"
