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
    task_description, tools = load_shellper_tools()

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

    system_prompt = (
        "You are a model that can do function calling with the following functions. "
        f"Task: {task_description}"
    )

    messages = [
        Message(role="system", content=system_prompt),
        Message(
            role="user",
            content="Show me what files are in my current directory please.",
        ),
    ]

    try:
        step_result = await kernel.step(messages=messages, tools=tools, context={})
        if not step_result.tool_calls:
            print("No tool call returned by the model.")
            return

        tool_call = step_result.tool_calls[0]
        tool_result = step_result.tool_results[0]

        print("Tool call:")
        print(
            json.dumps(
                {"name": tool_call.name, "arguments": tool_call.arguments}, indent=2
            )
        )
        print("\nTool result:")
        print(json.dumps(tool_result.output, indent=2))
    finally:
        await kernel.close()
        backend.shutdown()


if __name__ == "__main__":
    asyncio.run(run_demo())
