"""Step 3: Execute a single Grail script."""

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
    script_path = SCRIPTS_DIR / "echo.pym"

    config = GrailBackendConfig(grail_dir=SCRIPTS_DIR)
    backend = GrailBackend(config)

    print(f"Using script: {script_path}")
    print(f"Grail dir: {config.grail_dir}")

    tool_schema = ToolSchema(
        name="echo",
        description="Echo back the input",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text to echo"},
            },
            "required": ["content"],
        },
        script_path=script_path,
    )

    tool_call = ToolCall(
        id="call_1",
        name="echo",
        arguments={"content": "Hello from Grail!"},
    )

    result = await backend.execute(tool_call, tool_schema, {})

    print("=== Result ===")
    print(f"Output: {result.output}")
    print(f"Is error: {result.is_error}")

    backend.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
