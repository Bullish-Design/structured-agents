import ast
import json
import os
import uuid
from asyncio import run
from pathlib import Path
from typing import Any, Callable, Awaitable

from structured_agents import ToolCall, ToolSchema, KernelConfig, Message
from structured_agents import GrailBackend, GrailBackendConfig
from structured_agents.client.factory import build_client
from structured_agents.plugins.qwen import QwenPlugin
from structured_agents.grammar.config import GrammarConfig

AGENT_DIR = Path(__file__).parent / "agents" / "workspace_agent"
STATE_DIR = AGENT_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
AGENT_ID = "workspace_agent"


def build_externals(
    agent_id: str, context: dict[str, Any]
) -> dict[str, Callable[..., Awaitable[Any]]]:
    async def ensure_dir(path: str) -> None:
        os.makedirs(path, exist_ok=True)

    async def write_file(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    async def read_file(path: str) -> str:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    async def list_dir(path: str) -> list[str]:
        try:
            return sorted(os.listdir(path))
        except FileNotFoundError:
            return []

    async def file_exists(path: str) -> bool:
        return os.path.exists(path)

    return {
        "ensure_dir": ensure_dir,
        "write_file": write_file,
        "read_file": read_file,
        "list_dir": list_dir,
        "file_exists": file_exists,
    }


TOOL_SCHEMAS = [
    ToolSchema(
        name="add_entry",
        description="Add or replace a workspace entry.",
        parameters={
            "type": "object",
            "properties": {
                "state_dir": {"type": "string"},
                "name": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["state_dir", "name"],
        },
        script_path=AGENT_DIR / "add_entry.pym",
    ),
    ToolSchema(
        name="update_entry",
        description="Update an existing workspace entry.",
        parameters={
            "type": "object",
            "properties": {
                "state_dir": {"type": "string"},
                "name": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["state_dir", "name"],
        },
        script_path=AGENT_DIR / "update_entry.pym",
    ),
    ToolSchema(
        name="list_entries",
        description="List workspace entries, optionally filtered by priority.",
        parameters={
            "type": "object",
            "properties": {
                "state_dir": {"type": "string"},
                "filter_priority": {"type": "string"},
            },
            "required": ["state_dir"],
        },
        script_path=AGENT_DIR / "list_entries.pym",
    ),
    ToolSchema(
        name="summarize_state",
        description="Summarize the workspace entries and request formatting.",
        parameters={
            "type": "object",
            "properties": {
                "state_dir": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["state_dir"],
        },
        script_path=AGENT_DIR / "summarize_state.pym",
    ),
    ToolSchema(
        name="format_summary",
        description="Format a raw summary string.",
        parameters={
            "type": "object",
            "properties": {
                "raw_summary": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["raw_summary"],
        },
        script_path=AGENT_DIR / "format_summary.pym",
    ),
]


class WorkspaceAgent:
    def __init__(self, backend: GrailBackend, tool_schemas: list[ToolSchema]) -> None:
        self.backend = backend
        self.tool_schemas = {schema.name: schema for schema in tool_schemas}
        self.inbox: list[dict[str, Any]] = []
        self.outbox: list[dict[str, Any]] = []
        # Qwen3 integration
        self.kernel_config = KernelConfig(
            base_url="http://remora-server:8000/v1",
            model="Qwen/Qwen3-4B-Instruct-2507-FP8",
            temperature=0.0,
            max_tokens=512,
        )
        self.client = build_client(self.kernel_config)
        self.plugin = QwenPlugin()

    def load_state(self) -> dict[str, dict[str, str]]:
        entries: dict[str, dict[str, str]] = {}
        if STATE_DIR.exists():
            for entry_file in sorted(STATE_DIR.glob("*.txt")):
                text = entry_file.read_text(encoding="utf-8")
                data = {
                    line.split(":", 1)[0]: line.split(":", 1)[1] if ":" in line else ""
                    for line in text.splitlines()
                }
                entries[entry_file.stem] = data
        return entries

    def parse_output(self, payload: str | None) -> Any:
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            return payload

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        schema = self.tool_schemas[tool_name]
        # Inject state_dir only if the schema expects it
        props = schema.parameters.get("properties", {}) if schema.parameters else {}
        final_args = dict(arguments)
        if "state_dir" in props:
            final_args["state_dir"] = str(STATE_DIR)
        tool_call = ToolCall(
            id=f"{tool_name}-{uuid.uuid4().hex[:8]}",
            name=tool_name,
            arguments=final_args,
        )
        result = await self.backend.execute(tool_call, schema, {"agent_id": AGENT_ID})
        parsed = self.parse_output(result.output)
        response = {
            "tool": tool_name,
            "arguments": final_args,
            "raw": result.output,
            "parsed": parsed,
        }
        if (
            parsed
            and isinstance(parsed, dict)
            and (nested := parsed.get("nested_tool_call"))
        ):
            nested_result = await self.execute_tool(
                nested["name"], nested.get("arguments", {})
            )
            response["nested_tool_call"] = nested_result
        return response

    async def send_to_model(self, user_message: str) -> str:
        """Send a natural language message to Qwen3 and execute the chosen tool."""
        messages = [
            Message(
                role="developer",
                content=(
                    "You are a workspace management assistant. Select the most appropriate "
                    "tool to fulfill the user's request using the provided tool list. "
                    "Only use tools that are explicitly listed."
                ),
            ),
            Message(role="user", content=user_message),
        ]

        formatted_messages = self.plugin.format_messages(
            messages, list(self.tool_schemas.values())
        )
        formatted_tools = self.plugin.format_tools(list(self.tool_schemas.values()))
        grammar = self.plugin.build_grammar(
            list(self.tool_schemas.values()), GrammarConfig(mode="structural_tag")
        )
        extra_body = self.plugin.to_extra_body(grammar)

        response = await self.client.chat_completion(
            messages=formatted_messages,
            tools=formatted_tools,
            tool_choice="auto",
            extra_body=extra_body,
        )

        content, tool_calls = self.plugin.parse_response(
            response.content, response.tool_calls
        )

        if not tool_calls:
            return content or "No tool selected by model."

        # Execute first tool call (supporting parallel calls would require more handling)
        tool_call = tool_calls[0]
        result = await self.execute_tool(tool_call.name, tool_call.arguments)
        return (
            result["parsed"]
            if isinstance(result["parsed"], str)
            else json.dumps(result["parsed"])
        )

    async def process_message(self, message: dict[str, Any]) -> None:
        self.inbox.append(message)
        tool_name = message["tool"]
        tool_args = message.get("arguments", {})
        tool_result = await self.execute_tool(tool_name, tool_args)
        entry: dict[str, Any] = {
            "message": message["text"],
            "tool_result": tool_result,
            "state_snapshot": self.load_state(),
        }
        self.outbox.append(entry)


async def main() -> None:
    backend_config = GrailBackendConfig(grail_dir=AGENT_DIR)
    backend = GrailBackend(backend_config, externals_factory=build_externals)
    agent = WorkspaceAgent(backend, TOOL_SCHEMAS)

    # Natural language queries for Qwen3 to parse
    queries = [
        "Add a new task 'Review Q3 metrics' with high priority and note 'Check budget allocation'",
        "Update the 'Review Q3 metrics' task to in-progress with a note about data sources",
        "List all high-priority tasks",
        "Summarize all tasks in bullet format",
    ]

    print("=== Qwen3 Tool Selection Demo ===")
    for query in queries:
        print(f"\nQuery: {query}")
        result = await agent.send_to_model(query)
        print(f"Result: {result}")

    backend.shutdown()
    await agent.client.close()
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    run(main())
