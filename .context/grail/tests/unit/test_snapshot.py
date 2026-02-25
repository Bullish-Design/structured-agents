"""Test snapshot pause/resume functionality."""

import pytest

pytest.importorskip("pydantic_monty")

from pathlib import Path
from grail.script import load

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.integration
def test_snapshot_basic_properties():
    """Should expose snapshot properties."""
    script = load(FIXTURES_DIR / "simple.pym", grail_dir=None)

    async def double_impl(n: int) -> int:
        return n * 2

    snapshot = script.start(inputs={"x": 5}, externals={"double": double_impl})

    # Should be paused on first external call
    assert snapshot.function_name == "double"
    assert snapshot.args == () or 5 in snapshot.args or snapshot.kwargs.get("n") == 5
    assert snapshot.is_complete is False
    with pytest.raises(RuntimeError, match="Execution not complete"):
        assert snapshot.value is None


@pytest.mark.integration
def test_snapshot_resume():
    """Should resume execution with return value."""
    script = load(FIXTURES_DIR / "simple.pym", grail_dir=None)

    async def double_impl(n: int) -> int:
        return n * 2

    snapshot = script.start(inputs={"x": 5}, externals={"double": double_impl})

    # Resume with return value
    result_snapshot = snapshot.resume(return_value=10)

    # Should be complete now
    assert result_snapshot.is_complete is True
    assert result_snapshot.value == 10


@pytest.mark.integration
def test_snapshot_serialization():
    """Should serialize and deserialize snapshots."""
    script = load(FIXTURES_DIR / "simple.pym", grail_dir=None)

    async def double_impl(n: int) -> int:
        return n * 2

    snapshot = script.start(inputs={"x": 5}, externals={"double": double_impl})

    # Serialize
    data = snapshot.dump()
    assert isinstance(data, bytes)

    # Deserialize
    from grail.snapshot import Snapshot

    restored = Snapshot.load(data, script.source_map, {"double": double_impl})

    assert restored.function_name == snapshot.function_name
    assert restored.is_complete == snapshot.is_complete


@pytest.mark.integration
def test_snapshot_dump_load_requires_original_context():
    """
    Loading a snapshot requires the same source_map and externals
    that were used when the snapshot was created.
    """
    script = load(FIXTURES_DIR / "simple.pym", grail_dir=None)

    async def double_impl(n: int) -> int:
        return n * 2

    snapshot = script.start(inputs={"x": 5}, externals={"double": double_impl})
    data = snapshot.dump()

    from grail.snapshot import Snapshot

    restored = Snapshot.load(data, script.source_map, {"double": double_impl})
    result_snapshot = restored.resume(return_value=10)

    assert result_snapshot.is_complete is True
    assert result_snapshot.value == 10
