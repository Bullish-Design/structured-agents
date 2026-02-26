"""Agent - high-level entry point for structured-agents."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
import yaml

from structured_agents.client.protocol import LLMClient
from structured_agents.client.factory import build_client
from structured_agents.events.observer import NullObserver, Observer
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.kernel import AgentKernel
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import QwenResponseParser
from structured_agents.tools.grail import discover_tools
from structured_agents.types import Message, RunResult, ToolSchema


@dataclass
class AgentManifest:
    """Loaded bundle manifest."""

    name: str
    system_prompt: str
    agents_dir: Path
    limits: Any = None
    model: str = "qwen"
    grammar_config: DecodingConstraint | None = None
    max_turns: int = 20


def load_manifest(bundle_path: str | Path) -> AgentManifest:
    """Load a bundle manifest from a YAML file."""
    path = Path(bundle_path)
    if path.is_dir():
        path = path / "bundle.yaml"

    with open(path) as f:
        data = yaml.safe_load(f)

    return AgentManifest(
        name=data.get("name", "unnamed"),
        system_prompt=data.get("system_prompt", ""),
        agents_dir=Path(bundle_path).parent / data.get("agents_dir", "agents"),
        limits=data.get("limits"),
        model=data.get("model", "qwen"),
        grammar_config=None,
        max_turns=data.get("max_turns", 20),
    )


class Agent:
    """A ready-to-run agent. The top-level user-facing API."""

    def __init__(
        self,
        kernel: AgentKernel,
        manifest: AgentManifest,
        observer: Observer | None = None,
    ):
        self.kernel = kernel
        self.manifest = manifest
        self.observer = observer or NullObserver()

    @classmethod
    async def from_bundle(cls, path: str | Path, **overrides) -> "Agent":
        """Load a bundle and construct a fully wired agent."""
        manifest = load_manifest(path)

        tools = discover_tools(str(manifest.agents_dir))

        adapter = ModelAdapter(
            name=manifest.model,
            grammar_builder=lambda t, c: None,
            response_parser=QwenResponseParser(),
        )

        client = build_client(
            {
                "model": manifest.model,
                "base_url": "http://localhost:8000/v1",
                "api_key": "EMPTY",
            }
        )

        kernel = AgentKernel(
            client=client,
            adapter=adapter,
            tools=tools,
        )

        return cls(kernel, manifest)

    async def run(self, user_input: str, **kwargs) -> RunResult:
        """Run the agent with a user message."""
        messages = [
            Message(role="system", content=self.manifest.system_prompt),
            Message(role="user", content=user_input),
        ]

        tool_schemas = [t.schema for t in self.kernel.tools]

        return await self.kernel.run(
            messages,
            tool_schemas,
            max_turns=kwargs.get("max_turns", self.manifest.max_turns),
        )

    async def close(self) -> None:
        await self.kernel.close()
