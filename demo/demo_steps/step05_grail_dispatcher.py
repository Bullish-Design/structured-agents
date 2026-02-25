"""Step 5: Grail Dispatcher - pass-through agent pattern."""

import asyncio
from pathlib import Path
from structured_agents import (
    GrailBackend,
    GrailBackendConfig,
    ToolCall,
    ToolSchema,
)
import json

SCRIPTS_DIR = Path(__file__).parent / "scripts"


class GrailDispatcher:
    """A simple agent that dispatches commands to Grail scripts.

    This is NOT a full agent kernel - it's a lightweight wrapper
    that routes user commands to specific .pym scripts.
    No LLM involved - just direct script execution.
    """

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir
        self.backend = GrailBackend(GrailBackendConfig(grail_dir=scripts_dir))

        self.available_scripts = {}
        for pym_file in scripts_dir.glob("*.pym"):
            script_name = pym_file.stem
            self.available_scripts[script_name] = pym_file

    def list_commands(self) -> list[str]:
        """List available commands."""
        return list(self.available_scripts.keys())

    async def run(self, command: str, data: dict) -> dict:
        """Run a command with provided data.

        Args:
            command: The script name to run (e.g., "add")
            data: Parameters to pass to the script

        Returns:
            The result from the script execution
        """
        if command not in self.available_scripts:
            return {"error": f"Unknown command: {command}"}

        tool_schema = ToolSchema(
            name=command,
            description=f"Execute {command} operation",
            parameters={
                "type": "object",
                "properties": {k: {"type": "number"} for k in data.keys()},
            },
            script_path=self.available_scripts[command],
        )

        tool_call = ToolCall(id="dispatch_1", name=command, arguments=data)
        result = await self.backend.execute(tool_call, tool_schema, {})

        return json.loads(result.output) if result.output else {}

    def shutdown(self):
        self.backend.shutdown()


async def main():
    dispatcher = GrailDispatcher(SCRIPTS_DIR)

    print(f"Available commands: {dispatcher.list_commands()}")

    # Test commands
    result1 = await dispatcher.run("add", {"a": 5, "b": 3})
    print(f"\nadd(5, 3) = {result1}")

    result2 = await dispatcher.run("multiply", {"a": 4, "b": 7})
    print(f"multiply(4, 7) = {result2}")

    dispatcher.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
