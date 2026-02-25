"""Step 13: Filesystem agent - tests file operations with complex paths."""

import asyncio
from pathlib import Path
from structured_agents import (
    KernelConfig,
    Message,
    QwenPlugin,
    GrailBackend,
    GrailBackendConfig,
    ToolSchema,
    build_client,
)
from structured_agents.grammar.config import GrammarConfig


FILESYSTEM_TOOLS = [
    ToolSchema(
        name="read_file",
        description="Read contents of a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to read",
                },
            },
            "required": ["path"],
        },
    ),
    ToolSchema(
        name="write_file",
        description="Write content to a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    ),
    ToolSchema(
        name="list_directory",
        description="List files in a directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to directory"},
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files",
                },
            },
            "required": ["path"],
        },
    ),
    ToolSchema(
        name="file_exists",
        description="Check if a file or directory exists",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to check"},
            },
            "required": ["path"],
        },
    ),
]


class FilesystemAgent:
    def __init__(self, config: KernelConfig, backend: GrailBackend):
        self.config = config
        self.backend = backend
        self.client = build_client(config)
        self.plugin = QwenPlugin()

    async def operate(self, prompt: str):
        messages = [
            Message(
                role="developer",
                content="You are a filesystem assistant. Use tools to help with file operations.",
            ),
            Message(role="user", content=prompt),
        ]

        formatted = self.plugin.format_messages(messages, FILESYSTEM_TOOLS)
        formatted_tools = self.plugin.format_tools(FILESYSTEM_TOOLS)
        grammar = self.plugin.build_grammar(
            FILESYSTEM_TOOLS, GrammarConfig(mode="structural_tag")
        )
        extra_body = self.plugin.to_extra_body(grammar)

        response = await self.client.chat_completion(
            messages=formatted,
            tools=formatted_tools,
            tool_choice="auto",
            extra_body=extra_body,
        )

        content, tool_calls = self.plugin.parse_response(
            response.content, response.tool_calls
        )

        result = None
        if tool_calls:
            tool_call = tool_calls[0]
            tool_schema = next(
                (t for t in FILESYSTEM_TOOLS if t.name == tool_call.name), None
            )
            if tool_schema:
                result = await self.backend.execute(
                    tool_call, tool_schema, {"cwd": "/tmp"}
                )

        return content, tool_calls, result

    async def close(self):
        await self.client.close()


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )

    backend = GrailBackend(
        GrailBackendConfig(grail_dir=Path.cwd() / "demo" / "demo_steps" / "scripts")
    )
    agent = FilesystemAgent(config, backend)

    prompts = [
        "List files in /tmp directory",
        "Check if /tmp/test.txt exists",
        "Read the file /etc/hostname",
    ]

    print("=" * 60)
    print("FILESYSTEM AGENT - File Operations")
    print("=" * 60)

    for prompt in prompts:
        print(f"\n>>> {prompt}")
        content, tool_calls, result = await agent.operate(prompt)
        if tool_calls:
            tc = tool_calls[0]
            print(f"    Tool: {tc.name}")
            print(f"    Args: {tc.arguments}")
            if result:
                print(f"    Result: {result.output}")
        else:
            print(f"    No tool call: {content}")

    await agent.close()
    backend.shutdown()
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
