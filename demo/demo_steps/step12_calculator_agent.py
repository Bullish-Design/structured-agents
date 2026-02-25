"""Step 12: Calculator agent with multiple operations - tests complex tool selection."""

import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin, ToolSchema
from structured_agents.client.factory import build_client
from structured_agents.grammar.config import GrammarConfig


CALCULATOR_TOOLS = [
    ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="subtract",
        description="Subtract b from a",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="multiply",
        description="Multiply two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="divide",
        description="Divide a by b",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="power",
        description="Raise a to the power of b",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="modulo",
        description="Get remainder of a divided by b",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
]


class CalculatorAgent:
    def __init__(self, config: KernelConfig):
        self.config = config
        self.client = build_client(config)
        self.plugin = QwenPlugin()

    async def calculate(self, prompt: str):
        messages = [
            Message(
                role="developer",
                content="You are a calculator. Use the appropriate tool for each operation.",
            ),
            Message(role="user", content=prompt),
        ]

        formatted = self.plugin.format_messages(messages, CALCULATOR_TOOLS)
        formatted_tools = self.plugin.format_tools(CALCULATOR_TOOLS)
        grammar = self.plugin.build_grammar(
            CALCULATOR_TOOLS, GrammarConfig(mode="structural_tag")
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

        return content, tool_calls

    async def close(self):
        await self.client.close()


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )

    agent = CalculatorAgent(config)

    prompts = [
        "What is 15 + 27?",
        "Calculate 100 minus 37",
        "Multiply 12 by 8",
        "Divide 144 by 12",
        "What is 2 to the power of 10?",
        "What is 17 modulo 5?",
    ]

    print("=" * 60)
    print("CALCULATOR AGENT - Multiple Operations")
    print("=" * 60)

    for prompt in prompts:
        print(f"\n>>> {prompt}")
        content, tool_calls = await agent.calculate(prompt)
        if tool_calls:
            tc = tool_calls[0]
            print(f"    Tool: {tc.name}")
            print(f"    Args: {tc.arguments}")
        else:
            print(f"    No tool call: {content}")

    await agent.close()
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
