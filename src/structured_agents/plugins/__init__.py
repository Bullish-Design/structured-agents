"""Model plugins for structured-agents."""

from structured_agents.plugins.function_gemma import FunctionGemmaPlugin
from structured_agents.plugins.protocol import ModelPlugin
from structured_agents.plugins.qwen import QwenPlugin

__all__ = [
    "ModelPlugin",
    "FunctionGemmaPlugin",
    "QwenPlugin",
]
