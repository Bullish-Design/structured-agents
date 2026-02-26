"""structured-agents - Structured tool orchestration with grammar-constrained LLM outputs."""

from structured_agents.types import (
    Message,
    ToolCall,
    ToolResult,
    ToolSchema,
    TokenUsage,
    StepResult,
    RunResult,
)
from structured_agents.tools import Tool, GrailTool
from structured_agents.models import ModelAdapter, QwenResponseParser
from structured_agents.grammar import DecodingConstraint, ConstraintPipeline
from structured_agents.events import (
    Observer,
    NullObserver,
    Event,
    KernelStartEvent,
    KernelEndEvent,
    ModelRequestEvent,
    ModelResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnCompleteEvent,
)
from structured_agents.kernel import AgentKernel
from structured_agents.agent import Agent, AgentManifest
from structured_agents.client import LLMClient, OpenAICompatibleClient, build_client

__version__ = "0.3.0"

__all__ = [
    # Types
    "Message",
    "ToolCall",
    "ToolResult",
    "ToolSchema",
    "TokenUsage",
    "StepResult",
    "RunResult",
    # Tools
    "Tool",
    "GrailTool",
    # Models
    "ModelAdapter",
    "QwenResponseParser",
    # Grammar
    "DecodingConstraint",
    "ConstraintPipeline",
    # Events
    "Observer",
    "NullObserver",
    "Event",
    "KernelStartEvent",
    "KernelEndEvent",
    "ModelRequestEvent",
    "ModelResponseEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "TurnCompleteEvent",
    # Core
    "AgentKernel",
    "Agent",
    "AgentManifest",
    # Client
    "LLMClient",
    "OpenAICompatibleClient",
    "build_client",
]
