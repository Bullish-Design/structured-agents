# structured-agents v0.3.0 Source Code Review

**Reviewer:** Code Review Agent  
**Date:** 2026-02-26  
**Scope:** All source files under `src/structured_agents/`  
**Files reviewed:** 21

---

## Executive Summary

The v0.3.0 refactor achieves its goal of a simplified architecture with 5 core concepts (Tool, ModelAdapter, DecodingConstraint, Kernel, Agent). The codebase is small (~800 lines), well-structured, and uses modern Python idioms. However, the review reveals several significant issues: (1) the Grail integration is entirely stubbed out, (2) the kernel never emits events despite having a full observer system, (3) there are duplicate `build_client` functions, (4) `KernelConfig` is defined but unused, (5) the `GrailTool.execute` silently drops call context, and (6) the grammar/constraint pipeline is wired but functionally inert.

---

## Module-by-Module Analysis

### 1. `src/structured_agents/types.py`

**Issues:**

- **Lines 14-18 — `KernelConfig` is dead code.** Defined as a plain class (not a dataclass), never used anywhere in the codebase. `AgentKernel` duplicates these same fields as individual dataclass fields (lines 42-46 of `kernel.py`). Either use `KernelConfig` or remove it.

- **Line 14 — `KernelConfig` is not a dataclass.** It's a plain class with class-level annotations and default values. This means instances won't have `__init__`, `__repr__`, or `__eq__`. This is likely unintentional — it should be `@dataclass` or removed.

- **Lines 104-106 — `ToolResult.output_str` is a trivial identity property.** It returns `self.output` which is already typed as `str`. This is dead code with no callers.

- **Line 89 — Short tool call IDs.** `call_{uuid.uuid4().hex[:8]}` uses only 8 hex chars (32 bits of entropy). In high-throughput concurrent scenarios, collision risk is non-trivial. Consider using 12+ chars.

- **Line 8 — `Any` imported.** Repository AGENTS.md says "Avoid `Any` unless unavoidable." `ToolSchema.parameters` (line 130) is `dict[str, Any]` which is acceptable for JSON schema, but `ToolCall.arguments` (line 76) could potentially be `dict[str, object]` or a more specific type.

- **Line 176 — `RunResult` is not `slots=True`.** Unlike all other frozen dataclasses in this file, `RunResult` uses `@dataclass(frozen=True)` without `slots=True`. This is inconsistent and allows `__dict__` attribute creation.

### 2. `src/structured_agents/tools/protocol.py`

**Issues:**

- **Line 14 — `context: Any` parameter.** The `Tool.execute` method accepts `context: Any` which is maximally untyped. This makes the protocol structurally weak — any caller can pass anything. A `ToolCallContext` dataclass would be more appropriate.

- **No `__all__` export.** Minor, but inconsistent with other modules.

### 3. `src/structured_agents/tools/grail.py`

**Critical Issues:**

- **Lines 44-47 — `discover_tools` is entirely stubbed.** This is the primary entry point for the Grail integration — the whole point of the tool system — and it's a TODO that returns `[]`. This means `Agent.from_bundle()` will always produce an agent with zero tools.

- **Lines 15-18 — Schema generation is hardcoded/empty.** `GrailTool.__init__` sets the description to a generic `f"Tool: {script.name}"` and parameters to `{"type": "object", "properties": {}}`. It never introspects the script's `@external` functions or `Input()` declarations to build a real parameter schema. The model will have no idea what arguments the tool accepts.

- **Line 12 — `script: Any` and `limits: Any`.** Both constructor parameters are untyped. The `script` parameter should be typed as whatever `grail.load()` returns (e.g., `grail.Script` or a protocol). This violates the repository's typing policy.

- **Lines 27 — `await self._script.run(...)`.** The code assumes `script.run()` is async, but this is unverified against the actual grail API. If `grail.load()` returns a synchronous script runner, this will fail.

- **Line 30 — `context.call_id` access with no type safety.** `context` is `Any`, and the code does `context.call_id if context else "unknown"`. If context doesn't have `call_id`, this will raise `AttributeError` at runtime.

### 4. `src/structured_agents/grammar/config.py`

**Issues:**

- **Lines 7-13 and 16-33 — `DecodingConstraint` and `GrammarConfig` overlap.** Both have `strategy`/`mode` (same enum), `allow_parallel_calls`, and `send_tools_to_api`. `GrammarConfig` has additional `args_format` field. But `GrammarConfig` is never exported in `grammar/__init__.py` or `__init__.py`. It appears to be dead code or an incomplete migration — one should be removed or they should be unified.

- **Line 11 vs Line 20 — Default inconsistency.** `DecodingConstraint.allow_parallel_calls` defaults to `False`, but `GrammarConfig.allow_parallel_calls` defaults to `True`. If both represent the same concept, the defaults contradict each other.

- **Line 13 vs Line 23 — Default inconsistency.** `DecodingConstraint.send_tools_to_api` defaults to `False`, but `GrammarConfig.send_tools_to_api` defaults to `True`. Same contradiction.

- **`GrammarConfig` is unexported.** Not in `grammar/__init__.py` `__all__`, not in package `__init__.py`. If it's needed, export it; if not, remove it.

### 5. `src/structured_agents/grammar/pipeline.py`

**Issues:**

- **Line 14-15 — Builder signature uses `Any` for config.** `Callable[[list[ToolSchema], DecodingConstraint], dict[str, Any] | None]` — this is actually well-typed. However, the `ModelAdapter.grammar_builder` (in `adapter.py:14`) uses `Callable[[list[ToolSchema], Any], ...]`, losing the type constraint. These should be aligned.

- **Line 22-29 — `constrain()` is a thin wrapper.** The "pipeline" is a single function call to `self._builder`. There's no actual pipeline logic (no chaining, no transformation, no validation). The class adds indirection without value. Consider whether a plain function suffices.

### 6. `src/structured_agents/models/adapter.py`

**Issues:**

- **Line 15 — `response_parser: Any`.** This should be typed as `ResponseParser` (the protocol defined in `parsers.py`). Using `Any` here defeats the purpose of having the protocol.

- **Line 14 — `grammar_builder` second arg is `Any`.** Should be `DecodingConstraint` to match the `ConstraintPipeline` builder signature, but `kernel.py:79` passes `None` as the second argument. This mismatch suggests the grammar builder integration is incomplete.

- **Lines 19-24 — `__post_init__` mutates frozen-like semantics.** The class is `@dataclass(frozen=True)` and uses `object.__setattr__` to work around immutability in `__post_init__`. This is a code smell — the defaults should be handled differently (e.g., use a factory function or `__init_subclass__`).

- **Lines 26-38 — `_default_format_messages` appends tools as string.** The default message formatter appends `{"role": "system", "content": "Available tools: " + str(tools)}` which serializes tool dicts using Python's `str()` representation, not JSON. This produces unreliable, non-standard formatting that models may not parse well.

### 7. `src/structured_agents/models/parsers.py`

**Issues:**

- **Lines 63-70 — `FunctionGemmaResponseParser` is a trivial delegation.** It instantiates a new `QwenResponseParser()` on every `parse()` call and delegates to it. The docstring says it "handles structural tags differently" but the code doesn't. This is either incomplete or dead code.

- **Line 70 — Unnecessary instantiation.** Even if delegation is intended, creating a new `QwenResponseParser()` instance per call is wasteful. Should be a class attribute or shared instance.

- **Line 29 — `json.loads` without error handling.** In `QwenResponseParser.parse()`, `json.loads(func.get("arguments", "{}"))` can raise `JSONDecodeError` but isn't wrapped in try/except. The XML parser at line 52 handles this, but the API tool_calls path doesn't.

- **Lines 24-31 — Parser drops tool call IDs from API.** When parsing API-provided `tool_calls`, the code calls `ToolCall.create()` which generates new IDs, discarding the original `tc["id"]` from the API response. This breaks the tool call ID chain — the model's response references one ID, but the tool result will have a different one.

### 8. `src/structured_agents/events/types.py`

**Issues:**

- **Line 5 — `Union` import.** Python 3.13 supports `X | Y` syntax natively, so `Union` import is unnecessary. Line 66 could use `type Event = KernelStartEvent | KernelEndEvent | ...` (PEP 695 syntax).

- **No error event type.** The event system has no `ErrorEvent` for reporting errors during kernel execution, tool failures, or parsing errors. The kernel's error handling paths are thus invisible to observers.

### 9. `src/structured_agents/events/observer.py`

**Issues:**

- **No composite/multi-observer.** If a user wants both logging and metrics observers, there's no `CompositeObserver` or `MultiObserver` to fan out events. This is a common need.

### 10. `src/structured_agents/kernel.py`

**Critical Issues:**

- **The kernel NEVER emits events.** Despite importing all event types (lines 10-18), accepting an `observer` (line 41), and emitting `KernelStartEvent` in `run()` (line 149), the kernel:
  - Never emits `ModelRequestEvent` (before API call)
  - Never emits `ModelResponseEvent` (after API call)
  - Never emits `ToolCallEvent` (before tool execution)
  - Never emits `ToolResultEvent` (after tool execution)
  - Never emits `TurnCompleteEvent` (after each turn)
  - Never emits `KernelEndEvent` (after loop ends)
  
  Only `KernelStartEvent` is emitted. The entire observer system is effectively dead code. This is the most significant incomplete implementation.

- **Line 10-18 — Unused imports.** `Event`, `ModelRequestEvent`, `ModelResponseEvent`, `ToolCallEvent`, `ToolResultEvent`, `TurnCompleteEvent` are all imported but never used (only `KernelStartEvent` and `KernelEndEvent` are partially used — `KernelEndEvent` is imported but never emitted).

- **Line 117 — `tool.execute(tc.arguments, None)`.** The tool is always called with `context=None`, meaning `GrailTool.execute` will always use `call_id="unknown"`. The `tc` (ToolCall) object has `.id` which should be passed as context.

- **Lines 68-69 — `format_messages` called with empty tools list.** `formatter(messages, [])` always passes `[]` for tools. Then lines 70-74 separately format tools. But `_default_format_messages` appends tools to messages, so tools are never included in the default formatting path when used this way.

- **Line 48-49 — `_tool_map()` is O(n) per call.** Called multiple times per step (lines 63, 106). Should be cached.

- **Lines 119-129 — Concurrency model.** When `max_concurrency > 1`, `asyncio.gather` is used, but errors from individual tool calls aren't isolated. If one tool raises an unhandled exception, all concurrent calls fail. The `GrailTool.execute` catches exceptions, but custom `Tool` implementations may not.

- **Lines 138-201 — `run()` doesn't use custom exceptions.** The kernel never raises `KernelError` (defined in `exceptions.py`). Errors from `self.client.chat_completion()` will propagate as raw `openai` SDK exceptions with no wrapping.

- **Line 87 — `tool_choice="none"` when no tools.** Passing `tool_choice="none"` explicitly may cause issues with some backends that don't expect it. Better to omit the parameter entirely.

- **Lines 192-194 — Final message extraction.** If `messages` is empty (theoretically impossible but defensive), it creates `Message(role="assistant", content="")`. But `messages` starts from `initial_messages` which is always non-empty per the caller.

### 11. `src/structured_agents/agent.py`

**Issues:**

- **Line 7 — `yaml` import.** `yaml` (PyYAML) is not listed as a dependency in `pyproject.toml` (not checked, but should be verified). If it's not declared, this will fail at import time.

- **Line 45 — `agents_dir` path resolution.** `Path(bundle_path).parent / data.get("agents_dir", "agents")` uses the original `bundle_path` argument, not the resolved `path` variable (which may have been modified to `path / "bundle.yaml"`). If `bundle_path` is a directory, `Path(bundle_path).parent` goes one level too high.

- **Lines 73-76 — Adapter hardcodes `QwenResponseParser`.** `from_bundle()` always uses `QwenResponseParser()` regardless of the `manifest.model` value. There's no adapter registry or model-to-parser mapping.

- **Line 75 — `grammar_builder=lambda t, c: None`.** The grammar builder is a no-op lambda. Grammar-constrained decoding — a core feature of the library — is completely disabled in the high-level API.

- **Line 82 — Hardcoded vLLM URL.** `base_url` is hardcoded to `"http://localhost:8000/v1"`. Should come from config/manifest.

- **Lines 66-93 — `from_bundle` doesn't use `**overrides`.** The parameter is accepted but never applied to anything. Dead parameter.

- **Line 93 — Observer not passed to Agent.** `from_bundle` creates `cls(kernel, manifest)` without an observer, meaning `self.observer` is set to `NullObserver()` and never used (the kernel also has its own separate observer).

- **Line 29 — `grammar_config` in manifest.** `AgentManifest.grammar_config` exists but is hardcoded to `None` in `load_manifest()` (line 48). The YAML config is never read for grammar settings.

### 12. `src/structured_agents/client/protocol.py`

**Issues:**

- **Line 11 — `CompletionResponse` not frozen.** Unlike types in `types.py`, this dataclass is mutable. Should be `@dataclass(frozen=True)` for consistency and safety.

- **Line 19 — `raw_response: dict[str, Any]`.** Storing the raw response forces all client implementations to produce a dict, which may not be natural for all backends. Consider making this optional.

### 13. `src/structured_agents/client/openai.py`

**Issues:**

- **Line 82 — `response.to_dict()`.** The `openai` SDK's response object uses `.model_dump()` (Pydantic v2), not `.to_dict()`. This will raise `AttributeError` at runtime. This is a **bug**.

- **Lines 89-96 — Duplicate `build_client` function.** This function is identical to `client/factory.py:build_client`. Both exist, both are importable. `agent.py` imports from `factory.py`, `__init__.py` imports from `openai.py`. One should be removed.

- **Lines 43-44 — `tools` passed even when `None`.** The OpenAI SDK may not handle `tools=None` gracefully in all versions. Should be conditionally omitted from kwargs.

### 14. `src/structured_agents/client/factory.py`

**Issues:**

- **Entire file is a duplicate.** `build_client` here is identical to the one in `openai.py`. This module adds no value. Either consolidate into one location or differentiate them.

- **Line 10 — Return type is concrete, not protocol.** Returns `OpenAICompatibleClient` instead of `LLMClient`. This is fine but differs from the `openai.py` version's `LLMClient` return type annotation — wait, actually `openai.py:89` also returns `LLMClient`. Actually checking: `factory.py:10` returns `OpenAICompatibleClient` (concrete), `openai.py:89` returns `LLMClient` (protocol). These are inconsistent.

### 15. `src/structured_agents/exceptions.py`

**Issues:**

- **Lines 37-42 — `PluginError` and `BackendError` are unused.** Grep shows no code raises these exceptions. They exist anticipatorily but add noise.

- **Lines 21-34 — `ToolExecutionError` is never raised.** Neither `GrailTool.execute` nor `kernel.py` raises this. Tool errors are silently returned as `ToolResult(is_error=True)` instead.

- **Lines 10-18 — `KernelError` is never raised.** The kernel catches nothing and raises nothing from this hierarchy.

- **Overall:** The entire exception hierarchy is dead code. No module raises any of these exceptions.

### 16. `src/structured_agents/__init__.py`

**Issues:**

- **Missing exports:** `KernelConfig` (from types.py), `GrammarConfig` (from grammar/config.py), `ResponseParser` (protocol from parsers.py), `FunctionGemmaResponseParser`, `load_manifest`, `discover_tools` are not in `__all__`.

- **`discover_tools` is exported from `tools/__init__.py`** but not from the top-level package. Minor inconsistency.

---

## Cross-Cutting Issues

### 1. Grail Integration Is Entirely Stubbed

The library's stated purpose is structured tool orchestration via Grail `.pym` scripts, but:
- `discover_tools()` returns `[]` (grail.py:47)
- `GrailTool` hardcodes empty parameter schemas (grail.py:18)
- No call to `grail.load()` anywhere in the codebase
- `@external` function introspection is missing
- `Input()` declaration handling is missing

**Impact:** The core value proposition of the library is non-functional.

### 2. Observer System Is Dead

The kernel defines 7 event types, an observer protocol, and accepts an observer — but only emits 1 of 7 events. The rest of the observer infrastructure does nothing.

### 3. Grammar/Constraint Pipeline Is Inert

- `ConstraintPipeline` exists but is never instantiated
- `DecodingConstraint` exists but is never used in the kernel flow
- `Agent.from_bundle()` uses `lambda t, c: None` as grammar builder
- `GrammarConfig` is defined but unexported and unused
- The xgrammar dependency is never imported or used

**Impact:** Grammar-constrained decoding — the other core feature — is non-functional.

### 4. Custom Exceptions Are Dead Code

Five exception classes are defined. Zero are raised. All errors either propagate as raw SDK exceptions or are swallowed into `ToolResult.is_error`.

### 5. Duplicate Code

- `build_client` is defined identically in both `client/factory.py` and `client/openai.py`
- `DecodingConstraint` and `GrammarConfig` overlap significantly

### 6. Type Safety Gaps

Despite the repo's strict typing policy:
- `GrailTool.__init__` takes `script: Any, limits: Any`
- `Tool.execute` takes `context: Any`
- `ModelAdapter.response_parser` is typed as `Any`
- `ModelAdapter.grammar_builder` second arg is `Any`

### 7. Bug: `response.to_dict()` in OpenAI Client

`openai.py:82` calls `response.to_dict()` which doesn't exist on the `openai` SDK's Pydantic v2 models. Should be `response.model_dump()`. This will crash at runtime on every completion call.

### 8. Bug: Tool Call IDs Dropped by Parser

`QwenResponseParser.parse()` (parsers.py:30) calls `ToolCall.create()` which generates new IDs, discarding the API-provided tool call IDs. This breaks the request-response correlation chain for tool calls.

### 9. Bug: `GrailTool.execute` Always Gets `context=None`

`kernel.py:117` passes `None` as context to `tool.execute()`. `GrailTool.execute` then uses `call_id="unknown"` for all results, making tool result correlation unreliable.

---

## Severity Summary

| Severity | Count | Key Items |
|----------|-------|-----------|
| **Bug** | 3 | `response.to_dict()` crash, dropped tool call IDs, null context |
| **Critical Gap** | 3 | Grail stubbed, events dead, grammar inert |
| **Dead Code** | 5 | `KernelConfig`, `GrammarConfig`, exceptions, `output_str`, `FunctionGemmaResponseParser` |
| **Design Issue** | 4 | Duplicate `build_client`, `Any` types, hardcoded defaults, no adapter registry |
| **Minor** | 6 | Missing `slots=True`, `Union` import, short UUIDs, etc. |

---

## Static Analysis Findings (Pyright/Type Checker)

The following type errors were detected by the project's static analysis:

### `src/structured_agents/models/parsers.py`

- **Line 35 — Variable shadowing with type mismatch.** `tool_calls` parameter is `list[dict[str, Any]] | None`, but line 35 reassigns it to `list[ToolCall]` (from `_parse_xml_tool_calls`). This shadows the parameter with an incompatible type. Line 37 then returns this as `list[dict]`, causing a type error.

### `src/structured_agents/client/openai.py`

- **Lines 43-45 — OpenAI SDK type incompatibilities.** The `messages` parameter is `list[dict[str, Any]]` but the SDK expects `Iterable[ChatCompletionMessageParam]`. Similarly, `tools` and `tool_choice` use generic types instead of the SDK's specific union types. These pass at runtime via duck typing but fail strict type checking.

- **Lines 62-63 — `ChatCompletionMessageCustomToolCall` lacks `.function`.** The SDK's tool call objects may not always have a `.function` attribute depending on the tool call type. This is a potential runtime error with custom tool calling modes.

### `demo_v03.py`

- **Lines 238, 301, 527 — List invariance.** `list[GrailTool]` is not assignable to `list[Tool]` because `list` is invariant. `AgentKernel.tools` should be typed as `Sequence[Tool]` instead of `list[Tool]`.

---

## Recommendations (Priority Order)

1. **Fix `response.to_dict()` → `response.model_dump()`** — Runtime crash blocker
2. **Fix tool call ID preservation** — Correctness bug in parser
3. **Pass `ToolCall` as context to `tool.execute()`** — Correlation bug
4. **Implement `discover_tools()` with `grail.load()`** — Core feature
5. **Emit all events in kernel `step()` and `run()`** — Observer system
6. **Wire grammar constraint pipeline** — Core feature
7. **Remove duplicate `build_client`** — Pick one location
8. **Type `response_parser`, `script`, `context`** — Type safety
9. **Clean up dead code** — `KernelConfig`, `GrammarConfig`, unused exceptions
10. **Add adapter registry** — Map model names to parser/grammar combos
