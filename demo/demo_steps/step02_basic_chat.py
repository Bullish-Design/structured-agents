"""Step 2: Basic chat with QwenPlugin."""

import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin
from structured_agents.client.factory import build_client


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.7,
        max_tokens=256,
    )
    client = build_client(config)
    plugin = QwenPlugin()

    messages = [
        Message(role="developer", content="You are a helpful assistant."),
        Message(role="user", content="What is 2 + 2?"),
    ]

    formatted = plugin.format_messages(messages, [])

    response = await client.chat_completion(
        messages=formatted,
        tools=None,
        tool_choice="none",
    )

    print("=== Response ===")
    print(response.content)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
