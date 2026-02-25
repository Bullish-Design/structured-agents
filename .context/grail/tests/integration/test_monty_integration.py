"""Test direct integration with Monty."""

import pytest

# This requires pydantic-monty to be installed
pytest.importorskip("pydantic_monty")

import pydantic_monty


@pytest.mark.integration
def test_basic_monty_execution():
    """Test calling Monty with simple code."""
    code = "x = 1 + 2\nx"

    m = pydantic_monty.Monty(code)
    result = m.run(inputs=None)

    assert result == 3


@pytest.mark.integration
async def test_monty_with_external_function():
    """Test Monty with external functions."""
    code = """
result = await double(x)
result
"""

    stubs = """
x: int

async def double(n: int) -> int:
    ...
"""

    async def double_impl(n: int) -> int:
        return n * 2

    m = pydantic_monty.Monty(
        code, type_check_stubs=stubs, inputs=["x"], external_functions=["double"]
    )
    result = await pydantic_monty.run_monty_async(
        m, inputs={"x": 5}, external_functions={"double": double_impl}
    )

    assert result == 10


@pytest.mark.integration
def test_monty_with_resource_limits():
    """Test Monty with resource limits."""
    code = "x = 1\nx"

    m = pydantic_monty.Monty(
        code
        # max_memory=1024 * 1024,  # 1MB
        # max_duration_secs=1.0,
        # max_recursion_depth=100,
    )

    result = m.run(
        inputs=None,
        limits={"max_memory": 1024 * 1024, "max_duration_secs": 1.0, "max_recursion_depth": 100},
    )
    assert result == 1


@pytest.mark.integration
def test_monty_type_checking():
    """Test Monty's type checker integration."""
    code = """
result = await get_data("test")
result
"""

    stubs = """
async def get_data(id: str) -> dict:
    ...
"""

    # This should type-check successfully
    m = pydantic_monty.Monty(code, type_check=True, type_check_stubs=stubs)

    # Note: Actual execution would need the external function


@pytest.mark.integration
async def test_monty_error_handling():
    """Test that Monty errors can be caught and inspected."""
    code = "x = undefined_variable"

    m = pydantic_monty.Monty(code)

    with pytest.raises(Exception) as exc_info:
        await pydantic_monty.run_monty_async(m, inputs=None)

    # Should get some kind of error about undefined variable
    assert "undefined" in str(exc_info.value).lower() or "name" in str(exc_info.value).lower()
