# Architecture

This document describes the internal architecture of `structured-agents` and how the major subsystems interact.

## High-Level Overview

`structured-agents` provides a core agent loop that repeatedly:

1. Formats messages/tools for a model.
2. Sends a chat completion request to an OpenAI-compatible API.
3. Parses tool calls from the model response.
4. Executes tools via a backend.
5. Updates history and emits observer events.

The system is intentionally modular. Each subsystem is replaceable and focused.

## Core Modules

### Agent Kernel (`structured_agents.kernel`)

- Orchestrates the agent loop.
- Manages history trimming via a `HistoryStrategy`.
- Delegates model formatting/parsing to a `ModelPlugin`.
- Delegates tool execution to a `ToolBackend`.
- Emits observer events for visibility and diagnostics.

### Model Plugins (`structured_agents.plugins`)

- Normalize model-specific message formats.
- Build optional XGrammar EBNF constraints for structured output.
- Parse raw responses into `ToolCall` objects.

Key classes:

- `ModelPlugin` protocol
- `FunctionGemmaPlugin`
- `QwenPlugin`

### Tool Backends (`structured_agents.backends`)

- Provide execution strategies for tool calls.
- `GrailBackend` runs `.pym` scripts in isolated processes.
- `PythonBackend` executes Python async callables directly (useful for tests).

Key classes:

- `ToolBackend` protocol
- `GrailBackend`, `GrailBackendConfig`
- `PythonBackend`

### Bundles (`structured_agents.bundles`)

Bundles represent a deployable agent configuration:

- `bundle.yaml` contains tool definitions, prompts, and model configuration.
- `AgentBundle` loads the manifest and exposes tool schemas and prompt templates.

### Client (`structured_agents.client`)

- `OpenAICompatibleClient` wraps the OpenAI/vLLM API surface.
- `LLMClient` protocol allows replacement with other clients if needed.

### Observers (`structured_agents.observer`)

- Event system for tooling and telemetry.
- `CompositeObserver` fans out events.
- `NullObserver` is the default no-op implementation.

## Data Flow

```
Initial Messages + Tool Schemas
        │
        ▼
 Model Plugin → formatted messages/tools
        │
        ▼
 OpenAICompatibleClient → CompletionResponse
        │
        ▼
 Model Plugin → content + ToolCalls
        │
        ▼
 Tool Backend → ToolResults
        │
        ▼
 History + Observer Events → RunResult
```

## Type System and Contracts

- All core types are in `structured_agents.types`.
- Pydantic models (`KernelConfig`, bundle schemas) handle validation and config.
- Dataclasses (`ToolCall`, `ToolResult`, `RunResult`) are immutable and typed.
- Protocols define extensibility points for plugins, backends, history, observers, and clients.

## Error Handling

- `StructuredAgentsError` is the base exception.
- Specific error types exist for kernel, backend, tool execution, and bundle errors.
- Backends return `ToolResult` with `is_error=True` for tool failures.

## Event Lifecycle

Events are emitted in this order per turn:

1. `KernelStartEvent` (once at run start)
2. `ModelRequestEvent`
3. `ModelResponseEvent`
4. `ToolCallEvent` (per tool)
5. `ToolResultEvent` (per tool)
6. `TurnCompleteEvent`
7. `KernelEndEvent` (once at run end)

## Extensibility Points

- Add new model plugins by implementing `ModelPlugin`.
- Add new tool backends by implementing `ToolBackend`.
- Add new history strategies by implementing `HistoryStrategy`.
- Add new observers for logging, tracing, or UI integration.
- Add new client implementations by implementing `LLMClient`.

## Dependencies

- `grail`: required for `.pym` execution in `GrailBackend`.
- `openai`: used by the OpenAI-compatible client.
- `xgrammar`: optional integration via plugins that emit EBNF grammar.

## Related Documents

- `DEV_GUIDE.md`: contributor-focused implementation and workflow details.
- `STRUCTURED_AGENTS_DEV_GUIDE.md`: original build plan used to scaffold the library.
