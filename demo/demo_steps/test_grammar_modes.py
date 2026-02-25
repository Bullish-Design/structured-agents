"""Test script to evaluate different grammar modes for Qwen3."""

import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin, ToolSchema
from structured_agents.client.factory import build_client
from structured_agents.grammar.config import GrammarConfig


async def test_grammar_mode(mode: str, prompt: str):
    """Test a specific grammar mode."""
    print(f"\n{'=' * 60}")
    print(f"Testing mode: {mode}")
    print(f"Prompt: {prompt}")
    print("=" * 60)

    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    client = build_client(config)
    plugin = QwenPlugin()

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
        Message(role="user", content=prompt),
    ]

    formatted = plugin.format_messages(messages, tools)
    formatted_tools = plugin.format_tools(tools)
    grammar_config = GrammarConfig(mode=mode, allow_parallel_calls=False)
    grammar = plugin.build_grammar(tools, grammar_config)
    extra_body = plugin.to_extra_body(grammar)

    print(f"Grammar mode: {mode}")
    print(f"Extra body: {extra_body}")

    response = await client.chat_completion(
        messages=formatted,
        tools=formatted_tools,
        tool_choice="auto",
        extra_body=extra_body,
    )

    print(f"\nRaw response content: {response.content}")
    print(f"Raw tool_calls: {response.tool_calls}")

    # Parse the response
    content, tool_calls = plugin.parse_response(response.content, response.tool_calls)
    print(f"\nParsed content: {content}")
    print(f"Parsed tool_calls: {tool_calls}")

    await client.close()
    return {
        "mode": mode,
        "raw_content": response.content,
        "raw_tool_calls": response.tool_calls,
        "parsed_content": content,
        "parsed_tool_calls": tool_calls,
    }


async def main():
    # Test different prompts with different grammar modes
    prompts = [
        "What is 5 + 3?",
        "Calculate 10 minus 4",
        "Multiply 3 and 7",
    ]

    modes = ["structural_tag"]  # ebnf has empty args bug, json_schema ignored

    results = []
    for mode in modes:
        for prompt in prompts[:1]:  # Just test first prompt for now
            result = await test_grammar_mode(mode, prompt)
            results.append(result)
            await asyncio.sleep(1)  # Rate limit

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\nMode: {r['mode']}")
        print(f"  Raw tool_calls: {r['raw_tool_calls']}")
        print(f"  Parsed tool_calls: {r['parsed_tool_calls']}")


if __name__ == "__main__":
    asyncio.run(main())
