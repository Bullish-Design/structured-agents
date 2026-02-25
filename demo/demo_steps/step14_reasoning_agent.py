"""Step 14: Multi-tool reasoning agent - tests complex decision making."""

import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin, ToolSchema
from structured_agents.client.factory import build_client
from structured_agents.grammar.config import GrammarConfig


REASONING_TOOLS = [
    ToolSchema(
        name="get_weather",
        description="Get current weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "country": {
                    "type": "string",
                    "description": "Country code (e.g., US, UK)",
                },
            },
            "required": ["city"],
        },
    ),
    ToolSchema(
        name="get_forecast",
        description="Get weather forecast for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "days": {"type": "integer", "description": "Number of days (1-7)"},
            },
            "required": ["city", "days"],
        },
    ),
    ToolSchema(
        name="compare_cities",
        description="Compare weather between two cities",
        parameters={
            "type": "object",
            "properties": {
                "city1": {"type": "string"},
                "city2": {"type": "string"},
            },
            "required": ["city1", "city2"],
        },
    ),
    ToolSchema(
        name="get_time",
        description="Get current time for a city",
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone (e.g., America/New_York)",
                },
            },
            "required": ["timezone"],
        },
    ),
]


class ReasoningAgent:
    def __init__(self, config: KernelConfig):
        self.config = config
        self.client = build_client(config)
        self.plugin = QwenPlugin()

    async def reason(self, prompt: str):
        messages = [
            Message(
                role="developer",
                content="""You are a helpful assistant with access to weather and time tools.
Choose the appropriate tool based on the user's request.
- Use get_weather for current weather
- Use get_forecast for multi-day forecasts  
- Use compare_cities to compare two cities
- Use get_time for time information""",
            ),
            Message(role="user", content=prompt),
        ]

        formatted = self.plugin.format_messages(messages, REASONING_TOOLS)
        formatted_tools = self.plugin.format_tools(REASONING_TOOLS)
        grammar = self.plugin.build_grammar(
            REASONING_TOOLS, GrammarConfig(mode="structural_tag")
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

    agent = ReasoningAgent(config)

    prompts = [
        "What's the weather like in London?",
        "Give me a 5-day forecast for Paris",
        "Compare the weather in Tokyo and Seoul",
        "What time is it in New York?",
    ]

    print("=" * 60)
    print("REASONING AGENT - Multi-tool Decision Making")
    print("=" * 60)

    for prompt in prompts:
        print(f"\n>>> {prompt}")
        content, tool_calls = await agent.reason(prompt)
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
