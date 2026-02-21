# structured-agents

Structured tool orchestration with grammar-constrained LLM outputs. `structured-agents` provides a focused, composable agent loop that integrates model calls, tool execution, and observable events without taking over workspace or multi-agent coordination.

## What This Library Is

- A minimal, reusable agent kernel for tool-calling workflows.
- A structured output pipeline that supports grammar-constrained decoding via XGrammar.
- A toolkit for bundling tools, prompts, and model configuration.
- A clean integration layer for Grail `.pym` tools and Python tool backends.

## What This Library Is Not

- A multi-agent orchestrator.
- A workspace or filesystem manager.
- A code discovery or parsing engine.

## Installation

```bash
pip install structured-agents
```

This package requires the Grail runtime to execute `.pym` scripts. Install dependencies with your project’s normal Python dependency workflow (pip/uv/poetry).

## Quick Start

```python
import asyncio

from structured_agents import (
    AgentKernel,
    FunctionGemmaPlugin,
    KernelConfig,
    Message,
    PythonBackend,
    ToolSchema,
)


async def main() -> None:
    config = KernelConfig(
        base_url="http://localhost:8000/v1",
        model="google/functiongemma-270m-it",
    )

    backend = PythonBackend()

    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    backend.register("greet", greet)

    kernel = AgentKernel(
        config=config,
        plugin=FunctionGemmaPlugin(),
        backend=backend,
    )

    result = await kernel.run(
        initial_messages=[Message(role="user", content="Greet Alice")],
        tools=[
            ToolSchema(
                name="greet",
                description="Greet someone",
                parameters={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
        ],
        max_turns=3,
    )

    print(result.final_message.content)
    await kernel.close()


if __name__ == "__main__":
    asyncio.run(main())
```

## Using Grail `.pym` Tools

`structured-agents` executes `.pym` scripts via `GrailBackend`.

```python
from pathlib import Path

from structured_agents import GrailBackend, GrailBackendConfig, ToolSchema

backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd()))

schema = ToolSchema(
    name="read_file",
    description="Read file contents",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    script_path=Path("tools/read_file.pym"),
)
```

## Bundles

Bundles package prompts, tool definitions, and model configuration into a directory with a `bundle.yaml`.

```python
from structured_agents import load_bundle

bundle = load_bundle("./bundles/docstring_writer")
plugin = bundle.get_plugin()
messages = bundle.build_initial_messages({"input": "Add a docstring"})

# Use `bundle.tool_schemas` with AgentKernel
```

## Observability

The kernel emits events during execution. Observers can stream logs, drive TUIs, or capture telemetry.

```python
from structured_agents import CompositeObserver, NullObserver

observer = CompositeObserver([NullObserver()])
```

## Common Patterns

- Prefer `PythonBackend` for lightweight unit tests and fast local tooling.
- Use `GrailBackend` for real tool execution with `.pym` scripts.
- Keep tool outputs concise to preserve context.
- Use a termination tool (e.g., `submit_result`) to end long-running loops.

## API Overview

- `AgentKernel`: core agent loop.
- `ModelPlugin`: model-specific formatting, parsing, and grammar.
- `ToolBackend`: tool execution strategy.
- `AgentBundle`: bundle loader and tool schema generator.
- `Observer`: event hooks for external integrations.

## Project Status

The library is actively evolving. The API is stable for the core agent loop, but new plugins/backends may be added.

## License

MIT
