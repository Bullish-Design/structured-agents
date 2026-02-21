"""Bundle loading and management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template

from structured_agents.bundles.schema import BundleManifest, ToolDefinition
from structured_agents.exceptions import BundleError
from structured_agents.plugins import FunctionGemmaPlugin, ModelPlugin, QwenPlugin
from structured_agents.types import Message, ToolSchema


class AgentBundle:
    """A loaded agent bundle with tools, prompts, and configuration."""

    def __init__(self, path: Path, manifest: BundleManifest) -> None:
        self.path = path
        self.manifest = manifest
        self._tool_schemas: list[ToolSchema] | None = None
        self._system_template = Template(manifest.initial_context.system_prompt)
        self._user_template = Template(manifest.initial_context.user_template)

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def max_turns(self) -> int:
        return self.manifest.max_turns

    @property
    def termination_tool(self) -> str:
        return self.manifest.termination_tool

    def get_plugin(self) -> ModelPlugin:
        """Get the appropriate model plugin for this bundle."""
        plugin_name = self.manifest.model.plugin.lower()

        if plugin_name == "function_gemma":
            return FunctionGemmaPlugin()
        if plugin_name == "qwen":
            return QwenPlugin()
        raise BundleError(f"Unknown plugin: {plugin_name}")

    @property
    def tool_schemas(self) -> list[ToolSchema]:
        """Get tool schemas for this bundle."""
        if self._tool_schemas is None:
            self._tool_schemas = self._build_tool_schemas()
        return self._tool_schemas

    def _build_tool_schemas(self) -> list[ToolSchema]:
        """Build tool schemas from manifest."""
        schemas: list[ToolSchema] = []
        for tool_def in self.manifest.tools:
            properties: dict[str, Any] = {}
            required: list[str] = []

            for name, input_schema in tool_def.inputs.items():
                prop: dict[str, Any] = {"type": input_schema.type}
                if input_schema.description:
                    prop["description"] = input_schema.description
                if input_schema.enum:
                    prop["enum"] = input_schema.enum
                if input_schema.default is not None:
                    prop["default"] = input_schema.default
                properties[name] = prop

                if input_schema.required:
                    required.append(name)

            parameters: dict[str, Any] = {
                "type": "object",
                "properties": properties,
            }
            if required:
                parameters["required"] = required

            script_path = self.path / tool_def.script
            context_providers = tuple(
                self.path / cp for cp in tool_def.context_providers
            )

            schemas.append(
                ToolSchema(
                    name=tool_def.name,
                    description=tool_def.description,
                    parameters=parameters,
                    script_path=script_path,
                    context_providers=context_providers,
                )
            )

        return schemas

    def build_initial_messages(
        self,
        context: dict[str, Any] | None = None,
    ) -> list[Message]:
        """Build initial messages from templates.

        Args:
            context: Variables to render in templates.
                     Common variables: node_text, input, etc.
        """
        context = context or {}

        system_prompt = self._system_template.render(**context)
        user_message = self._user_template.render(**context)

        return [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Render the system prompt with context."""
        context = context or {}
        return self._system_template.render(**context)


def load_bundle(directory: str | Path) -> AgentBundle:
    """Load an agent bundle from a directory.

    Args:
        directory: Path to bundle directory containing bundle.yaml

    Returns:
        Loaded AgentBundle

    Raises:
        BundleError: If bundle is invalid or cannot be loaded
    """
    path = Path(directory)

    if not path.is_dir():
        raise BundleError(f"Bundle path is not a directory: {path}")

    manifest_path = path / "bundle.yaml"
    if not manifest_path.exists():
        manifest_path = path / "bundle.yml"
        if not manifest_path.exists():
            raise BundleError(f"Bundle manifest not found in {path}")

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        raise BundleError(f"Failed to read bundle manifest: {exc}") from exc

    try:
        manifest = BundleManifest(**data)
    except Exception as exc:
        raise BundleError(f"Invalid bundle manifest: {exc}") from exc

    return AgentBundle(path, manifest)
