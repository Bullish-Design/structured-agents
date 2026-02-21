# Developer Guide

This guide is for contributors working on the `structured-agents` codebase itself. It complements `ARCHITECTURE.md` with deeper implementation details, design philosophy, and coding patterns.

## Purpose

`structured-agents` is intentionally small and composable. The goal is to provide a reliable, typed core for agent loops without forcing decisions about UI, workspace management, or multi-agent coordination.

If you are integrating the library into an application, start with `README.md`. If you are modifying the library, start here and in `ARCHITECTURE.md`.

## Design Philosophy

- **Small surface area**: each module handles one responsibility.
- **Deterministic behavior**: predictable output, explicit configuration.
- **Typed interfaces**: protocols for extensibility and strict type checking.
- **Minimal side effects**: most components are pure or isolated.
- **Tool safety**: Grail `.pym` scripts execute in isolated processes.

## Architectural Reference

Read `ARCHITECTURE.md` first to understand how components fit together. This guide focuses on implementation specifics.

## Core Concepts

### Agent Kernel

The `AgentKernel` owns the turn-by-turn loop. It does not manage workspace state or orchestration. Key responsibilities:

- Prepare model input via `ModelPlugin`.
- Make API calls via `OpenAICompatibleClient`.
- Parse tool calls and execute them via `ToolBackend`.
- Trim history using `HistoryStrategy`.
- Emit observer events at each stage.

### Model Plugins

Plugins define how messages, tools, and grammar are formatted. They also parse raw responses back into `ToolCall` objects. Any new model integration should be added as a plugin and tested in isolation.

### Tool Backends

Backends execute tool calls. `GrailBackend` is the default production implementation. `PythonBackend` exists for tests and simple local tooling.

### Bundles

Bundles provide a deployable configuration format. The loader converts bundle definitions into `ToolSchema` objects and uses Jinja2 templates for prompt rendering.

### Observers

Observers allow external integrations to observe the kernel lifecycle. Observers must be async and non-blocking. Use `CompositeObserver` to multiplex events.

## Coding Patterns

### Immutability and Data Classes

Core types like `ToolCall`, `ToolResult`, and `RunResult` are immutable dataclasses. They should remain lightweight, serializable, and value-oriented.

### Protocol-Driven Extensibility

Every major integration point is a protocol. This ensures third parties can implement custom plugins/backends without modifying the kernel.

### Error Handling

- Throw `StructuredAgentsError` subclasses for systemic failures.
- Tool failures should return `ToolResult(is_error=True)` instead of raising.
- The kernel surfaces errors to observers via `on_error`.

### Logging

Modules should use `logging.getLogger(__name__)` and avoid `print()`. Observers provide a better channel for user-facing output.

### Grammar Constraints

Only plugins may generate grammar via `build_grammar` and `extra_body`. This ensures model-specific grammar logic remains isolated.

## Testing Strategy

- **Unit tests**: cover core types, plugins, backends, and bundle loading.
- **Integration tests**: exercise a full agent loop with mocked model outputs.
- Prefer deterministic behavior and avoid network calls.
- Use `PythonBackend` in tests unless `.pym` execution is required.

## Adding a New Plugin

1. Implement the `ModelPlugin` protocol.
2. Add a grammar builder if needed.
3. Add tests for parsing and formatting.
4. Export it in `structured_agents/plugins/__init__.py`.

## Adding a New Backend

1. Implement the `ToolBackend` protocol.
2. Provide a `Snapshot` strategy if supported.
3. Add tests for execution and error handling.
4. Export it in `structured_agents/backends/__init__.py`.

## Adding a New Bundle Field

1. Extend the schema in `structured_agents/bundles/schema.py`.
2. Update the loader to interpret the new field.
3. Add tests covering the new behavior.

## Release Checklist

- Run full test suite: `uv run pytest -v --tb=short`.
- Update `__version__` in `structured_agents/__init__.py` when releasing.
- Verify `pyproject.toml` dependencies are up to date.

## Helpful References

- `ARCHITECTURE.md` for system overview.
- `STRUCTURED_AGENTS_DEV_GUIDE.md` for original build plan.
- `tests/` for usage examples.
