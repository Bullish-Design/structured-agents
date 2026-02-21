"""Bundle schema definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolInputSchema(BaseModel):
    """Schema for a tool input parameter."""

    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """Definition of a tool in a bundle."""

    name: str
    script: str
    description: str
    inputs: dict[str, ToolInputSchema] = Field(default_factory=dict)
    context_providers: list[str] = Field(default_factory=list)


class ModelConfig(BaseModel):
    """Model configuration in a bundle."""

    plugin: str = "function_gemma"
    adapter: str | None = None
    grammar_strategy: str = "permissive"


class InitialContext(BaseModel):
    """Initial context (prompts) in a bundle."""

    system_prompt: str
    user_template: str = "{{ input }}"


class BundleManifest(BaseModel):
    """The bundle.yaml schema."""

    name: str
    version: str = "1.0"

    model: ModelConfig = Field(default_factory=ModelConfig)
    initial_context: InitialContext

    max_turns: int = 20
    termination_tool: str = "submit_result"

    tools: list[ToolDefinition]

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate tool names in bundle")
        return tools
