"""Test public API surface."""

import grail


def test_public_api_symbols():
    """Verify all public symbols are exported."""
    expected = {
        # Core
        "load",
        "run",
        # Declarations
        "external",
        "Input",
        # Snapshot
        "Snapshot",
        # Limits
        "STRICT",
        "DEFAULT",
        "PERMISSIVE",
        # Errors
        "GrailError",
        "ParseError",
        "CheckError",
        "InputError",
        "ExternalError",
        "ExecutionError",
        "LimitError",
        "OutputError",
        # Check results
        "CheckResult",
        "CheckMessage",
    }

    for symbol in expected:
        assert hasattr(grail, symbol), f"Missing public symbol: {symbol}"


def test_version_exists():
    """Should have __version__ attribute."""
    assert hasattr(grail, "__version__")
    assert isinstance(grail.__version__, str)


def test_all_list():
    """Should have __all__ list."""
    assert hasattr(grail, "__all__")
    assert isinstance(grail.__all__, list)
    assert len(grail.__all__) >= 15


def test_can_import_all():
    """Should be able to import all public symbols."""
    from grail import (
        load,
        run,
        external,
        Input,
        Snapshot,
        STRICT,
        DEFAULT,
        PERMISSIVE,
        GrailError,
        ParseError,
        CheckError,
        InputError,
        ExternalError,
        ExecutionError,
        LimitError,
        OutputError,
        CheckResult,
        CheckMessage,
    )

    assert load is not None
    assert run is not None
