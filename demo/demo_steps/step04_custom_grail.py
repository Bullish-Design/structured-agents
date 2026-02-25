"""Step 4: Execute custom Grail scripts."""

import asyncio
from pathlib import Path
from structured_agents import (
    GrailBackend,
    GrailBackendConfig,
    ToolCall,
    ToolSchema,
)

SCRIPTS_DIR = Path(__file__).parent / "scripts"


async def main():
    config = GrailBackendConfig(grail_dir=SCRIPTS_DIR)
    backend = GrailBackend(config)

    add_schema = ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        script_path=SCRIPTS_DIR / "add.pym",
    )

    add_call = ToolCall(id="call_1", name="add", arguments={"a": 5, "b": 3})
    add_result = await backend.execute(add_call, add_schema, {})

    print("=== add(5, 3) ===")
    print(f"Output: {add_result.output}")

    multiply_schema = ToolSchema(
        name="multiply",
        description="Multiply two numbers",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        script_path=SCRIPTS_DIR / "multiply.pym",
    )

    multiply_call = ToolCall(id="call_2", name="multiply", arguments={"a": 4, "b": 7})
    multiply_result = await backend.execute(multiply_call, multiply_schema, {})

    print("\n=== multiply(4, 7) ===")
    print(f"Output: {multiply_result.output}")

    backend.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
