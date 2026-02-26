# Grammar Integration Report

## Scope

This report focuses on the **core library architecture** for structured outputs and grammar constraints in `structured-agents` v0.3.x. It synthesizes the recent structural tag failure analysis and grounds recommendations in the vendored vLLM and xgrammar sources. An appendix summarizes how the demo would change.

## Executive Summary

- **Default to native tool calling** with no grammar constraints. This aligns with the v0.3.0 ethos: minimal complexity, deterministic behavior, and reliance on backend capabilities.
- **Keep grammar constraints as opt-in** and focus on JSON schema constraints where possible.
- **Treat structural tags as advanced/experimental** until xgrammar + vLLM compatibility for Qwen XML schemas is demonstrably stable.

## Dependency Grounding (vLLM + xgrammar)

- vLLM expects structured outputs to be supplied through `structured_outputs` and serializes `structural_tag` as JSON internally when a `response_format` is provided (`vllm/entrypoints/openai/chat_completion/protocol.py`).
- vLLM’s xgrammar backend compiles `STRUCTURAL_TAG` by JSON-decoding the string and then invoking either legacy `structures` logic or the new `compile_structural_tag` path (`vllm/v1/structured_output/backend_xgrammar.py`).
- xgrammar defines a `QwenXMLParameterFormat` for structural tags, but its compiler rejects unsupported JSON schema types (such as `qwen_xml_parameter` in the reported failure).

## Current Core Library State

- Grammar constraints are applied through `ConstraintPipeline` in `structured_agents/grammar/pipeline.py`.
- `DecodingConstraint` currently requires a strategy and defaults to `ebnf` (`structured_agents/grammar/config.py`).
- `AgentKernel` expects `constraint_pipeline` to be `None` when no grammar is desired (`structured_agents/kernel.py`).
- The Qwen response parser parses tool calls from vLLM tool calls or fallback XML parsing (`structured_agents/models/parsers.py`).

## Recommended Architecture (v0.3.x)

### 1) Default Path: Native Tool Calling

**Principle:** if the backend already supports tool calling (e.g., vLLM with `tool_call_parser`), the library should not add additional grammar layers.

**Behavior:**
- `constraint_pipeline` defaults to `None`.
- `DecodingConstraint` becomes optional and used only when a grammar feature is explicitly enabled.
- The kernel sends `tools` to the OpenAI-compatible API and relies on `tool_calls` returned by the backend.

**Rationale:**
- Simplifies the runtime path and avoids xgrammar compatibility failures.
- Eliminates unnecessary structured output compilation latency.
- Matches the v0.3.0 ethos of minimal complexity and deterministic behavior.

### 2) Optional JSON Schema Constraints

**Principle:** offer a safe, explicit constraint path that relies on standard JSON schema, not model-specific XML types.

**Behavior:**
- `DecodingConstraint(strategy="json_schema")` builds `structured_outputs` with JSON schema only.
- Schema validation should be conservative: detect xgrammar-unsupported JSON schema features and fail fast with a clear error (no fallback).

**Rationale:**
- JSON schema is the most portable structured output format and is documented in vLLM’s structured outputs guide.
- The constraint path remains explicit and does not interfere with native tool calling.

### 3) Structural Tags as Advanced/Experimental

**Principle:** structural tags are powerful but fragile when tied to model-specific XML formats and xgrammar compatibility.

**Behavior:**
- Structural tags remain supported **only** through explicit configuration, with strong warning in docs.
- No automatic fallback or implicit enablement.

**Rationale:**
- The reported failure stems from xgrammar rejecting the `qwen_xml_parameter` schema type, which is incompatible with its JSON schema compiler.
- The integration cost and fragility exceed the value for the default path.

## Proposed Core API Semantics

### Decoding Configuration

- `DecodingConstraint | None` remains the entry point for grammar constraints.
- A `None` config means **native tool calling only**.
- Supported strategies:
  - `json_schema` (opt-in)
  - `structural_tag` (experimental)
  - `ebnf` (legacy/advanced)

### Constraint Pipeline

- `ConstraintPipeline` should **only** build extra payloads for explicit constraint strategies.
- With `None` or `strategy="none"`, return `None` (no `extra_body`).

### Failure Semantics

- Any unsupported grammar features should fail fast with clear errors (no silent fallbacks).
- Avoid degrading to alternative constraint modes automatically.

## Rationale Alignment With v0.3.0 Ethos

- **Minimal complexity:** default path is just OpenAI-compatible tool calling.
- **Deterministic behavior:** no hidden grammar compilation paths or heuristics.
- **Reliability:** avoid fragile xgrammar/vLLM coupling unless explicitly requested.
- **Dependency introspection:** all structured output behavior is grounded in `.context/vllm` and `.context/xgrammar` sources.

## Appendix A: Demo Impact Overview

**If the core library adopts the recommended architecture:**

- `demo/ultimate_demo` should default to **no grammar constraint**, relying on vLLM’s tool parser.
- The demo config should **remove `DISABLE_GRAMMAR`** and instead set `GRAMMAR_CONFIG = None` to indicate native tool calling.
- The demo kernel and subagent kernels should always build adapters with `constraint_pipeline=None` unless an experimental grammar config is explicitly supplied.

## Appendix B: Structural Tag Support (Detailed)

### Overview

Structural tags are an xgrammar feature that allow interleaving free text and constrained structured segments. In xgrammar, these are defined via composable formats (e.g., `tag`, `sequence`, `triggered_tags`) and can embed JSON schema constraints. This is powerful but delicate when paired with model-specific XML tool calling formats.

### Pros

- **Precise output control:** strong guarantees on format.
- **Flexible:** interleaves free text and structured segments.
- **Advanced tool calling:** can model parallel tool calls and special delimiters.

### Cons

- **Compatibility risk:** the reported crash shows xgrammar rejecting `qwen_xml_parameter` as an unsupported schema type, which is required by Qwen’s XML parameter format.
- **Operational complexity:** requires xgrammar compilation, which adds latency and introduces additional runtime failure modes.
- **Maintenance burden:** demands continuous synchronization between vLLM, xgrammar, and model-specific formats.

### Implications for structured-agents

- Structural tags should **not** be the default.
- If offered, the path must require explicit opt-in and emit strong compatibility warnings.
- The API should be explicit about supported JSON schema constraints and fail fast when encountering unsupported schema types.

### Recommended Long-Term Strategy

- Consider structural tags only after:
  - xgrammar supports model-specific schema types used by Qwen-like XML tool formats, or
  - a custom adapter is introduced to translate Qwen XML parameters into a JSON schema supported by xgrammar.

Until then, structural tags are best positioned as a power-user feature with strong caveats.
