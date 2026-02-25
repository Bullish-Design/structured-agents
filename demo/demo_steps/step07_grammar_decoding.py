"""Step 7: Grammar-constrained decoding with XGrammar."""

import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin, ToolSchema
from structured_agents.client.factory import build_client
from structured_agents.grammar.config import GrammarConfig


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    client = build_client(config)
    plugin = QwenPlugin()

    # Define a simple tool schema
    tools = [
        ToolSchema(
            name="calculator",
            description="Perform a calculation",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply"],
                    },
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["operation", "a", "b"],
            },
        )
    ]

    messages = [
        Message(role="developer", content="You are a calculator assistant."),
        Message(role="user", content="What is 5 + 3?"),
    ]

    formatted = plugin.format_messages(messages, tools)
    formatted_tools = plugin.format_tools(tools)
    # Use structural_tag mode - ebnf mode has empty arguments bug with vLLM
    grammar = plugin.build_grammar(tools, GrammarConfig(mode="structural_tag"))
    extra_body = plugin.to_extra_body(grammar)

    response = await client.chat_completion(
        messages=formatted,
        tools=formatted_tools,
        tool_choice="auto",
        extra_body=extra_body,
    )

    print("=== Response ===")
    print(f"Content: {response.content}")
    print(f"Tool calls: {response.tool_calls}")

    # Parse the response
    content, tool_calls = plugin.parse_response(response.content, response.tool_calls)
    print(f"\nParsed content: {content}")
    print(f"Parsed tool calls: {tool_calls}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
