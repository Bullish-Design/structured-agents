"""Step 8: Shell agent with single tool call."""

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

SCRIPTS_DIR = Path(__file__).parent / "scripts"

SHELL_TOOLS = [
    ToolSchema(
        name="echo",
        description="Echo back the input text",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text to echo"},
            },
            "required": ["content"],
        },
        script_path=SCRIPTS_DIR / "echo.pym",
    ),
]


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )

    client = build_client(config)
    plugin = QwenPlugin()
    backend = GrailBackend(GrailBackendConfig(grail_dir=SCRIPTS_DIR))

    messages = [
        Message(
            role="developer",
            content="You are a helpful assistant that can use shell commands.",
        ),
        Message(role="user", content="Echo 'Hello World'"),
    ]

    # Format for model
    formatted_messages = plugin.format_messages(messages, SHELL_TOOLS)
    formatted_tools = plugin.format_tools(SHELL_TOOLS)
    grammar = plugin.build_grammar(SHELL_TOOLS, GrammarConfig(mode="structural_tag"))
    extra_body = plugin.to_extra_body(grammar)

    # Make LLM call
    response = await client.chat_completion(
        messages=formatted_messages,
        tools=formatted_tools,
        tool_choice="auto",
        extra_body=extra_body,
    )

    print("=== LLM Response ===")
    print(f"Content: {response.content}")
    print(f"Tool calls: {response.tool_calls}")

    # Parse and execute
    content, tool_calls = plugin.parse_response(response.content, response.tool_calls)

    if tool_calls:
        tool_call = tool_calls[0]
        tool_schema = next(t for t in SHELL_TOOLS if t.name == tool_call.name)

        print(f"\n=== Executing {tool_call.name} ===")
        print(f"Arguments: {tool_call.arguments}")

        result = await backend.execute(tool_call, tool_schema, {})
        print(f"Result: {result.output}")

    await client.close()
    backend.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
