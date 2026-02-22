# Code Review v2: structured-agents

## Library Concept and Overview

`structured-agents` is a compact, typed agent loop for tool-calling LLM workflows. It focuses on a predictable execution core (the `AgentKernel`) and clean integration points for model-specific formatting (`ModelPlugin`), tool execution (`ToolBackend`), tool discovery (`ToolRegistry`), and prompt/tool bundling (`AgentBundle`). The design favors a minimal surface area while still supporting structured outputs via XGrammar, Grail `.pym` tools, and OpenAI-compatible model servers.

The project deliberately avoids workspace management, multi-agent orchestration, or UI concerns. Instead, it provides an extensible foundation for teams to build agent applications with their own environment and coordination layers.

## Detailed Library Walkthrough

### Entry Point and Dependency Enforcement
- `structured_agents/__init__.py` eagerly calls `require_xgrammar_and_vllm()` from `deps.py`, forcing both dependencies to be present. This makes the import fail fast, which aligns with a “strict dependency” stance but also prevents using the library in minimal/partial scenarios.

### Core Types and Contracts
- `types.py` defines immutable dataclasses (`Message`, `ToolCall`, `ToolResult`, `StepResult`, `RunResult`) and the `ToolSchema` and `KernelConfig` Pydantic model.
- `Message.to_openai_format()` centralizes serialization to OpenAI-compatible request payloads.
- `ToolSchema` embeds backend routing (`backend`), optional Grail script paths, context providers, and an unused `mcp_server` field.
- `ToolResult.to_message()` normalizes tool outputs into assistant-compatible tool messages.

### Agent Kernel
- `kernel.py` is the primary orchestrator. It:
  - Formats input messages/tools via the plugin.
  - Builds grammar constraints when tools exist.
  - Uses `OpenAICompatibleClient` to execute the model call.
  - Parses tool calls via the plugin, then executes tools sequentially via the backend.
  - Updates history, gathers token usage, and emits observer events.
- Tool resolution can be done by schemas or tool names (resolved through `ToolRegistry`).
- Termination is determined by either no tool calls, a custom termination predicate, or `max_turns`.

### Client Layer
- `client/openai_compat.py` wraps `AsyncOpenAI` and produces a `CompletionResponse`. It is a concrete class, but the repo also defines an `LLMClient` protocol that is not wired into the kernel.

### Plugins and Grammar
- `plugins/function_gemma.py` and `plugins/qwen.py` implement the model format/parse logic. FunctionGemma supports grammar constraints (EBNF or structural tags), while Qwen does not.
- `grammar` provides:
  - `GrammarConfig` (mode + formatting preferences).
  - Grammar artifacts (`EBNFGrammar`, `StructuralTagGrammar`, `JsonSchemaGrammar`) that generate vLLM payloads.
  - A builder (`FunctionGemmaGrammarBuilder`) that builds EBNF or structural-tag grammar.

### Tool Backends
- `PythonBackend` executes async Python callables directly and is mostly intended for tests and lightweight usage.
- `GrailBackend` uses a process pool to run `.pym` scripts via Grail, supports context providers, and enforces timeouts and limits.
- `CompositeBackend` dispatches execution by `ToolSchema.backend` and proxies context provider execution to the Grail backend.

### Registries
- `PythonRegistry` wraps Python callables into `ToolSchema` definitions by inspecting signatures and type hints.
- `GrailRegistry` scans `.pym` scripts in an agents directory, reading `.grail` metadata if present.
- `CompositeRegistry` delegates tool resolution across registries.

### Bundles
- `AgentBundle` loads `bundle.yaml`, resolves tools, and renders Jinja2 templates for system and user prompts.
- Bundles select registries and plugins, but registry selection is limited to string names (`grail` or `python`), and registry configuration is not exposed in the manifest beyond the name.

### Observability
- The observer system uses typed event dataclasses (`ModelRequestEvent`, `ToolResultEvent`, etc.) with a `CompositeObserver` to fan out events.
- Observers are async and non-blocking, and errors are logged rather than interrupting the run.

### Tests
- Tests cover kernel execution, backends, plugins, registries, grammar building, and bundle loading.
- Integration tests simulate multi-turn tool workflows and verify observer event sequences.

## Architecture Review and Recommendations

### Strengths
- **Clear separation of concerns.** Kernel, plugins, backends, registries, and bundles are discrete modules with minimal cross-cutting logic.
- **Typed, immutable core data.** The dataclasses and Pydantic config reduce mutation and improve testability.
- **Minimal, testable API surface.** Most functionality is small and focused, which makes it easy to reason about behavior.
- **Solid test coverage.** The tests cover the critical paths and validate the intended flow.

### Issues and Opportunities for Improvement

1. **LLM client injection is missing (limits composability).**
   - The `LLMClient` protocol exists but is not used by `AgentKernel`, which always constructs `OpenAICompatibleClient` internally.
   - **Recommendation:** Accept an `LLMClient` instance (or factory) in `AgentKernel` and default to `OpenAICompatibleClient` only when not provided. This allows alternate clients (mocked or non-OpenAI servers) and makes the kernel more reusable.

2. **Grammar configuration is not validated against plugin capabilities.**
   - `GrammarConfig` allows modes (`ebnf`, `structural_tag`, `json_schema`) but plugins do not enforce compatibility.
   - `FunctionGemmaGrammarBuilder.supports_mode()` includes `"permissive"`, which is not a valid grammar mode and seems like a conflation with `args_format`.
   - **Recommendation:** Add a validation layer in `AgentKernel` or `AgentBundle` to ensure the selected grammar mode is supported by the plugin. Tighten `supports_mode()` to align with real `GrammarConfig.mode` values.

3. **Grammar generation is overly permissive and not schema-aware.**
   - Grammar building does not use tool parameter schemas; it accepts any arg content (`[^}]*`) by default.
   - **Recommendation:** Provide a schema-driven grammar builder that maps JSON schema to grammar rules, enabling precise argument validation and more reliable tool calling.

4. **Backend and registry roles are separated but not coordinated.**
   - Registries resolve tool schemas; backends execute tools. There is no unified “tool source” abstraction tying discovery and execution together.
   - **Recommendation:** Introduce a `ToolSource` abstraction that encapsulates both schema resolution and execution. This would simplify the kernel (one entry point) and allow alternate tool sources (MCP, HTTP tool services, remote registries).

5. **Bundle registry configuration is too static.**
   - Bundles only list registry names; there is no manifest-level way to configure registry parameters (e.g., custom agents directory, python module imports, custom registry types).
   - **Recommendation:** Replace `registries: ["grail"]` with a structured registry list containing `type` and `config`, and allow dynamic registry extension. This improves modularity and allows custom registry injection without code edits.

6. **Tool output serialization is inconsistent and under-specified.**
   - `ToolResult.output` can be either `str` or `dict`, and `ToolResult.to_message()` stringifies dicts. This blurs structured/typed outputs and makes downstream handling ambiguous.
   - **Recommendation:** Standardize tool output to a single structured type (e.g., `ToolPayload` with `data` + `rendered_text`), or introduce an explicit serializer interface so callers can choose between JSON, text, or richer formatting.

7. **Kernel has no explicit concurrency strategy despite “parallel calls” grammar options.**
   - Grammar config allows parallel calls, but tool execution is always sequential.
   - **Recommendation:** Provide an opt-in async execution mode (e.g., `tool_execution_strategy`) with concurrency limits. This aligns the runtime with the grammar’s parallel-call assumption.

8. **Unused or unclear fields create ambiguity.**
   - `ToolSchema.mcp_server` is defined but never used.
   - Grail snapshots are implemented but store no state; the snapshot feature is not meaningfully functional.
   - **Recommendation:** Either implement these fully or remove them from the public API to avoid confusion.

9. **History management is message-count based only.**
   - `SlidingWindowHistory` trims by count, not token usage. For large tool outputs, this may be ineffective.
   - **Recommendation:** Introduce a token-aware history strategy or allow pluggable token counters so history can be trimmed by cost.

10. **Plugin/grammar logic is too tightly coupled to model-specific details.**
   - Plugins carry both formatting and parsing responsibilities and also own grammar conversion. This makes plugins monolithic.
   - **Recommendation:** Split plugin responsibilities into smaller components (formatter, parser, grammar builder). A composition approach makes it easier to reuse parsing logic across models and to mix in alternate grammar backends.

11. **OpenAI-compatible client API is not surfaced as a reusable dependency.**
   - The client is internal and effectively bound to KernelConfig. This makes it harder to reuse elsewhere (e.g., in CLI tools or diagnostics).
   - **Recommendation:** Expose `OpenAICompatibleClient` via composition from bundle or kernel config, and allow `AgentKernel` to accept `LLMClient` or `OpenAICompatibleClient` explicitly.

12. **Bundle templates lack validation for missing variables.**
   - Jinja rendering silently ignores missing variables by default, which can lead to incomplete prompts.
   - **Recommendation:** Enable strict Jinja rendering or provide optional validation to catch missing context keys early.

## Summary of Key Refactors (No Backward-Compatibility Required)
- Make `AgentKernel` accept an injected `LLMClient` and optionally a `ToolSource` abstraction.
- Rework grammar generation to be schema-aware and plugin-validated.
- Replace string-based registry selection in bundles with structured registry definitions and extension points.
- Standardize tool result payloads and provide a serialization strategy.
- Align runtime tool execution with grammar-level parallel-call semantics.

This codebase is already clean and well-organized. These refinements would increase composability, reduce implicit coupling, and make it easier to extend the library into new tool ecosystems and model families without expanding the kernel’s responsibilities.
