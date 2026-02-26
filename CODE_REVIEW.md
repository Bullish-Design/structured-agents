# Code Review: structured-agents v0.3.0

**Date:** 2026-02-26
**Scope:** Full codebase review — source, tests, config, documentation, demos
**Review type:** Post-refactor architecture and quality audit

---

## Executive Summary

The v0.3.0 refactor successfully collapses a 51-file, 6-layer architecture into ~20 files with 5 clean core concepts (Tool, ModelAdapter, DecodingConstraint, Kernel, Agent). The simplified design is directionally correct and the module boundaries are well-chosen.

However, the refactor is **incomplete**. Three of the library's core differentiating features are non-functional: Grail tool discovery is stubbed, grammar-constrained decoding is wired but inert, and the observer/event system only emits 1 of 7 event types. There are 3 runtime bugs that will crash or corrupt behavior in production. The test suite (16 tests, 0 negative paths) provides false confidence. Documentation (README, ARCHITECTURE.md) describes a pre-v0.3.0 API that no longer exists. Four declared dependencies are unused, and `vllm` as a hard install dependency will force ~10GB of CUDA wheels on any consumer.

**Verdict:** The architecture is sound but the implementation needs a completion pass before it can be considered a viable v0.3.0 release.

---

## Table of Contents

1. [Runtime Bugs](#1-runtime-bugs)
2. [Non-Functional Core Features](#2-non-functional-core-features)
3. [Dead Code](#3-dead-code)
4. [Architecture & Design Issues](#4-architecture--design-issues)
5. [Type Safety](#5-type-safety)
6. [Test Suite](#6-test-suite)
7. [Documentation & Demos](#7-documentation--demos)
8. [Dependencies & Packaging](#8-dependencies--packaging)
9. [Module-Level Notes](#9-module-level-notes)
10. [Recommendations](#10-recommendations)

---

## 1. Runtime Bugs

### BUG-1: `response.to_dict()` crashes every completion call
**File:** `src/structured_agents/client/openai.py:82`

The OpenAI SDK's Pydantic v2 response objects use `model_dump()`, not `to_dict()`. This will raise `AttributeError` on every LLM call.

```python
# Current (broken)
raw_response=response.to_dict(),

# Fix
raw_response=response.model_dump(),
```

### BUG-2: Parser drops tool call IDs, breaking correlation
**File:** `src/structured_agents/models/parsers.py:30`

`QwenResponseParser.parse()` calls `ToolCall.create()` which generates **new** UUIDs, discarding the API-provided `tc["id"]`. The model's response references one ID; the tool result will carry a different one. This breaks the tool-call-to-tool-result correlation chain that OpenAI-compatible APIs rely on.

```python
# Current (broken) — generates new ID, discards tc["id"]
parsed.append(ToolCall.create(func["name"], args))

# Fix — preserve the original ID
parsed.append(ToolCall(id=tc["id"], name=func["name"], arguments=args))
```

### BUG-3: Tool context always `None`, call_id always `"unknown"`
**File:** `src/structured_agents/kernel.py:117`

The kernel passes `None` as context to every tool execution:

```python
return await tool.execute(tc.arguments, None)  # tc has .id but it's not passed
```

`GrailTool.execute` then falls back to `call_id="unknown"` for all results. The `ToolCall` object (which has the `.id`) should be passed as context.

---

## 2. Non-Functional Core Features

### FEAT-1: Grail integration is entirely stubbed

The library's stated purpose is structured tool orchestration via Grail `.pym` scripts, but:

- `discover_tools()` returns `[]` (`tools/grail.py:47`) — the function body is a TODO comment
- `GrailTool.__init__` hardcodes `description=f"Tool: {script.name}"` and `parameters={"type": "object", "properties": {}}` — it never introspects the script's `@external` functions or `Input()` declarations to build a real parameter schema
- `grail.load()` is never called anywhere in the codebase
- The model will have no knowledge of what arguments any tool accepts

**Impact:** `Agent.from_bundle()` will always produce an agent with zero tools.

### FEAT-2: Grammar-constrained decoding pipeline is inert

- `ConstraintPipeline` exists but is never instantiated by any production code path
- `Agent.from_bundle()` uses `grammar_builder=lambda t, c: None` — a no-op
- `DecodingConstraint` is never read or applied in the kernel flow
- `xgrammar` (a declared dependency) is never imported anywhere in source
- The `GrammarConfig` dataclass exists in `grammar/config.py` but is unexported and unused

**Impact:** The other core differentiator — forcing models to output valid tool calls via grammar constraints — does nothing.

### FEAT-3: Observer/event system is 85% dead

The kernel defines 7 event types, imports all of them, and accepts an `Observer` — but only emits `KernelStartEvent` (in `kernel.py:149`). It never emits:

- `ModelRequestEvent` (before API call)
- `ModelResponseEvent` (after API call)
- `ToolCallEvent` (before tool execution)
- `ToolResultEvent` (after tool execution)
- `TurnCompleteEvent` (after each turn)
- `KernelEndEvent` (after loop ends)

The 6 unused event type imports at `kernel.py:10-18` confirm these were intended but not implemented.

---

## 3. Dead Code

| Item | Location | Issue |
|------|----------|-------|
| `KernelConfig` | `types.py:14-18` | Plain class (not even a dataclass), never used. `AgentKernel` duplicates its fields individually. |
| `GrammarConfig` | `grammar/config.py:16-33` | Overlaps with `DecodingConstraint` but has different defaults. Unexported, unused. |
| `ToolResult.output_str` | `types.py:104-106` | Identity property — returns `self.output` which is already `str`. No callers. |
| `FunctionGemmaResponseParser` | `models/parsers.py:63-70` | Delegates to a fresh `QwenResponseParser()` on every call. Adds no behavior. |
| Exception hierarchy (5 classes) | `exceptions.py:1-47` | `StructuredAgentsError`, `KernelError`, `ToolExecutionError`, `PluginError`, `BackendError` — none are raised anywhere. |
| `max_history_messages` | `kernel.py:43` | Field exists on `AgentKernel` but is never referenced in `step()` or `run()`. History grows unbounded. |
| `**overrides` parameter | `agent.py:67` | `Agent.from_bundle()` accepts it but never applies it. |

---

## 4. Architecture & Design Issues

### 4.1 Duplicate `build_client`

Two identical `build_client` functions exist:
- `client/factory.py:10-17` (imported by `agent.py`)
- `client/openai.py:89-96` (exported by `client/__init__.py`)

They have inconsistent return type annotations (`OpenAICompatibleClient` vs `LLMClient`). One should be removed.

### 4.2 `ModelAdapter.__post_init__` mutates frozen dataclass

`adapter.py:21-24` uses `object.__setattr__` to work around `frozen=True` immutability. This is a code smell — if defaults need to be set, use a factory classmethod or make the fields non-optional with default factory functions.

### 4.3 Default message formatter serializes tools via `str()`

`adapter.py:34-37` appends tool info as `"Available tools: " + str(tools)`, using Python's `str()` representation of dicts. This produces unreliable, non-standard output that models will struggle to parse. Should use `json.dumps()` or a structured format.

### 4.4 No adapter registry

`Agent.from_bundle()` hardcodes `QwenResponseParser()` regardless of the `manifest.model` value. There's no mapping from model names to parser/grammar-builder pairs. Adding a second model family requires modifying `agent.py` source code.

### 4.5 `_tool_map()` is O(n) per call, called multiple times per step

`kernel.py:48-49` rebuilds the tool lookup dict on every call. It's invoked twice per `step()` (lines 63, 106). Should be cached as an instance attribute, invalidated only when `self.tools` changes.

### 4.6 Hardcoded vLLM URL

`agent.py:82` hardcodes `base_url="http://localhost:8000/v1"`. This should come from the bundle manifest or environment configuration.

### 4.7 No `CompositeObserver`

If a user wants both logging and metrics observers, there's no way to fan out events to multiple observers. A `CompositeObserver` that wraps a list of observers is a common and expected pattern.

### 4.8 `ConstraintPipeline` adds indirection without value

`pipeline.py` wraps a single callable in a class. The `constrain()` method is a 3-line function that checks for empty tools and delegates. There's no chaining, transformation, or validation — a plain function would suffice.

---

## 5. Type Safety

Despite the repository's AGENTS.md requiring "all new Python code must be fully typed" and "avoid `Any` unless unavoidable," several core interfaces use `Any`:

| Location | Type | Should Be |
|----------|------|-----------|
| `tools/grail.py:12` | `script: Any, limits: Any` | `grail.GrailScript`, `grail.Limits \| None` |
| `tools/protocol.py:14` | `context: Any` | A `ToolCallContext` dataclass |
| `models/adapter.py:15` | `response_parser: Any` | `ResponseParser` (the protocol in `parsers.py`) |
| `models/adapter.py:14` | `grammar_builder` 2nd arg `Any` | `DecodingConstraint` |
| `kernel.py:40-41` | `tools: list[Tool]` | `Sequence[Tool]` (list is invariant) |

### Static analysis errors

- `client/openai.py:43-45` — passes `list[dict]` where OpenAI SDK expects `Iterable[ChatCompletionMessageParam]`. Passes at runtime via duck typing but fails strict type checking.
- `models/parsers.py:35` — `tool_calls` variable shadowed with incompatible type (`list[dict] | None` → `list[ToolCall]`).
- `types.py:176` — `RunResult` is `@dataclass(frozen=True)` without `slots=True`, inconsistent with all other frozen dataclasses in the file.

---

## 6. Test Suite

### Quantitative overview

| Metric | Value |
|--------|-------|
| Test files | 12 |
| Test functions | 16 |
| Negative/error-path tests | 0 |
| Parametrized tests | 0 |
| Tests using real fixtures | 0 |
| `conftest.py` files | 0 |
| True integration tests | 0 |

### Critical gaps

1. **Zero negative tests.** No test verifies behavior on: tool execution failure, unknown tool names, `max_turns` exhaustion, malformed API responses, invalid arguments, or any exception path.

2. **The "integration" test is fully mocked.** `test_integration/test_full_agent.py` mocks the client, tools, and grammar builder. It tests mock wiring, not component integration. The real fixtures in `tests/fixtures/sample_bundle/` and `tests/fixtures/grail_tools/` are never used.

3. **`QwenResponseParser._parse_xml_tool_calls()` has zero coverage.** This is the library's core grammar-constrained output parser — arguably the most important function — and it has no tests.

4. **`load_manifest()` has a latent bug.** It reads `data.get("system_prompt")` but the actual bundle YAML fixture nests it under `initial_context.system_prompt`. No test catches this because fixtures are never used.

5. **Weak assertions.** Multiple tests use assertions that would pass on broken implementations:
   - `test_agent_from_bundle_minimal`: `assert agent is not None`
   - `test_grail_tool_execute`: `assert "42" in result.output` (passes on `"error: 42 not found"`)
   - `test_model_adapter_creation`: `assert adapter.grammar_builder is not None`

6. **No shared fixtures.** No `conftest.py` exists. Mock setup is duplicated and inconsistent across test files.

7. **`@pytest.mark.asyncio` used with `asyncio_mode = "auto"`.** Redundant decorators. Harmless but inconsistent.

---

## 7. Documentation & Demos

### README.md — completely stale

Every code example uses a pre-v0.3.0 API. Imports reference `KernelConfig`, `FunctionGemmaPlugin`, `RegistryBackendToolSource`, `PythonBackend`, `PythonRegistry`, `CompositeObserver`, `ToolExecutionStrategy` — **none of which exist** in the v0.3.0 source. The actual `AgentKernel` constructor takes `(client, adapter, tools)`, not `(config, plugin, tool_source)`.

### ARCHITECTURE.md — describes a different codebase

References 6+ modules (`plugins`, `bundles`, `tool_sources`, `registries`, `backends`, `observer`) that don't exist. This document describes either the pre-refactor design or a planned future state, not the current implementation.

### Demo scripts

| Script | Status |
|--------|--------|
| `demo_v03.py` | **Functional** — uses actual v0.3.0 API |
| `demo/workspace_agent_demo.py` | **Broken** — imports from 7+ non-existent modules |
| `demo/demo_steps/step01-step14` | **Broken** — import `KernelConfig`, `QwenPlugin` |

### Stale artifacts checked into repo

- `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md`, `DEMO_CONCEPT.md`, `DEMO_IMPLEMENTATION_PLAN.md` — planning docs
- `demo/WORKSPACE_AGENT_CONVO.md` — conversation log
- `demo/demo_steps/*/run.log` — runtime logs
- `demo/__pycache__/` — bytecode cache

---

## 8. Dependencies & Packaging

### Critical: `vllm` as hard install dependency

`pyproject.toml` declares `vllm>=0.15.1` as a required dependency. The library communicates with vLLM exclusively over HTTP via the OpenAI-compatible API — it never imports `vllm`. Installing `vllm` pulls ~10GB of CUDA wheels. This should be removed from install requirements or moved to an optional extras group.

### Dead dependencies

| Dependency | Status |
|------------|--------|
| `pydantic>=2.0` | Not imported in any v0.3.0 source file. Types use dataclasses. |
| `jinja2>=3.0` | Not imported anywhere. Likely a leftover from old template system. |
| `fsdantic` (git) | Not imported anywhere. |
| `httpx>=0.25` | Only used in `demo/workspace_agent_demo.py` (which is broken). Not used in library. |
| `xgrammar==0.1.29` | Not imported in any source module. May be needed by vLLM at runtime, but the library itself doesn't use it. |

### Missing `py.typed` marker

No `py.typed` file exists in `src/structured_agents/`. For a library emphasizing full typing, this marker is needed so downstream type checkers respect the annotations.

### Commented-out dependency

`cairn` is commented out in `[tool.uv.sources]`. Should be removed.

---

## 9. Module-Level Notes

### `types.py`
- `KernelConfig` is a plain class, not a dataclass — no `__init__`, `__repr__`, or `__eq__`. Likely unintentional.
- Short tool call IDs (`call_{uuid.hex[:8]}`) — only 32 bits of entropy. Consider 12+ chars for high-throughput scenarios.

### `tools/grail.py`
- `GrailTool` assumes `script.run()` is async but this is unverified against the actual grail API signature.
- Schema generation ignores the script's actual inputs/externals.

### `grammar/config.py`
- `DecodingConstraint` and `GrammarConfig` coexist with contradictory defaults: `allow_parallel_calls` defaults to `False` in one and `True` in the other. Same for `send_tools_to_api`.

### `models/parsers.py`
- `json.loads` in the API tool_calls path (line 29) has no error handling. The XML parser path handles `JSONDecodeError` but the standard path doesn't.

### `kernel.py`
- Error handling is absent. The kernel never raises custom exceptions. API errors propagate as raw `openai` SDK exceptions.
- `tool_choice="none"` is explicitly sent when no tools exist (line 87), which may cause issues with some backends.
- Concurrent tool execution (`asyncio.gather`) doesn't isolate per-tool errors. One failing tool kills all concurrent executions.

### `agent.py`
- `agents_dir` path resolution bug: uses `Path(bundle_path).parent` which goes one directory too high when `bundle_path` is a directory.
- `grammar_config` in manifest is hardcoded to `None` — YAML config is never read for grammar settings.
- Observer is not passed from `Agent` to `AgentKernel` during `from_bundle()`.

### `client/openai.py`
- Passes `tools=None` directly to SDK, which may not be handled gracefully in all SDK versions. Should be omitted from kwargs when not present.

---

## 10. Recommendations

### P0 — Fix before any release

1. **Fix the 3 runtime bugs** (BUG-1, BUG-2, BUG-3)
2. **Implement `discover_tools()`** with `grail.load()` — this is the library's core value
3. **Remove `vllm` from hard dependencies** — it's a server, not an import
4. **Rewrite README.md and ARCHITECTURE.md** to match the actual v0.3.0 API

### P1 — Fix before production use

5. **Emit all 7 event types** in kernel `step()` and `run()`
6. **Wire the grammar-constraint pipeline** in `Agent.from_bundle()` and kernel
7. **Remove duplicate `build_client`** — consolidate into one location
8. **Add negative tests** — error paths, max_turns exhaustion, malformed responses
9. **Add real integration tests** using the existing fixtures in `tests/fixtures/`
10. **Clean dead dependencies** from `pyproject.toml`

### P2 — Improve quality

11. **Replace `Any` types** with proper protocols/types on Tool.execute context, ModelAdapter.response_parser, GrailTool constructor
12. **Remove dead code** — `KernelConfig`, `GrammarConfig`, `ToolResult.output_str`, unused exceptions, `FunctionGemmaResponseParser` passthrough
13. **Add `conftest.py`** with shared test fixtures
14. **Add `py.typed`** marker for downstream type checker support
15. **Clean stale demo files** — broken demo_steps, planning docs, run logs, `__pycache__`
16. **Add adapter registry** mapping model names to parser/grammar-builder pairs
17. **Cache `_tool_map()`** instead of rebuilding it on every `step()` call

---

*Detailed per-module analysis is available in `.analysis/source_review.md`, `.analysis/test_review.md`, and `.analysis/config_review.md`.*
