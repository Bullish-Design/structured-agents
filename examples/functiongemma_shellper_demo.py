import asyncio
import json
from pathlib import Path

from structured_agents import (
    AgentKernel,
    FunctionGemmaPlugin,
    GrailBackend,
    GrailBackendConfig,
    KernelConfig,
    Message,
    ToolSchema,
)

JOB_DESCRIPTION_PATH = (
    Path(__file__).resolve().parent.parent
    / ".context"
    / "functiongemma_examples"
    / "distil-SHELLper-main"
    / "data"
    / "job_description.json"
)

TOOLS_DIR = Path("agents") / "shellper_demo"


def load_shellper_tools() -> tuple[str, list[ToolSchema]]:
    data = json.loads(JOB_DESCRIPTION_PATH.read_text(encoding="utf-8"))
    tools: list[ToolSchema] = []
    for tool in data["tools"]:
        func = tool["function"]
        tools.append(
            ToolSchema(
                name=func["name"],
                description=func.get("description", ""),
                parameters=func.get("parameters", {}),
                script_path=TOOLS_DIR / f"{func['name']}.pym",
            )
        )
    return data["task_description"], tools


async def run_demo() -> None:
    _task_description, tools = load_shellper_tools()

    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="google/functiongemma-270m-it",
        temperature=0,
        max_tokens=128,
        tool_choice="auto",
    )

    backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    kernel = AgentKernel(
        config=config,
        plugin=FunctionGemmaPlugin(),
        backend=backend,
    )

    developer_prompt = (
        "You are a model that can do function calling with the following functions."
    )

    user_prompts = [
        "Show me what files are in my current directory please.",
        "What directory am I in right now?",
        "Create a folder called reports.",
        "Show me the last 5 lines of error_log.txt.",
        "Search for files with draft in the name.",
    ]

    async def run_call(prompt: str) -> dict[str, object]:
        messages = [
            Message(role="developer", content=developer_prompt),
            Message(role="user", content=prompt),
        ]
        step_result = await kernel.step(messages=messages, tools=tools, context={})
        if not step_result.tool_calls:
            return {
                "prompt": prompt,
                "error": "No tool call returned by the model.",
            }
        tool_call = step_result.tool_calls[0]
        tool_result = step_result.tool_results[0]
        return {
            "prompt": prompt,
            "tool_call": {"name": tool_call.name, "arguments": tool_call.arguments},
            "tool_result": tool_result.output,
        }

    try:
        results = await asyncio.gather(*(run_call(prompt) for prompt in user_prompts))
        for result in results:
            print("\n=== Demo Result ===")
            print(json.dumps(result, indent=2))
    finally:
        await kernel.close()
        backend.shutdown()


if __name__ == "__main__":
    asyncio.run(run_demo())
