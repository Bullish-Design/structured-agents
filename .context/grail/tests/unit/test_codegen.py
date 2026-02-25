from grail.parser import parse_pym_content
from grail.codegen import generate_monty_code


def test_strips_grail_imports():
    """Should remove 'from grail import ...' statements."""
    content = """
from grail import external, Input
from typing import Any

x: int = Input("x")

@external
async def double(n: int) -> int:
    ...

result = await double(x)
result
"""
    parse_result = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parse_result)

    assert "from grail" not in monty_code
    assert "from typing import Any" in monty_code  # typing imports preserved


def test_strips_external_functions():
    """Should remove @external function definitions."""
    content = """
from grail import external

@external
async def double(n: int) -> int:
    ...

result = await double(5)
"""
    parse_result = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parse_result)

    assert "async def double" not in monty_code
    assert "await double(5)" in monty_code  # Call preserved


def test_strips_input_declarations():
    """Should remove Input() assignment statements."""
    content = """
from grail import Input

x: int = Input("x")
y = x * 2
"""
    parse_result = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parse_result)

    assert "Input(" not in monty_code
    assert "y = x * 2" in monty_code  # Usage preserved


def test_preserves_executable_code():
    """Should preserve all executable code."""
    content = """
from grail import external, Input

x: int = Input("x")

@external
async def process(n: int) -> int:
    ...

result = await process(x)
final = result * 2

{
    "value": final,
    "doubled": final * 2
}
"""
    parse_result = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parse_result)

    # Check executable code is preserved
    assert "result = await process(x)" in monty_code
    assert "final = result * 2" in monty_code
    assert "'value': final" in monty_code


def test_source_map_accounts_for_stripped_lines():
    """
    When @external functions are removed, the source map should still
    point Monty lines back to the correct .pym lines.
    """
    content = """\
from grail import external, Input

budget: float = Input("budget")

@external
async def fetch_data(key: str) -> dict: ...

result = budget * 2
"""
    parsed = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parsed)

    monty_lines = monty_code.strip().splitlines()
    result_monty_line = None
    for i, line in enumerate(monty_lines, 1):
        if "result = budget * 2" in line:
            result_monty_line = i
            break

    assert result_monty_line is not None, "Expected 'result = budget * 2' in Monty code"
    assert source_map.monty_to_pym.get(result_monty_line) == 8


def test_source_map_identity_for_unchanged_lines():
    """Lines that aren't affected by stripping should still map correctly."""
    content = """\
x = 1
y = 2
z = x + y
"""
    parsed = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parsed)

    for monty_line, pym_line in source_map.monty_to_pym.items():
        assert monty_line == pym_line


def test_source_map_created():
    """Should create source map for line number mapping."""
    content = """\
x = 1
y = 2
z = x + y
"""

    parse_result = parse_pym_content(content)
    monty_code, source_map = generate_monty_code(parse_result)

    # Source map should have mappings
    assert len(source_map.pym_to_monty) > 0
    assert len(source_map.monty_to_pym) > 0


def test_generate_monty_code_produces_valid_python():
    """The output of generate_monty_code should always be valid Python."""
    import ast

    content = """\
from grail import external, Input

budget: float = Input("budget")

@external
async def fetch(url: str) -> str: ...

result = budget * 2
"""
    parsed = parse_pym_content(content)
    monty_code, _ = generate_monty_code(parsed)

    # Should not raise
    ast.parse(monty_code)
