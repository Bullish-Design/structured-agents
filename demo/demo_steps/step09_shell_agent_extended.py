"""Step 9: Extended shell agent with multiple tools."""

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
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
        script_path=SCRIPTS_DIR / "echo.pym",
    ),
    ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
        script_path=SCRIPTS_DIR / "add.pym",
    ),
    ToolSchema(
        name="multiply",
        description="Multiply two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
        script_path=SCRIPTS_DIR / "multiply.pym",
    ),
]


class ToolCallingAgent:
    """A simple agent that calls tools based on LLM output."""

    def __init__(
        self, config: KernelConfig, tools: list[ToolSchema], backend: GrailBackend
    ):
        self.config = config
        self.tools = tools
        self.backend = backend
        self.client = build_client(config)
        self.plugin = QwenPlugin()

    async def run(self, prompt: str) -> dict:
        messages = [
            Message(
                role="developer",
                content="You are a helpful assistant that calls tools when needed.",
            ),
            Message(role="user", content=prompt),
        ]

        formatted = self.plugin.format_messages(messages, self.tools)
        formatted_tools = self.plugin.format_tools(self.tools)
        grammar = self.plugin.build_grammar(
            self.tools, GrammarConfig(mode="structural_tag")
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

        if not tool_calls:
            return {"content": content, "tool_call": None}

        tool_call = tool_calls[0]
        tool_schema = next(t for t in self.tools if t.name == tool_call.name)
        result = await self.backend.execute(tool_call, tool_schema, {})

        return {
            "content": content,
            "tool_call": {"name": tool_call.name, "arguments": tool_call.arguments},
            "result": result.output,
        }

    async def close(self):
        await self.client.close()
        self.backend.shutdown()


async def main():
    backend = GrailBackend(GrailBackendConfig(grail_dir=SCRIPTS_DIR))
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )

    agent = ToolCallingAgent(config, SHELL_TOOLS, backend)

    # Test various prompts
    test_prompts = [
        "Echo 'test successful'",
        "Add 5 and 3",
        "Multiply 4 and 7",
    ]

    for prompt in test_prompts:
        print(f"\n=== Prompt: {prompt} ===")
        result = await agent.run(prompt)
        print(f"Content: {result.get('content')}")
        if result.get("tool_call"):
            print(f"Tool: {result['tool_call']['name']}")
            print(f"Arguments: {result['tool_call']['arguments']}")
            print(f"Result: {result.get('result')}")

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
