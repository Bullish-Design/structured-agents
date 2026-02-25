"""Test Monty compatibility checker."""

from pathlib import Path

from grail.checker import check_pym
from grail.parser import parse_pym_content, parse_pym_file

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_valid_pym_passes() -> None:
    """Valid .pym files should pass all checks."""
    result = parse_pym_file(FIXTURES_DIR / "simple.pym")
    check_result = check_pym(result)

    assert check_result.valid is True
    assert len(check_result.errors) == 0


def test_class_definition_detected() -> None:
    """Class definitions should be detected as E001."""
    result = parse_pym_file(FIXTURES_DIR / "invalid_class.pym")
    check_result = check_pym(result)

    assert check_result.valid is False
    assert any(error.code == "E001" for error in check_result.errors)
    assert any("Class definitions" in error.message for error in check_result.errors)


def test_with_statement_detected() -> None:
    """'with' statements should be detected as E003."""
    result = parse_pym_file(FIXTURES_DIR / "invalid_with.pym")
    check_result = check_pym(result)

    assert check_result.valid is False
    assert any(error.code == "E003" for error in check_result.errors)


def test_generator_detected() -> None:
    """Generators should be detected as E002."""
    result = parse_pym_file(FIXTURES_DIR / "invalid_generator.pym")
    check_result = check_pym(result)

    assert check_result.valid is False
    assert any(error.code == "E002" for error in check_result.errors)


def test_forbidden_import_detected() -> None:
    """Forbidden imports should be detected as E005."""
    content = """
import json

data = json.loads('{}')
"""
    result = parse_pym_content(content)
    check_result = check_pym(result)

    assert check_result.valid is False
    assert any(error.code == "E005" for error in check_result.errors)
    assert any("json" in error.message for error in check_result.errors)


def test_typing_import_allowed() -> None:
    """Imports from typing should be allowed."""
    content = """
from typing import Any, Dict

x: Dict[str, Any] = {}
"""
    result = parse_pym_content(content)
    check_result = check_pym(result)

    assert not any(error.code == "E005" for error in check_result.errors)


def test_info_collection() -> None:
    """Should collect info about the script."""
    result = parse_pym_file(FIXTURES_DIR / "with_multiple_externals.pym")
    check_result = check_pym(result)

    assert check_result.info["externals_count"] == 2
    assert check_result.info["inputs_count"] == 2
    assert check_result.info["lines_of_code"] > 0
    assert "for_loop" in check_result.info["monty_features_used"]


def test_bare_dict_warning() -> None:
    """Bare dict as final expression should warn."""
    content = """
from grail import external, Input

x: int = Input("x")

{"result": x * 2}
"""
    result = parse_pym_content(content)
    check_result = check_pym(result)

    assert any(warning.code == "W001" for warning in check_result.warnings)


def test_external_async_not_tracked_as_feature() -> None:
    """External async functions should not count toward async_await feature tracking."""
    content = """\
from grail import external

@external
async def fetch(url: str) -> str: ...

result = "hello"
"""
    parsed = parse_pym_content(content)
    result = check_pym(parsed)

    assert "async_await" not in result.info.get("monty_features_used", [])
