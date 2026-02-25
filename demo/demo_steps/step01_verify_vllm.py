"""Step 1: Verify vLLM server connectivity."""

import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin
from structured_agents.client.factory import build_client


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
    )
    client = build_client(config)
    plugin = QwenPlugin()

    try:
        messages = [
            Message(role="developer", content="You are a helpful assistant."),
            Message(role="user", content="Say 'connected' if you can hear me."),
        ]

        formatted = plugin.format_messages(messages, [])

        response = await client.chat_completion(
            messages=formatted,
            tools=None,
            tool_choice="none",
        )

        print("✓ Connected to vLLM server")
        print(f"Response: {response.content}")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
