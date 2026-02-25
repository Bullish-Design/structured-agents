"""Step 6: Stateful Chat Agent."""

import asyncio
from typing import List
from structured_agents import KernelConfig, Message, QwenPlugin
from structured_agents.client.factory import build_client


class ChatAgent:
    """A simple chat agent that maintains message history.

    This is NOT a tool-calling agent - it just maintains
    a conversation with the LLM. No tools involved.
    """

    def __init__(
        self, config: KernelConfig, system_prompt: str = "You are a helpful assistant."
    ):
        self.config = config
        self.system_prompt = system_prompt
        self.client = build_client(config)
        self.plugin = QwenPlugin()
        self.history: List[Message] = [
            Message(role="developer", content=system_prompt),
        ]

    async def chat(self, user_message: str) -> str:
        """Send a message and get a response."""
        self.history.append(Message(role="user", content=user_message))

        formatted = self.plugin.format_messages(self.history, [])

        response = await self.client.chat_completion(
            messages=formatted,
            tools=None,
            tool_choice="none",
        )

        assistant_message = Message(role="assistant", content=response.content)
        self.history.append(assistant_message)

        return response.content

    def clear_history(self):
        """Clear conversation history."""
        self.history = [Message(role="developer", content=self.system_prompt)]

    async def close(self):
        await self.client.close()


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.7,
        max_tokens=256,
    )

    agent = ChatAgent(config, system_prompt="You are a concise, helpful assistant.")

    # Multi-turn conversation
    print("=== Turn 1 ===")
    response1 = await agent.chat("Hello! What is your name?")
    print(f"Agent: {response1}")

    print("\n=== Turn 2 ===")
    response2 = await agent.chat("What is 2 + 2?")
    print(f"Agent: {response2}")

    print("\n=== Turn 3 ===")
    response3 = await agent.chat("Thanks! What was my first question?")
    print(f"Agent: {response3}")

    # Show history
    print("\n=== Conversation History ===")
    for msg in agent.history:
        print(f"{msg.role}: {msg.content[:50]}...")

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
