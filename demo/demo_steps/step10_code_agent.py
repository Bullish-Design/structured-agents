"""Step 10: Code agent using code_helper tools."""

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

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agents" / "code_helper"

CODE_TOOLS = [
    ToolSchema(
        name="generate_docstring",
        description="Generate a docstring for Python code",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code"},
                "function_name": {
                    "type": "string",
                    "description": "Optional function name",
                },
            },
            "required": ["code"],
        },
        script_path=SCRIPTS_DIR / "generate_docstring.pym",
    ),
    ToolSchema(
        name="summarize_code",
        description="Summarize what Python code does",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source code to summarize",
                },
            },
            "required": ["code"],
        },
        script_path=SCRIPTS_DIR / "summarize_code.pym",
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
            Message(role="developer", content="You are a code analysis assistant."),
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


SAMPLE_CODE = '''
def process_data(users: list[dict]) -> dict:
    """Process a list of user dictionaries and return statistics."""
    total = len(users)
    avg_age = sum(u.get('age', 0) for u in users) / total if total > 0 else 0
    return {'total_users': total, 'avg_age': avg_age}
'''


async def main():
    backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=512,
    )

    agent = ToolCallingAgent(config, CODE_TOOLS, backend)

    # Test docstring generation
    prompt = f"Generate a docstring for this code:\n{SAMPLE_CODE}"
    print(f"=== Prompt: {prompt[:50]}... ===")

    result = await agent.run(prompt)
    print(f"Content: {result.get('content')}")
    if result.get("tool_call"):
        print(f"Tool: {result['tool_call']['name']}")
        print(f"Arguments: {result['tool_call']['arguments']}")
        print(f"Result: {result.get('result')}")

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
