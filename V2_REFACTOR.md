# V2 Refactor Roadmap

This roadmap focuses on the remaining items from `CODE_REVIEW_v2.md`. It groups work into phases with rough effort sizing and dependencies so you can execute in a clean, incremental order.

## Phase 1: Foundations (Medium)

1. **Schema-aware grammar generation** (Medium)
   - **Goal:** Use `ToolSchema.parameters` JSON schema to build stricter argument grammars.
   - **Work:**
     - Create a grammar builder that walks JSON schema types and emits EBNF fragments.
     - Add coverage for objects, arrays, enums, primitives, optional/required fields.
     - Extend `GrammarConfig` to select a schema-aware mode (or reuse `json_schema`).
   - **Dependencies:** None, but best done before parallel execution for higher reliability.

## Phase 2: Tooling Abstractions (Large)

2. **Unified ToolSource abstraction** (Large)
   - **Goal:** Replace separate registry/backend plumbing with a single interface that can both resolve schemas and execute tools.
   - **Work:**
     - Introduce `ToolSource` protocol with `list_tools`, `resolve`, `execute`, and optional `context_providers` hooks.
     - Build adapters for existing registries/backends (`RegistryToolSource`, `BackendToolSource`).
     - Update `AgentKernel` to accept a `ToolSource` or maintain backward-compatible adapters.
   - **Dependencies:** None, but impacts kernel API and tests.

3. **Bundle registry config expansion** (Medium)
   - **Goal:** Allow registry configuration in `bundle.yaml`.
   - **Work:**
     - Replace `registries: ["grail"]` with `registries: [{type: "grail", config: {...}}]`.
     - Update `BundleManifest` schema and loader.
     - Support multiple registry types and custom config payloads.
   - **Dependencies:** Works best with ToolSource to avoid extra wiring.

## Phase 3: Execution Semantics (Large)

4. **Parallel tool execution strategy** (Large)
   - **Goal:** Provide an opt-in parallel execution mode when grammar allows multiple tool calls.
   - **Work:**
     - Add `ToolExecutionStrategy` (sequential vs concurrent with limit).
     - Update `AgentKernel.step()` to execute tool calls concurrently under a bounded semaphore.
     - Emit observer events consistently (tool call/result ordering should be deterministic).
   - **Dependencies:** None, but benefits from ToolSource consolidation.

## Phase 4: Plugin Decomposition (Large)

5. **Plugin responsibilities split** (Large)
   - **Goal:** Make plugins composable by separating formatting, parsing, and grammar-building.
   - **Work:**
     - Define `MessageFormatter`, `ToolFormatter`, `ResponseParser`, `GrammarProvider` protocols.
     - Provide defaults for FunctionGemma/Qwen by composing these components.
     - Update `ModelPlugin` to be a lightweight coordinator.
   - **Dependencies:** Schema-aware grammar builder should land before this.

## Phase 5: Client Exposure (Small)

6. **Explicit client reuse API** (Small)
   - **Goal:** Provide a first-class pathway to reuse `OpenAICompatibleClient` outside the kernel.
   - **Work:**
     - Add a documented factory or helper for building clients from `KernelConfig` or `Bundle` settings.
     - Optional: allow `AgentKernel` to accept a client factory for lifecycle control.
   - **Dependencies:** None (can be done anytime).

---

## Suggested Order

1. Schema-aware grammar generation
2. ToolSource abstraction
3. Bundle registry configuration
4. Parallel tool execution
5. Plugin decomposition
6. Client exposure API

## Estimated Effort Summary

- **Small:** Client exposure API
- **Medium:** Schema-aware grammar, token-aware history, bundle registry config
- **Large:** ToolSource abstraction, parallel execution strategy, plugin decomposition

## Testing Focus

- Update unit tests for grammar builder behavior and history trimming.
- Add integration tests for ToolSource and parallel execution.
- Ensure bundle loading supports new registry schema.
