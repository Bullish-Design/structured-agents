# Structured-Agents v2: Refactoring Plan

## Overview

This document provides a comprehensive refactoring plan for structured-agents v2, designed to fully leverage vLLM's XGrammar capabilities (including structural tags) and support multiple tool sources (Grail, Python, MCP). The plan prioritizes clean architecture over backwards compatibility.

---

## Part 1: Issues Identified in Current Implementation

### Critical Issues

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | vLLM payload missing `type` field | `plugins/function_gemma.py:132-135` | Grammar constraints may not apply |
| 2 | Test expects legacy `guided_grammar` format | `tests/test_plugins/test_function_gemma.py:78` | Test fails against correct implementation |
| 3 | No tool name escaping in EBNF | `plugins/grammar/function_gemma.py:25-26` | Invalid grammar for names with special chars |
| 4 | Single tool call only (`root ::= function_call`) | `plugins/grammar/function_gemma.py:28` | Blocks FunctionGemma parallel calls |
| 5 | Fragile argument grammar (`[^}]`) | `plugins/grammar/function_gemma.py:35-37` | No braces in args, no `<escape>` support |

### Architectural Gaps

| # | Gap | Location | Impact |
|---|-----|----------|--------|
| 6 | Dead `grammar_strategy` field | `bundles/schema.py:35` | Confusing, never consumed |
| 7 | Hard-coded plugin selection | `bundles/loader.py:39-47` | Can't add plugins without core changes |
| 8 | No tool registry abstraction | `bundles/loader.py:56-98` | Bundle duplicates schemas, can't use MCP/Python |
| 9 | Grammar returns raw string | `plugins/protocol.py:53` | Can't represent structural tags |
| 10 | Bundle schema != example bundles | `bundles/schema.py` vs `.context/grail_agent_examples/` | Field name mismatches |

### Missing Capabilities

| # | Capability | Why Needed |
|---|------------|------------|
| 11 | Structural tag support | vLLM optimization for tool calling |
| 12 | Multiple tool registries | Support Grail, Python callables, MCP servers |
| 13 | Grammar capability negotiation | Different models support different constraint types |
| 14 | Proper FunctionGemma `<escape>` handling | Required for string arguments |

---

## Part 2: Target Architecture

### Design Principles

1. **Composition over inheritance** - Use protocols and composition, not class hierarchies
2. **Explicit over implicit** - No magic; configuration is clear and typed
3. **Separation of concerns** - Registries resolve tools, backends execute them, plugins format for models
4. **vLLM-native** - Design around vLLM's batched inference and XGrammar capabilities

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Bundle (YAML)                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Prompts   │  │   Tools     │  │  Grammar    │  │  Model Config       │ │
│  │  (Jinja2)   │  │  (by name)  │  │   Config    │  │  (plugin + opts)    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
         │  ToolRegistry    │ │ PluginRegistry│ │  BackendRegistry │
         │  (composite)     │ │              │ │   (composite)    │
         └──────────────────┘ └──────────────┘ └──────────────────┘
                    │                 │                 │
      ┌─────────────┼─────────────┐   │   ┌─────────────┼─────────────┐
      ▼             ▼             ▼   │   ▼             ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐│┌──────────┐ ┌──────────┐ ┌──────────┐
│  Grail   │ │  Python  │ │   MCP    │││  Grail   │ │  Python  │ │   MCP    │
│ Registry │ │ Registry │ │ Registry │││ Backend  │ │ Backend  │ │ Backend  │
└──────────┘ └──────────┘ └──────────┘│└──────────┘ └──────────┘ └──────────┘
      │             │             │   │       │           │           │
      └─────────────┴─────────────┘   │       └───────────┴───────────┘
                    │                 │                   │
                    ▼                 ▼                   │
         ┌──────────────────────────────────────┐        │
         │           AgentKernel                │        │
         │  ┌────────────────────────────────┐  │        │
         │  │  tools: list[ToolSchema]       │◄─┼────────┘
         │  │  plugin: ModelPlugin           │  │
         │  │  backend: ToolBackend          │  │
         │  └────────────────────────────────┘  │
         │                 │                    │
         │                 ▼                    │
         │  ┌────────────────────────────────┐  │
         │  │  plugin.build_grammar(tools)   │  │
         │  │         │                      │  │
         │  │         ▼                      │  │
         │  │  GrammarArtifact               │  │
         │  │    ├─ EBNF(str)                │  │
         │  │    ├─ StructuralTag(...)       │  │
         │  │    └─ JsonSchema(dict)         │  │
         │  │         │                      │  │
         │  │         ▼                      │  │
         │  │  plugin.to_extra_body(artifact)│  │
         │  │         │                      │  │
         │  │         ▼                      │  │
         │  │  {"structured_outputs": {...}} │  │
         │  └────────────────────────────────┘  │
         │                 │                    │
         │                 ▼                    │
         │          LLMClient (vLLM)            │
         └──────────────────────────────────────┘
```

### Module Layout

```
structured_agents/
├── __init__.py                    # Public API
├── types.py                       # Core types (Message, ToolCall, ToolResult, etc.)
├── kernel.py                      # AgentKernel
├── exceptions.py                  # Exception hierarchy
├── history.py                     # History strategies
│
├── grammar/                       # Grammar system
│   ├── __init__.py
│   ├── artifacts.py               # GrammarArtifact types
│   ├── config.py                  # GrammarConfig
│   ├── builders/
│   │   ├── __init__.py
│   │   ├── protocol.py            # GrammarBuilder protocol
│   │   ├── function_gemma.py      # FunctionGemma EBNF + structural tags
│   │   └── json_schema.py         # JSON schema utilities
│   └── utils.py                   # EBNF escaping, validation
│
├── plugins/                       # Model plugins
│   ├── __init__.py
│   ├── protocol.py                # ModelPlugin protocol
│   ├── registry.py                # Plugin registry
│   ├── function_gemma.py          # FunctionGemma plugin
│   └── qwen.py                    # Qwen plugin
│
├── registries/                    # Tool registries
│   ├── __init__.py
│   ├── protocol.py                # ToolRegistry protocol
│   ├── composite.py               # CompositeRegistry
│   ├── grail.py                   # GrailRegistry
│   ├── python.py                  # PythonRegistry
│   └── mcp.py                     # MCPRegistry
│
├── backends/                      # Tool execution
│   ├── __init__.py
│   ├── protocol.py                # ToolBackend protocol
│   ├── composite.py               # CompositeBackend
│   ├── grail.py                   # GrailBackend
│   ├── python.py                  # PythonBackend
│   └── mcp.py                     # MCPBackend
│
├── client/                        # LLM client
│   ├── __init__.py
│   ├── protocol.py                # LLMClient protocol
│   └── openai_compat.py           # OpenAI-compatible client
│
├── bundles/                       # Bundle system
│   ├── __init__.py
│   ├── schema.py                  # Bundle manifest schema
│   └── loader.py                  # Bundle loading
│
└── observer/                      # Event system (unchanged)
    ├── __init__.py
    ├── protocol.py
    ├── events.py
    ├── null.py
    └── composite.py
```

---

## Part 3: Core Abstractions

### 3.1 Startup Dependency Check

```python
# structured_agents/deps.py
from __future__ import annotations


def require_xgrammar_and_vllm() -> None:
    """Fail fast if required grammar dependencies are missing."""
    try:
        import vllm  # noqa: F401
        import xgrammar  # noqa: F401
    except ImportError as exc:
        message = (
            "Missing required dependencies: vllm and xgrammar. "
            "Install them to use structured-agents v2."
        )
        raise RuntimeError(message) from exc
```

Call `require_xgrammar_and_vllm()` once at startup (e.g., in `structured_agents/__init__.py` or kernel initialization). Remove all runtime try/except fallbacks that mask missing dependencies.

### 3.2 Grammar Artifacts

```python
# grammar/artifacts.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from xgrammar import StructuralTag


@dataclass(frozen=True, slots=True)
class EBNFGrammar:
    """EBNF grammar string for XGrammar."""

    grammar: str

    def to_vllm_payload(self) -> dict[str, Any]:
        return {
            "structured_outputs": {
                "type": "grammar",
                "grammar": self.grammar,
            }
        }


@dataclass(frozen=True, slots=True)
class StructuralTagGrammar:
    """XGrammar structural tag for optimized tool calling."""

    tag: StructuralTag

    def to_vllm_payload(self) -> dict[str, Any]:
        return {
            "structured_outputs": {
                "type": "structural_tag",
                "structural_tag": self.tag,
            }
        }


@dataclass(frozen=True, slots=True)
class JsonSchemaGrammar:
    """JSON schema constraint."""

    schema: dict[str, Any]

    def to_vllm_payload(self) -> dict[str, Any]:
        return {
            "structured_outputs": {
                "type": "json_schema",
                "json_schema": self.schema,
            }
        }


# Union type for all grammar artifacts
GrammarArtifact = EBNFGrammar | StructuralTagGrammar | JsonSchemaGrammar | None
```

### 3.3 Grammar Configuration

```python
# grammar/config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GrammarConfig:
    """Configuration for grammar generation."""

    # Output mode
    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"

    # Tool call options
    allow_parallel_calls: bool = True

    # Argument handling
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"

```

### 3.4 Grammar Builder Protocol

```python
# grammar/builders/protocol.py
from __future__ import annotations

from typing import Protocol

from structured_agents.grammar.artifacts import GrammarArtifact
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


class GrammarBuilder(Protocol):
    """Protocol for building grammar artifacts from tool schemas."""

    def build(
        self,
        tools: list[ToolSchema],
        config: GrammarConfig,
    ) -> GrammarArtifact:
        """Build a grammar artifact for the given tools.

        Args:
            tools: Available tool schemas.
            config: Grammar configuration.

        Returns:
            Grammar artifact (EBNF, structural tag, or JSON schema).
        """
        ...

    def supports_mode(self, mode: str) -> bool:
        """Check if this builder supports the given mode."""
        ...
```

### 3.5 FunctionGemma Grammar Builder

```python
# grammar/builders/function_gemma.py
from __future__ import annotations

from structured_agents.grammar.artifacts import (
    EBNFGrammar,
    GrammarArtifact,
    StructuralTagGrammar,
)
from structured_agents.grammar.config import GrammarConfig
from structured_agents.grammar.utils import escape_ebnf_string
from structured_agents.types import ToolSchema

from xgrammar import StructuralTag
from xgrammar.structural_tag import GrammarFormat, OrFormat, SequenceFormat, TagFormat


class FunctionGemmaGrammarBuilder:
    """Grammar builder for FunctionGemma models."""

    def supports_mode(self, mode: str) -> bool:
        return mode in ("ebnf", "structural_tag", "permissive")

    def build(
        self,
        tools: list[ToolSchema],
        config: GrammarConfig,
    ) -> GrammarArtifact:
        if not tools:
            return None

        if config.mode == "structural_tag":
            return self._build_structural_tag(tools, config)

        return self._build_ebnf(tools, config)

    def _build_ebnf(
        self,
        tools: list[ToolSchema],
        config: GrammarConfig,
    ) -> EBNFGrammar:
        """Build EBNF grammar for FunctionGemma format."""
        tool_names = [escape_ebnf_string(tool.name) for tool in tools]
        tool_alts = " | ".join(f'"{name}"' for name in tool_names)

        # Root rule: single or multiple calls
        if config.allow_parallel_calls:
            root_rule = "root ::= function_call+"
        else:
            root_rule = "root ::= function_call"

        # Argument body based on format
        if config.args_format == "escaped_strings":
            arg_body = self._escaped_string_args_grammar()
        elif config.args_format == "json":
            arg_body = self._json_args_grammar()
        else:
            arg_body = "arg_body ::= [^}]*"

        grammar = "\n".join([
            root_rule,
            "",
            'function_call ::= "<start_function_call>" "call:" tool_name "{" arg_body "}" "<end_function_call>"',
            "",
            f"tool_name ::= {tool_alts}",
            "",
            arg_body,
        ])

        return EBNFGrammar(grammar=grammar)

    def _build_structural_tag(
        self,
        tools: list[ToolSchema],
        config: GrammarConfig,
    ) -> StructuralTagGrammar:
        """Build structural tag for FunctionGemma format."""
        tool_formats = []

        for tool in tools:
            # Build argument grammar for this tool
            args_grammar = self._build_args_grammar_for_tool(tool, config)

            tool_formats.append(
                TagFormat(
                    begin=f"<start_function_call>call:{tool.name}{{",
                    content=GrammarFormat(grammar=args_grammar),
                    end="}<end_function_call>",
                )
            )

        # Combine tool formats
        if len(tool_formats) == 1:
            format_spec = tool_formats[0]
        else:
            format_spec = OrFormat(elements=tool_formats)

        # Wrap for parallel calls if needed
        if config.allow_parallel_calls:
            format_spec = SequenceFormat(
                elements=[format_spec],
                min_elements=1,
                max_elements=None,  # Unlimited
            )

        tag = StructuralTag(format=format_spec)

        return StructuralTagGrammar(tag=tag)

    def _build_args_grammar_for_tool(
        self,
        tool: ToolSchema,
        config: GrammarConfig,
    ) -> str:
        """Build argument grammar for a specific tool."""
        # For now, permissive args
        # TODO: Generate per-parameter constraints from tool.parameters
        return "[^}]*"

    def _escaped_string_args_grammar(self) -> str:
        """Grammar supporting FunctionGemma <escape> delimiters."""
        return "\n".join([
            "arg_body ::= (arg_pair (\",\" arg_pair)*)?",
            "arg_pair ::= arg_name \":\" arg_value",
            "arg_name ::= [a-zA-Z_][a-zA-Z0-9_]*",
            'arg_value ::= escaped_string | number | "true" | "false" | "null"',
            'escaped_string ::= "<escape>" [^<]* "<escape>"',
            "number ::= \"-\"? [0-9]+ (\".\" [0-9]+)?",
        ])

    def _json_args_grammar(self) -> str:
        """Grammar for JSON-formatted arguments."""
        return "\n".join([
            "arg_body ::= (pair (\",\" pair)*)?",
            "pair ::= string \":\" value",
            'string ::= \"\\"\" [^\\"]* \"\\"\\"',
            "value ::= string | number | object | array | \"true\" | \"false\" | \"null\"",
            'object ::= \"{\" (pair (\",\" pair)*)? \"}\"',
            'array ::= \"[\" (value (\",\" value)*)? \"]\"',
            "number ::= \"-\"? [0-9]+ (\".\" [0-9]+)?",
        ])
```

### 3.6 Grammar Utilities

```python
# grammar/utils.py
from __future__ import annotations


def escape_ebnf_string(value: str) -> str:
    """Escape special characters for EBNF string literals.

    Args:
        value: Raw string value.

    Returns:
        Escaped string safe for use in EBNF.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def validate_ebnf(grammar: str) -> list[str]:
    """Validate EBNF grammar syntax.

    Args:
        grammar: EBNF grammar string.

    Returns:
        List of error messages (empty if valid).
    """
    try:
        from xgrammar.testing import _get_matcher_from_grammar
        _get_matcher_from_grammar(grammar)
        return []
    except Exception as e:
        return [str(e)]
```

### 3.7 Tool Registry Protocol

```python
# registries/protocol.py
from __future__ import annotations

from typing import Protocol

from structured_agents.types import ToolSchema


class ToolRegistry(Protocol):
    """Protocol for resolving tool schemas from a source."""

    @property
    def name(self) -> str:
        """Registry identifier."""
        ...

    def list_tools(self) -> list[str]:
        """List all available tool names."""
        ...

    def resolve(self, tool_name: str) -> ToolSchema | None:
        """Resolve a single tool by name.

        Args:
            tool_name: Name of the tool to resolve.

        Returns:
            ToolSchema if found, None otherwise.
        """
        ...

    def resolve_all(self, tool_names: list[str]) -> list[ToolSchema]:
        """Resolve multiple tools by name.

        Args:
            tool_names: Names of tools to resolve.

        Returns:
            List of resolved ToolSchemas (excludes tools not found).
        """
        ...
```

### 3.8 Grail Registry

```python
# registries/grail.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from structured_agents.types import ToolSchema

logger = logging.getLogger(__name__)


@dataclass
class GrailRegistryConfig:
    """Configuration for Grail tool registry."""

    agents_dir: Path = field(default_factory=lambda: Path.cwd() / "agents")
    use_grail_check: bool = False  # Run grail check to generate inputs.json
    cache_schemas: bool = True


class GrailRegistry:
    """Registry that resolves tools from Grail .pym scripts."""

    def __init__(self, config: GrailRegistryConfig | None = None) -> None:
        self._config = config or GrailRegistryConfig()
        self._cache: dict[str, ToolSchema] = {}
        self._scanned = False

    @property
    def name(self) -> str:
        return "grail"

    def list_tools(self) -> list[str]:
        """List all .pym tools in the agents directory."""
        self._scan_if_needed()
        return list(self._cache.keys())

    def resolve(self, tool_name: str) -> ToolSchema | None:
        """Resolve a Grail tool by name."""
        self._scan_if_needed()
        return self._cache.get(tool_name)

    def resolve_all(self, tool_names: list[str]) -> list[ToolSchema]:
        """Resolve multiple Grail tools."""
        self._scan_if_needed()
        return [self._cache[name] for name in tool_names if name in self._cache]

    def _scan_if_needed(self) -> None:
        """Scan agents directory if not already done."""
        if self._scanned and self._config.cache_schemas:
            return

        self._cache.clear()

        if not self._config.agents_dir.exists():
            logger.warning("Agents directory not found: %s", self._config.agents_dir)
            return

        for pym_path in self._config.agents_dir.rglob("*.pym"):
            try:
                schema = self._load_tool_schema(pym_path)
                if schema:
                    self._cache[schema.name] = schema
            except Exception as e:
                logger.warning("Failed to load %s: %s", pym_path, e)

        self._scanned = True

    def _load_tool_schema(self, pym_path: Path) -> ToolSchema | None:
        """Load tool schema from .pym file and its .grail artifacts."""
        tool_name = pym_path.stem

        # Try to find inputs.json in .grail directory
        grail_dir = pym_path.parent / ".grail" / tool_name
        inputs_json = grail_dir / "inputs.json"

        if inputs_json.exists():
            return self._schema_from_inputs_json(tool_name, pym_path, inputs_json)

        # Fallback: run grail check if enabled
        if self._config.use_grail_check:
            return self._schema_from_grail_check(tool_name, pym_path)

        # Minimal schema from just the .pym file
        return ToolSchema(
            name=tool_name,
            description=f"Grail tool: {tool_name}",
            parameters={"type": "object", "properties": {}},
            script_path=pym_path,
            backend="grail",
        )

    def _schema_from_inputs_json(
        self,
        tool_name: str,
        pym_path: Path,
        inputs_json: Path,
    ) -> ToolSchema:
        """Build schema from grail-generated inputs.json."""
        with inputs_json.open() as f:
            inputs = json.load(f)

        # Convert Grail inputs format to JSON Schema
        properties: dict[str, Any] = {}
        required: list[str] = []

        for input_name, input_spec in inputs.items():
            # Skip system-injected inputs
            if input_name.startswith("_"):
                continue

            prop: dict[str, Any] = {}

            if "type" in input_spec:
                prop["type"] = self._grail_type_to_json(input_spec["type"])
            if "description" in input_spec:
                prop["description"] = input_spec["description"]
            if "default" in input_spec:
                prop["default"] = input_spec["default"]
            else:
                required.append(input_name)

            properties[input_name] = prop

        parameters: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return ToolSchema(
            name=tool_name,
            description=inputs.get("_description", f"Grail tool: {tool_name}"),
            parameters=parameters,
            script_path=pym_path,
            backend="grail",
        )

    def _schema_from_grail_check(
        self,
        tool_name: str,
        pym_path: Path,
    ) -> ToolSchema | None:
        """Run grail check and parse outputs."""
        import subprocess

        try:
            result = subprocess.run(
                ["grail", "check", str(pym_path), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                check_output = json.loads(result.stdout)
                # Parse check output into schema
                # ... implementation depends on grail check output format
        except Exception as e:
            logger.warning("grail check failed for %s: %s", pym_path, e)

        return None

    def _grail_type_to_json(self, grail_type: str) -> str:
        """Convert Grail type annotation to JSON Schema type."""
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }
        return type_map.get(grail_type, "string")
```

### 3.9 Python Registry

```python
# registries/python.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints

from structured_agents.types import ToolSchema


@dataclass
class PythonTool:
    """A registered Python callable as a tool."""

    name: str
    func: Callable[..., Any]
    description: str | None = None


class PythonRegistry:
    """Registry for Python callable tools."""

    def __init__(self) -> None:
        self._tools: dict[str, PythonTool] = {}

    @property
    def name(self) -> str:
        return "python"

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        description: str | None = None,
    ) -> None:
        """Register a Python callable as a tool.

        Args:
            name: Tool name.
            func: The callable to register.
            description: Optional description (defaults to docstring).
        """
        self._tools[name] = PythonTool(
            name=name,
            func=func,
            description=description or func.__doc__ or f"Python function: {name}",
        )

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def resolve(self, tool_name: str) -> ToolSchema | None:
        tool = self._tools.get(tool_name)
        if not tool:
            return None
        return self._build_schema(tool)

    def resolve_all(self, tool_names: list[str]) -> list[ToolSchema]:
        return [
            self._build_schema(self._tools[name])
            for name in tool_names
            if name in self._tools
        ]

    def get_callable(self, tool_name: str) -> Callable[..., Any] | None:
        """Get the registered callable for a tool."""
        tool = self._tools.get(tool_name)
        return tool.func if tool else None

    def _build_schema(self, tool: PythonTool) -> ToolSchema:
        """Build ToolSchema from function signature."""
        sig = inspect.signature(tool.func)
        hints = get_type_hints(tool.func) if hasattr(tool.func, "__annotations__") else {}

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            prop: dict[str, Any] = {"type": self._python_type_to_json(hints.get(param_name))}

            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            else:
                prop["default"] = param.default

            properties[param_name] = prop

        parameters: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return ToolSchema(
            name=tool.name,
            description=tool.description or "",
            parameters=parameters,
            backend="python",
        )

    def _python_type_to_json(self, python_type: Any) -> str:
        """Convert Python type hint to JSON Schema type."""
        if python_type is None:
            return "string"

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        origin = getattr(python_type, "__origin__", python_type)
        return type_map.get(origin, "string")
```

### 3.10 Composite Registry

```python
# registries/composite.py
from __future__ import annotations

from structured_agents.registries.protocol import ToolRegistry
from structured_agents.types import ToolSchema


class CompositeRegistry:
    """Registry that combines multiple registries."""

    def __init__(self, registries: list[ToolRegistry] | None = None) -> None:
        self._registries: list[ToolRegistry] = registries or []

    @property
    def name(self) -> str:
        return "composite"

    def add(self, registry: ToolRegistry) -> None:
        """Add a registry to the composite."""
        self._registries.append(registry)

    def list_tools(self) -> list[str]:
        """List all tools from all registries."""
        tools: list[str] = []
        seen: set[str] = set()

        for registry in self._registries:
            for tool_name in registry.list_tools():
                if tool_name not in seen:
                    tools.append(tool_name)
                    seen.add(tool_name)

        return tools

    def resolve(self, tool_name: str) -> ToolSchema | None:
        """Resolve from first registry that has the tool."""
        for registry in self._registries:
            schema = registry.resolve(tool_name)
            if schema:
                return schema
        return None

    def resolve_all(self, tool_names: list[str]) -> list[ToolSchema]:
        """Resolve all tools, preferring earlier registries."""
        resolved: dict[str, ToolSchema] = {}

        for name in tool_names:
            if name not in resolved:
                schema = self.resolve(name)
                if schema:
                    resolved[name] = schema

        # Preserve order
        return [resolved[name] for name in tool_names if name in resolved]
```

### 3.11 Updated ToolSchema

```python
# types.py (updated ToolSchema)
@dataclass(frozen=True, slots=True)
class ToolSchema:
    """Schema for a tool, with execution metadata."""

    name: str
    description: str
    parameters: dict[str, Any]

    # Execution metadata
    backend: str = "python"  # "grail", "python", "mcp"
    script_path: Path | None = None  # For Grail
    context_providers: tuple[Path, ...] = ()  # For Grail
    mcp_server: str | None = None  # For MCP

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tools array format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
```

### 3.12 Updated Model Plugin Protocol

```python
# plugins/protocol.py
from __future__ import annotations

from typing import Any, Protocol

from structured_agents.grammar.artifacts import GrammarArtifact
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import Message, ToolCall, ToolSchema


class ModelPlugin(Protocol):
    """Protocol for model-specific formatting and parsing."""

    @property
    def name(self) -> str:
        """Plugin identifier."""
        ...

    @property
    def supports_ebnf(self) -> bool:
        """Whether this model supports EBNF grammar constraints."""
        ...

    @property
    def supports_structural_tags(self) -> bool:
        """Whether this model supports XGrammar structural tags."""
        ...

    @property
    def supports_json_schema(self) -> bool:
        """Whether this model supports JSON schema constraints."""
        ...

    def format_messages(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> list[dict[str, Any]]:
        """Convert messages to model API format."""
        ...

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Convert tool schemas to API format."""
        ...

    def build_grammar(
        self,
        tools: list[ToolSchema],
        config: GrammarConfig,
    ) -> GrammarArtifact:
        """Build grammar artifact for the given tools and config."""
        ...

    def to_extra_body(
        self,
        artifact: GrammarArtifact,
    ) -> dict[str, Any] | None:
        """Convert grammar artifact to vLLM extra_body payload."""
        ...

    def parse_response(
        self,
        content: str | None,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Parse model response into content and tool calls."""
        ...
```

### 3.13 Updated FunctionGemma Plugin

```python
# plugins/function_gemma.py
from __future__ import annotations

import json
import logging
import re
from typing import Any

from structured_agents.grammar.artifacts import (
    EBNFGrammar,
    GrammarArtifact,
    StructuralTagGrammar,
)
from structured_agents.grammar.builders.function_gemma import FunctionGemmaGrammarBuilder
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import Message, ToolCall, ToolSchema

logger = logging.getLogger(__name__)


class FunctionGemmaPlugin:
    """Plugin for Google's FunctionGemma models."""

    name = "function_gemma"
    supports_ebnf = True
    supports_structural_tags = True
    supports_json_schema = False

    _TOOL_CALL_PATTERN = re.compile(
        r"<start_function_call>call:([a-zA-Z_][a-zA-Z0-9_-]*)\{([^}]*)\}<end_function_call>"
    )

    def __init__(self) -> None:
        self._grammar_builder = FunctionGemmaGrammarBuilder()

    def format_messages(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> list[dict[str, Any]]:
        """Format messages for FunctionGemma."""
        return [msg.to_openai_format() for msg in messages]

    def format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Format tools for the API."""
        return [tool.to_openai_format() for tool in tools]

    def build_grammar(
        self,
        tools: list[ToolSchema],
        config: GrammarConfig,
    ) -> GrammarArtifact:
        """Build grammar artifact for FunctionGemma."""
        return self._grammar_builder.build(tools, config)

    def to_extra_body(
        self,
        artifact: GrammarArtifact,
    ) -> dict[str, Any] | None:
        """Convert grammar artifact to vLLM payload."""
        if artifact is None:
            return None

        if isinstance(artifact, EBNFGrammar):
            return artifact.to_vllm_payload()

        if isinstance(artifact, StructuralTagGrammar):
            return artifact.to_vllm_payload()

        raise ValueError(f"Unsupported artifact type: {type(artifact)}")

    def parse_response(
        self,
        content: str | None,
        tool_calls_raw: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Parse FunctionGemma response."""
        tool_calls: list[ToolCall] = []

        # Try standard OpenAI format first
        if tool_calls_raw:
            for tc in tool_calls_raw:
                try:
                    func = tc.get("function", {})
                    args_str = func.get("arguments", "{}")
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", f"call_{id(tc)}"),
                            name=func.get("name", "unknown"),
                            arguments=args,
                        )
                    )
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Failed to parse tool call: %s", exc)
            return content, tool_calls

        # Parse grammar-constrained format from content
        if content:
            matches = self._TOOL_CALL_PATTERN.findall(content)
            for name, args_str in matches:
                args = self._parse_arguments(args_str)
                tool_calls.append(ToolCall.create(name=name, arguments=args))

            if tool_calls:
                return None, tool_calls

        return content, tool_calls

    def _parse_arguments(self, args_str: str) -> dict[str, Any]:
        """Parse FunctionGemma argument format."""
        args: dict[str, Any] = {}

        if not args_str.strip():
            return args

        # Try JSON first
        try:
            json_str = "{" + args_str + "}" if not args_str.startswith("{") else args_str
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Parse <escape> delimited strings
        # Pattern: key:<escape>value<escape> or key:value
        escape_pattern = re.compile(r"(\w+):(?:<escape>([^<]*)<escape>|([^,}]+))")

        for match in escape_pattern.finditer(args_str):
            key = match.group(1)
            value = match.group(2) if match.group(2) is not None else match.group(3)

            # Try to parse as JSON value
            try:
                args[key] = json.loads(value)
            except json.JSONDecodeError:
                args[key] = value.strip().strip("\"'")

        return args
```

### 3.14 Plugin Registry

```python
# plugins/registry.py
from __future__ import annotations

from typing import Type

from structured_agents.plugins.function_gemma import FunctionGemmaPlugin
from structured_agents.plugins.protocol import ModelPlugin
from structured_agents.plugins.qwen import QwenPlugin


class PluginRegistry:
    """Registry for model plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, Type[ModelPlugin]] = {
            "function_gemma": FunctionGemmaPlugin,
            "qwen": QwenPlugin,
        }

    def register(self, name: str, plugin_cls: Type[ModelPlugin]) -> None:
        """Register a plugin class."""
        self._plugins[name] = plugin_cls

    def get(self, name: str) -> ModelPlugin:
        """Get a plugin instance by name."""
        name_lower = name.lower()
        if name_lower not in self._plugins:
            available = ", ".join(self._plugins.keys())
            raise ValueError(f"Unknown plugin: {name}. Available: {available}")
        return self._plugins[name_lower]()

    def list_plugins(self) -> list[str]:
        """List available plugin names."""
        return list(self._plugins.keys())


# Global default registry
_default_registry = PluginRegistry()


def register_plugin(name: str, plugin_cls: Type[ModelPlugin]) -> None:
    """Register a plugin in the default registry."""
    _default_registry.register(name, plugin_cls)


def get_plugin(name: str) -> ModelPlugin:
    """Get a plugin from the default registry."""
    return _default_registry.get(name)
```

### 3.15 Composite Backend

```python
# backends/composite.py
from __future__ import annotations

from typing import Any

from structured_agents.backends.protocol import ToolBackend
from structured_agents.types import ToolCall, ToolResult, ToolSchema


class CompositeBackend:
    """Backend that routes execution to appropriate sub-backends."""

    def __init__(self) -> None:
        self._backends: dict[str, ToolBackend] = {}

    def register(self, backend_name: str, backend: ToolBackend) -> None:
        """Register a backend for a given type."""
        self._backends[backend_name] = backend

    async def execute(
        self,
        tool_call: ToolCall,
        tool_schema: ToolSchema,
        context: dict[str, Any],
    ) -> ToolResult:
        """Execute tool using appropriate backend."""
        backend = self._backends.get(tool_schema.backend)

        if not backend:
            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                output=f"No backend registered for: {tool_schema.backend}",
                is_error=True,
            )

        return await backend.execute(tool_call, tool_schema, context)

    async def run_context_providers(
        self,
        providers: list[Any],
        context: dict[str, Any],
    ) -> list[str]:
        """Run context providers using Grail backend."""
        grail_backend = self._backends.get("grail")
        if grail_backend:
            return await grail_backend.run_context_providers(providers, context)
        return []

    def supports_snapshots(self) -> bool:
        return all(b.supports_snapshots() for b in self._backends.values())

    def create_snapshot(self) -> Any:
        return {name: b.create_snapshot() for name, b in self._backends.items()}

    def restore_snapshot(self, snapshot: Any) -> None:
        for name, sub_snapshot in snapshot.items():
            if name in self._backends:
                self._backends[name].restore_snapshot(sub_snapshot)
```

### 3.16 Updated Bundle Schema

```python
# bundles/schema.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolReference(BaseModel):
    """Reference to a tool in a registry."""

    name: str
    registry: str = "grail"  # Which registry to resolve from

    # Optional overrides
    description: str | None = None
    inputs_override: dict[str, Any] | None = None
    context_providers: list[str] = Field(default_factory=list)


class GrammarSettings(BaseModel):
    """Grammar configuration for the bundle."""

    mode: str = "ebnf"  # "ebnf", "structural_tag", "json_schema"
    allow_parallel_calls: bool = True
    args_format: str = "permissive"  # "permissive", "escaped_strings", "json"


class ModelSettings(BaseModel):
    """Model configuration in a bundle."""

    plugin: str = "function_gemma"
    adapter: str | None = None
    grammar: GrammarSettings = Field(default_factory=GrammarSettings)


class InitialContext(BaseModel):
    """Initial prompts for the agent."""

    system_prompt: str
    user_template: str = "{{ input }}"


class BundleManifest(BaseModel):
    """The bundle.yaml schema."""

    name: str
    version: str = "1.0"

    model: ModelSettings = Field(default_factory=ModelSettings)
    initial_context: InitialContext

    max_turns: int = 20
    termination_tool: str = "submit_result"

    # Tool references (resolved via registries)
    tools: list[ToolReference]

    # Registry configuration
    registries: list[str] = Field(default_factory=lambda: ["grail"])
```

---

## Part 4: Implementation Phases

### Phase 1: Core Grammar System (2-3 days)

**Goal:** Implement the grammar abstraction layer.

**Tasks:**
1. Create `grammar/` package structure
2. Implement `GrammarArtifact` types (`EBNFGrammar`, `StructuralTagGrammar`, `JsonSchemaGrammar`)
3. Implement `GrammarConfig` dataclass
4. Implement `GrammarBuilder` protocol
5. Implement startup dependency check (`require_xgrammar_and_vllm`)
6. Implement `FunctionGemmaGrammarBuilder` with:
   - Fixed EBNF (escaping, parallel calls)
   - Structural tag support (always enabled)
7. Implement `grammar/utils.py` (escaping, validation)
8. Write tests for grammar generation

**Deliverables:**
- Working grammar builder that produces both EBNF and structural tags
- Tests validating grammar output against XGrammar

---

### Phase 2: Tool Registry System (2-3 days)

**Goal:** Implement the tool registry abstraction.

**Tasks:**
1. Create `registries/` package structure
2. Implement `ToolRegistry` protocol
3. Update `ToolSchema` with execution metadata (`backend`, `script_path`, etc.)
4. Implement `GrailRegistry`:
   - Scan agents directory for .pym files
   - Parse `.grail/.../inputs.json` when available
   - Optional `grail check` integration
5. Implement `PythonRegistry`:
   - Register callables with automatic schema generation
   - Type hint introspection for parameters
6. Implement `CompositeRegistry`
7. Write tests for all registries

**Deliverables:**
- Working registries for Grail and Python tools
- Composite registry for combining sources

---

### Phase 3: Plugin System Update (1-2 days)

**Goal:** Update plugins to use grammar artifacts.

**Tasks:**
1. Update `ModelPlugin` protocol with:
   - Capability properties (`supports_ebnf`, etc.)
   - Updated `build_grammar()` signature
   - New `to_extra_body()` method
2. Implement `PluginRegistry`
3. Update `FunctionGemmaPlugin`:
   - Use `FunctionGemmaGrammarBuilder`
   - Handle both EBNF and structural tag artifacts
   - Fix response parsing (support `<escape>`, parallel calls)
4. Update `QwenPlugin` for new protocol
5. Fix test at `test_function_gemma.py:78`
6. Write tests for plugin capabilities

**Deliverables:**
- Updated plugins using grammar artifacts
- All existing tests passing (or updated)

---

### Phase 4: Backend System Update (1-2 days)

**Goal:** Support multiple tool backends.

**Tasks:**
1. Update `ToolBackend` protocol if needed
2. Implement `CompositeBackend`
3. Update `PythonBackend` to use registry callables
4. Ensure `GrailBackend` works with new `ToolSchema`
5. Write tests for composite backend

**Deliverables:**
- Composite backend routing to appropriate sub-backends
- Tests for multi-backend scenarios

---

### Phase 5: Bundle System Update (1-2 days)

**Goal:** Simplify bundles to use registries.

**Tasks:**
1. Update `BundleManifest` schema:
   - `ToolReference` instead of inline definitions
   - `GrammarSettings` instead of dead `grammar_strategy`
   - Registry configuration
2. Update `AgentBundle` class:
   - Use `PluginRegistry.get()` instead of hard-coded if/else
   - Resolve tools via registries
   - Pass `GrammarConfig` to plugin
3. Update `load_bundle()` function
4. Migrate test fixtures to new schema
5. Write tests for bundle loading

**Deliverables:**
- Cleaner bundle schema
- Bundle loading via registries

---

### Phase 6: Kernel Integration (1 day)

**Goal:** Wire everything together in the kernel.

**Tasks:**
1. Update `AgentKernel` to:
   - Accept `CompositeRegistry` and `CompositeBackend`
   - Pass `GrammarConfig` to plugin
   - Use `plugin.to_extra_body()` for vLLM payload
2. Ensure all observer events still work
3. Write integration tests

**Deliverables:**
- Fully integrated kernel using new abstractions
- End-to-end tests passing

---

### Phase 7: MCP Registry (Optional, 2-3 days)

**Goal:** Add MCP (Model Context Protocol) support.

**Tasks:**
1. Implement `MCPRegistry`:
   - Connect to MCP server
   - Discover available tools
   - Generate `ToolSchema` from MCP tool definitions
2. Implement `MCPBackend`:
   - Execute tools via MCP protocol
   - Handle async responses
3. Write tests (may need MCP server mock)

**Deliverables:**
- Working MCP integration
- Tests with mocked MCP server

---

## Part 5: Migration Guide

Since backwards compatibility is not a concern, this is a clean break. Key changes:

### For Users

1. **Bundle schema changes:**
   ```yaml
   # Old
   tools:
     - name: "echo"
       script: "tools/echo.pym"
       description: "Echo input"
       inputs:
         message:
           type: "string"

   # New
   tools:
     - name: "echo"
       registry: "grail"  # Tool resolved from registry
   ```

2. **Plugin selection:**
   ```python
   # Old
   plugin = bundle.get_plugin()

   # New
   from structured_agents.plugins.registry import get_plugin
   plugin = get_plugin(bundle.manifest.model.plugin)
   ```

3. **Grammar configuration:**
   ```yaml
   # Old (dead code)
   model:
     grammar_strategy: "permissive"

   # New (actually used)
   model:
     grammar:
       mode: "structural_tag"
       allow_parallel_calls: true
   ```

### For Plugin Authors

1. Implement new protocol methods:
   - `supports_ebnf`, `supports_structural_tags`, `supports_json_schema`
   - `build_grammar(tools, config)` returning `GrammarArtifact`
   - `to_extra_body(artifact)` returning vLLM payload

2. Use grammar builders for EBNF generation

### For Registry Authors

1. Implement `ToolRegistry` protocol
2. Return `ToolSchema` with `backend` field set

---

## Part 6: Testing Strategy

### Unit Tests

- `test_grammar/` - Grammar artifact generation, EBNF validation
- `test_registries/` - Tool resolution from each registry type
- `test_plugins/` - Plugin formatting, parsing, grammar building
- `test_backends/` - Tool execution via each backend

### Integration Tests

- Bundle loading → registry resolution → kernel execution
- Grammar artifact → vLLM payload → response parsing
- Multi-backend execution (Grail + Python tools in same run)

### XGrammar Validation Tests

```python
def test_generated_grammar_accepts_valid_output():
    """Verify generated EBNF accepts valid FunctionGemma output."""
    from xgrammar.testing import _is_grammar_accept_string

    grammar = build_functiongemma_grammar(tools)
    valid_output = "<start_function_call>call:my_tool{arg:value}<end_function_call>"

    assert _is_grammar_accept_string(grammar.grammar, valid_output)
```

---

## Part 7: File Changes Summary

### New Files

```
grammar/
  __init__.py
  artifacts.py          # GrammarArtifact types
  config.py             # GrammarConfig
  utils.py              # Escaping, validation
  builders/
    __init__.py
    protocol.py         # GrammarBuilder protocol
    function_gemma.py   # FunctionGemma builder

registries/
  __init__.py
  protocol.py           # ToolRegistry protocol
  composite.py          # CompositeRegistry
  grail.py              # GrailRegistry
  python.py             # PythonRegistry
  mcp.py                # MCPRegistry (Phase 7)

backends/
  composite.py          # CompositeBackend

plugins/
  registry.py           # PluginRegistry
```

### Modified Files

```
types.py                # ToolSchema with backend field
plugins/protocol.py     # Updated ModelPlugin
plugins/function_gemma.py  # Use grammar builder
plugins/qwen.py         # Updated for new protocol
bundles/schema.py       # New schema with ToolReference
bundles/loader.py       # Use registries
kernel.py               # Wire new abstractions
```

### Deleted Files

```
plugins/grammar/function_gemma.py  # Moved to grammar/builders/
```

---

## Part 8: Success Criteria

1. **All tests pass** - Existing functionality preserved
2. **Structural tags work** - Can generate and use XGrammar structural tags
3. **Multiple registries** - Can resolve tools from Grail, Python, and (optionally) MCP
4. **Grammar is correct** - EBNF escapes names, supports parallel calls
5. **vLLM payload is correct** - Includes `type` field, structural tag support
6. **Clean architecture** - Clear separation of concerns, typed protocols
7. **No dead code** - All configuration fields are used

---

## Appendix: Example Bundle (New Schema)

```yaml
name: docstring_agent
version: "2.0"

model:
  plugin: function_gemma
  grammar:
    mode: structural_tag
    allow_parallel_calls: false
    args_format: escaped_strings

initial_context:
  system_prompt: |
    You are a model that can do function calling with the following functions.
    <task_description>You are a Python documentation tool.</task_description>
  user_template: |
    Document this code:
    {{ node_text }}

max_turns: 15
termination_tool: submit_result

registries:
  - grail
  - python

tools:
  - name: read_current_docstring
    registry: grail
  - name: read_type_hints
    registry: grail
  - name: write_docstring
    registry: grail
    context_providers:
      - docstring/context/docstring_style.pym
  - name: submit_result
    registry: grail
```
