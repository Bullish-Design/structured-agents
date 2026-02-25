# Architecture

This document describes the internal architecture of `structured-agents` and how the major subsystems interact.

## High-Level Overview

`structured-agents` provides a core agent loop that repeatedly:

1. Formats messages/tools for a model via a composed plugin.
2. Sends a chat completion request to an OpenAI-compatible API.
3. Parses tool calls from the model response.
4. Executes tools through a `ToolSource` (registry + backend).
5. Updates history and emits observer events.

The system is intentionally modular. Each subsystem is replaceable and focused.

## Core Modules

### Agent Kernel (`structured_agents.kernel`)

- Orchestrates the agent loop.
- Manages history trimming via a `HistoryStrategy`.
- Delegates formatting/parsing to a `ModelPlugin`.
- Executes tools via a `ToolSource`.
- Honors `ToolExecutionStrategy` for parallel tool execution.
- Emits observer events for visibility and diagnostics.

### Model Plugins (`structured_agents.plugins`)

Plugins are composed from component protocols:

- `MessageFormatter`
- `ToolFormatter`
- `ResponseParser`
- `GrammarProvider`

`ComposedModelPlugin` wires these together and exposes capability flags based on the grammar provider.

Key classes:

- `ModelPlugin` protocol
- `ComposedModelPlugin`
- `FunctionGemmaPlugin`
- `QwenPlugin` (example implementation)

### Tool Sources (`structured_agents.tool_sources`)

- Unifies tool discovery and execution.
- `RegistryBackendToolSource` bridges `ToolRegistry` and `ToolBackend`.

### Tool Backends and Registries

- Backends execute tool calls (`PythonBackend`, `GrailBackend`).
- Registries provide tool schemas (`PythonRegistry`, `GrailRegistry`).

### Bundles (`structured_agents.bundles`)

Bundles represent a deployable agent configuration:

- `bundle.yaml` contains tool references, prompts, and model configuration.
- `AgentBundle` loads the manifest, exposes tool schemas, and builds a `ToolSource`.

### Client (`structured_agents.client`)

- `OpenAICompatibleClient` wraps the OpenAI/vLLM API surface.
- `build_client` provides a public factory for client reuse.

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
  ToolSource → ToolResults
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
5. `ToolResultEvent` (per tool, emitted in deterministic order)
6. `TurnCompleteEvent`
7. `KernelEndEvent` (once at run end)

## Extensibility Points

- Add new model plugins by implementing component protocols and composing them.
- Add new tool sources by implementing `ToolSource`.
- Add new backends/registries for tool execution and schema discovery.
- Add new history strategies by implementing `HistoryStrategy`.
- Add new observers for logging, tracing, or UI integration.
- Add new client implementations by implementing `LLMClient`.

## Dependencies

- `grail`: required for `.pym` execution in `GrailBackend`.
- `openai`: used by the OpenAI-compatible client.
- `xgrammar`: required for grammar-constrained decoding.

## Grammar-Constrained Decoding

The library supports multiple grammar modes via XGrammar for controlling model output structure:

### Grammar Configuration

```python
from structured_agents.grammar.config import GrammarConfig

grammar_config = GrammarConfig(
    mode="structural_tag",  # "ebnf", "structural_tag", or "json_schema"
    allow_parallel_calls=True,  # Allow multiple tool calls in one response
    args_format="permissive",  # "permissive", "escaped_strings", or "json"
)
```

### Supported Modes by Plugin

| Plugin | ebnf | structural_tag | json_schema |
|--------|------|---------------|-------------|
| FunctionGemmaPlugin | ✅ | ✅ | ✅ |
| QwenPlugin | ❌ (vLLM override) | ✅ (recommended) | ❌ (schema mismatch) |

### Mode Details

- **`structural_tag`**: XGrammar structural tags. **Recommended for Qwen models.** Uses `QwenXMLParameterFormat` internally, which the model is specifically trained to generate. This is the only mode that works reliably with Qwen.

- **`ebnf`**: EBNF grammar format. Works for FunctionGemma. For Qwen, vLLM automatically sets its own JSON schema when tools are provided, which overrides the EBNF grammar and causes empty arguments.

- **`json_schema`**: JSON schema constraint. Works for FunctionGemma. For Qwen, the schema format doesn't match what the model expects.

### Why structural_tag Works for Qwen

The `structural_tag` mode uses `QwenXMLParameterFormat` which generates output in the exact XML format that Qwen3 was trained on:

```xml
<function=tool_name>
<parameter=key>value</parameter>
</function>
```

vLLM's `qwen3_xml` tool parser is specifically designed to parse this format, resulting in correct tool call extraction with arguments.

### Recommended Configuration for Qwen

```python
from structured_agents.plugins import QwenPlugin
from structured_agents.grammar.config import GrammarConfig

plugin = QwenPlugin()
grammar = plugin.build_grammar(
    tools, 
    GrammarConfig(
        mode="structural_tag",  # Only mode that works reliably for Qwen
        allow_parallel_calls=True,
    )
)
```

### Response Parsing

The Qwen response parser automatically cleans up quote noise from enum values. vLLM sometimes returns string arguments with extra surrounding quotes, which are automatically stripped.

## Related Documents

- `DEV_GUIDE.md`: contributor-focused implementation and workflow details.
