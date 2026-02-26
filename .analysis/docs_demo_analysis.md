# Documentation & Demo Analysis: structured-agents

**Date:** 2026-02-26
**Scope:** README.md, ARCHITECTURE.md, all demo files, `__init__.py` exports

---

## 1. README.md vs Actual API

The README describes an API that **does not exist** in the codebase. It documents a pre-refactor architecture that was never cleaned up after the v0.3.0 simplification.

### Symbols README exports that don't exist

| README Symbol | Import Path in README | Exists? |
|---|---|---|
| `FunctionGemmaPlugin` | `structured_agents` | NO — not in `__init__.py` or any module |
| `KernelConfig` (Pydantic) | `structured_agents` | PARTIAL — exists in `types.py` but is a bare class (not Pydantic), not exported from `__init__.py`, and not used by `AgentKernel` |
| `ToolExecutionStrategy` | `structured_agents` | NO — not defined anywhere |
| `CompositeObserver` | `structured_agents` | NO — not defined anywhere |
| `PythonBackend` | `structured_agents.backends` | NO — `backends` package doesn't exist |
| `PythonRegistry` | `structured_agents.registries` | NO — `registries` package doesn't exist |
| `GrailRegistry` | `structured_agents.registries` | NO |
| `GrailRegistryConfig` | `structured_agents.registries` | NO |
| `GrailBackend` | `structured_agents.backends` | NO |
| `GrailBackendConfig` | `structured_agents.backends` | NO |
| `RegistryBackendToolSource` | `structured_agents.tool_sources` | NO — `tool_sources` package doesn't exist |
| `ToolSource` (protocol) | conceptual | NO — not defined as a protocol |
| `ModelPlugin` (protocol) | `structured_agents.plugins` | NO — `plugins` package doesn't exist |
| `ComposedModelPlugin` | `structured_agents.plugins` | NO |
| `QwenPlugin` | `structured_agents.plugins` | NO — `plugins` package doesn't exist |
| `load_bundle` | `structured_agents` | NO — not exported or importable |
| `AgentBundle` | `structured_agents.bundles` | NO — `bundles` package doesn't exist |
| `HistoryStrategy` | conceptual | NO — not defined |

### Symbols that actually exist in `__init__.py`

```python
# Types
Message, ToolCall, ToolResult, ToolSchema, TokenUsage, StepResult, RunResult

# Tools
Tool, GrailTool

# Models
ModelAdapter, QwenResponseParser

# Grammar
DecodingConstraint, ConstraintPipeline

# Events
Observer, NullObserver, Event, KernelStartEvent, KernelEndEvent,
ModelRequestEvent, ModelResponseEvent, ToolCallEvent, ToolResultEvent, TurnCompleteEvent

# Core
AgentKernel, Agent, AgentManifest

# Client
LLMClient, OpenAICompatibleClient, build_client
```

### README Quick Start code: Would it run?

**No.** The Quick Start imports `FunctionGemmaPlugin`, `KernelConfig`, `PythonBackend`, `PythonRegistry`, `RegistryBackendToolSource` — none of which exist. It also calls `kernel.run()` with a `tool_source` constructor argument that `AgentKernel` doesn't accept (it takes `tools: list[Tool]`).

### README "Tool Sources" section: Valid?

**No.** Imports `GrailBackend`, `GrailBackendConfig`, `GrailRegistry`, `GrailRegistryConfig`, `RegistryBackendToolSource` from packages that don't exist.

### README "Bundles" section: Valid?

**No.** `load_bundle` and `AgentBundle` don't exist. `bundle.get_plugin()`, `bundle.build_initial_messages()`, `bundle.build_tool_source()` are phantom methods.

### README "Observability" section: Valid?

**Partially.** `NullObserver` exists. `CompositeObserver` does not.

### README "Client Reuse" section: Valid?

**Partially.** `build_client` exists but takes a `dict`, not a `KernelConfig` — the README shows `build_client(config)` where `config` is a `KernelConfig`.

### Summary

The README describes what appears to be a **planned v0.3.1+ API** that was never implemented. The actual v0.3.0 API is radically simpler: no plugins, no registries, no backends, no tool sources, no bundles. The README is **100% fiction** for all sections except the project description and license.

---

## 2. ARCHITECTURE.md vs Actual Module Structure

### Modules ARCHITECTURE.md describes

| Module | Described | Exists? |
|---|---|---|
| `structured_agents.kernel` | AgentKernel | YES — but with different constructor API |
| `structured_agents.plugins` | ComposedModelPlugin, FunctionGemmaPlugin, QwenPlugin | NO — package doesn't exist |
| `structured_agents.tool_sources` | RegistryBackendToolSource | NO |
| `structured_agents.backends` | PythonBackend, GrailBackend | NO |
| `structured_agents.registries` | PythonRegistry, GrailRegistry | NO |
| `structured_agents.bundles` | AgentBundle, bundle.yaml | NO |
| `structured_agents.client` | OpenAICompatibleClient, build_client | YES |
| `structured_agents.observer` | CompositeObserver, NullObserver | PARTIAL — `events/observer.py` exists with `NullObserver`; no `CompositeObserver` |

### Concepts ARCHITECTURE.md describes that don't exist

- **MessageFormatter, ToolFormatter, ResponseParser, GrammarProvider** protocols — none exist
- **ComposedModelPlugin** — doesn't exist
- **ToolSource** protocol — doesn't exist
- **ToolRegistry** and **ToolBackend** protocols — don't exist
- **HistoryStrategy** protocol — doesn't exist
- **`StructuredAgentsError`** base exception — `exceptions.py` exists but is not imported/exported
- **Event lifecycle** — documented 7 events; `AgentKernel.run()` only emits `KernelStartEvent`, never emits the other 6

### What actually exists in `src/structured_agents/`

```
__init__.py          — top-level exports (v0.3.0 API)
types.py             — Message, ToolCall, ToolResult, ToolSchema, TokenUsage, StepResult, RunResult, KernelConfig (dead)
kernel.py            — AgentKernel (client, adapter, tools, observer pattern)
agent.py             — Agent, AgentManifest, load_manifest
exceptions.py        — (exists, not exported)
client/
  __init__.py
  protocol.py        — LLMClient, CompletionResponse
  openai.py          — OpenAICompatibleClient, build_client
  factory.py         — another build_client (duplicate!)
tools/
  __init__.py
  protocol.py        — Tool protocol
  grail.py           — GrailTool, discover_tools
models/
  __init__.py
  adapter.py         — ModelAdapter
  parsers.py         — ResponseParser, QwenResponseParser, FunctionGemmaResponseParser
events/
  __init__.py
  types.py           — Event dataclasses (7 types)
  observer.py        — Observer, NullObserver
grammar/
  __init__.py
  config.py          — DecodingConstraint
  pipeline.py        — ConstraintPipeline
```

### Summary

ARCHITECTURE.md describes an API surface ~3x larger than what exists. It references 6 packages (`plugins`, `backends`, `registries`, `tool_sources`, `bundles`, `observer`) that don't exist. The described data flow and extensibility points are aspirational.

---

## 3. Demo Scripts: Working vs Broken

### `demo_v03.py` (root-level)

**Status: PARTIALLY WORKS (types/events demos only)**

- Imports from `structured_agents` using the v0.3.0 API: **All imports resolve.**
- `demo_types()` — WORKS (pure dataclass construction)
- `demo_grammar_pipeline()` — WORKS (pure pipeline logic, no server needed)
- `demo_events()` — WORKS (constructs events and NullObserver)
- `demo_kernel_direct()` — BROKEN at runtime: `build_client` is called with a `dict` which is correct, but `AgentKernel` is constructed with `max_tokens` and `temperature` kwargs which exist on the dataclass; however, `kernel.run()` calls `self.client.chat_completion()` which hits BUG-1 (`response.to_dict()` crash). Also references `demo_tools/` directory for `.pym` scripts.
- `demo_agent_api()` — Same runtime crash path + depends on `demo_tools/`
- `demo_full_conversation()` — Same

**Overall: 3/6 demos work. The 3 that require a server hit BUG-1.**

### `demo/workspace_agent_demo.py`

**Status: COMPLETELY BROKEN — fails at import time**

Imports from packages that don't exist:
- `structured_agents.bundles` — NO
- `structured_agents.observer` — NO (it's `events.observer`)
- `structured_agents.registries.grail` — NO
- `structured_agents.backends.grail` — NO
- `structured_agents.tool_sources.registry_backend` — NO
- `structured_agents.plugins.qwen` — NO
- `structured_agents.plugins.registry` — NO

Also imports `KernelConfig`, `ToolExecutionStrategy` from `structured_agents` — neither exported.

**This demo was written for the aspirational API that doesn't exist.**

### `demo/demo_steps/step01_verify_vllm.py`

**Status: BROKEN at import time**

Imports `KernelConfig`, `QwenPlugin` from `structured_agents` — neither is exported. Also imports `build_client` from `structured_agents.client.factory` which **does** exist but is a duplicate of `client/openai.py:build_client`.

### `demo/demo_steps/step02_basic_chat.py`

**Status: BROKEN** — same `KernelConfig`, `QwenPlugin` import failures.

### `demo/demo_steps/step03_single_grail.py`

**Status: BROKEN at import time**

Imports `GrailBackend`, `GrailBackendConfig` from `structured_agents` — neither exported.

### `demo/demo_steps/step04_custom_grail.py`

**Status: BROKEN** — same as step03.

### `demo/demo_steps/step05_grail_dispatcher.py`

**Status: BROKEN** — same as step03.

### `demo/demo_steps/step06_chat_agent.py`

**Status: BROKEN** — `KernelConfig`, `QwenPlugin` import failures.

### `demo/demo_steps/step07_grammar_decoding.py`

**Status: BROKEN** — `KernelConfig`, `QwenPlugin`, `ToolSchema` — `ToolSchema` IS exported but `KernelConfig` and `QwenPlugin` are not.

### `demo/demo_steps/step08_shell_agent_single.py`

**Status: BROKEN** — imports `KernelConfig`, `QwenPlugin`, `GrailBackend`, `GrailBackendConfig`, `build_client` from `structured_agents` — `KernelConfig`, `QwenPlugin`, `GrailBackend`, `GrailBackendConfig` not exported.

### `demo/demo_steps/step09_shell_agent_extended.py`

**Status: BROKEN** — same as step08.

### `demo/demo_steps/step10_code_agent.py`

**Status: BROKEN** — imports `QwenPlugin`, `GrailBackend`, `GrailBackendConfig` from `structured_agents`. None exported.

### `demo/demo_steps/step12_calculator_agent.py`

**Status: BROKEN** — imports `KernelConfig`, `QwenPlugin` from `structured_agents`. Neither exported.

### `demo/demo_steps/step13_filesystem_agent.py`

**Status: BROKEN** — imports `KernelConfig`, `QwenPlugin`, `GrailBackend`, `GrailBackendConfig`, `build_client`. Most not exported.

### `demo/demo_steps/step14_reasoning_agent.py`

**Status: BROKEN** — same `KernelConfig`, `QwenPlugin` import failures.

### `demo/demo_steps/test_grammar_modes.py`

**Status: BROKEN** — same `KernelConfig`, `QwenPlugin` import failures.

### Summary Table

| Demo | Import OK? | Runs? | Notes |
|---|---|---|---|
| `demo_v03.py` (types) | YES | YES | Pure dataclass demos |
| `demo_v03.py` (grammar) | YES | YES | Pure pipeline logic |
| `demo_v03.py` (events) | YES | YES | NullObserver test |
| `demo_v03.py` (kernel/agent) | YES | NO | BUG-1 crash at runtime |
| `demo/workspace_agent_demo.py` | NO | NO | Imports non-existent packages |
| `demo/demo_steps/step01` | NO | NO | `KernelConfig`, `QwenPlugin` |
| `demo/demo_steps/step02` | NO | NO | Same |
| `demo/demo_steps/step03` | NO | NO | `GrailBackend`, `GrailBackendConfig` |
| `demo/demo_steps/step04` | NO | NO | Same |
| `demo/demo_steps/step05` | NO | NO | Same |
| `demo/demo_steps/step06` | NO | NO | `KernelConfig`, `QwenPlugin` |
| `demo/demo_steps/step07` | NO | NO | Same |
| `demo/demo_steps/step08` | NO | NO | Multiple missing |
| `demo/demo_steps/step09` | NO | NO | Same |
| `demo/demo_steps/step10` | NO | NO | Same |
| `demo/demo_steps/step12` | NO | NO | Same |
| `demo/demo_steps/step13` | NO | NO | Same |
| `demo/demo_steps/step14` | NO | NO | Same |
| `demo/demo_steps/test_grammar_modes.py` | NO | NO | Same |

**Result: 3 of 19 demo entry points work. 0 of 19 work end-to-end with a server.**

---

## 4. Two Conflicting APIs in the Demos

The demos reveal that two different APIs were being developed simultaneously:

### API A: v0.3.0 (actual — `demo_v03.py`)
- `AgentKernel(client, adapter, tools, observer)`
- `ModelAdapter(name, grammar_builder, response_parser)`
- `build_client(dict)` → `OpenAICompatibleClient`
- `GrailTool(script, limits)` with `Tool.schema` / `Tool.execute()`
- `DecodingConstraint` + `ConstraintPipeline`
- Observer via `emit(Event)`

### API B: aspirational (all `demo/demo_steps/*` and `demo/workspace_agent_demo.py`)
- `AgentKernel(config=KernelConfig, plugin=QwenPlugin, tool_source=ToolSource, observer, grammar_config)`
- `QwenPlugin` with `format_messages()`, `format_tools()`, `build_grammar()`, `parse_response()`
- `build_client(KernelConfig)` → client
- `GrailBackend(GrailBackendConfig)` with `backend.execute(tool_call, schema, context)`
- `GrailRegistry(GrailRegistryConfig)` with auto-discovery
- `RegistryBackendToolSource(registry, backend)`
- `load_bundle(path)` → `AgentBundle` with `get_plugin()`, `build_initial_messages()`, `get_grammar_config()`
- `GrammarConfig(mode="structural_tag")`
- `CompositeObserver([obs1, obs2])`
- Observer via individual `on_*` methods (`on_kernel_start`, `on_model_request`, etc.)
- `PluginRegistry` with `list_plugins()`, `get(name)`
- `KernelConfig` as Pydantic model with `base_url`, `model`, `temperature`, etc.

**These two APIs are fundamentally incompatible.** API B is far more sophisticated and appears to be what was planned for v0.3.1+, but none of its infrastructure exists.

---

## 5. Stale Files & Cleanup Candidates

### Root-level stale docs

| File | Issue |
|---|---|
| `README.md` | Documents entirely phantom API |
| `ARCHITECTURE.md` | Documents modules/protocols that don't exist |
| `V031_REFACTORING_GUIDE.md` | Refactoring guide for bugs — useful but should be in `docs/plans/` |
| `V031_REFACTORING_PLAN.md` | Same |
| `CODE_REVIEW.md` | Review output — should be in `.analysis/` or `docs/` |

### Demo stale files

| File/Dir | Issue |
|---|---|
| `demo/workspace_agent_demo.py` | Written for API B; completely broken |
| `demo/demo_steps/step01-step14` | All written for API B; all broken at import |
| `demo/demo_steps/test_grammar_modes.py` | API B; broken |
| `demo/demo_steps/scripts/` | Grail scripts for demos that can't run |
| `demo/demo_steps/agents/` | Grail agent configs for broken demos |
| `demo/agents/workspace_agent/` | Bundle configs for non-existent bundle system |
| `demo/agents/workspace_agent/state/` | Runtime artifact directory |
| `demo/logs/` | 5 log files from demo runs |
| `demo/__pycache__/` | Python cache |
| `demo/WORKSPACE_AGENT_DEMO_IMPROVEMENT.md` | Planning doc for broken demo |
| `demo/WORKSPACE_AGENT_CONVO.md` | Conversation log |
| `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md` | Plan for broken demo |
| `demo/DEMO_IMPLEMENTATION_PLAN.md` | Plan for demo steps |
| `demo/DEMO_CONCEPT.md` | Concept doc for demos |
| `demo/overview.md` | Overview of demo framework |

### Root-level stale dirs

| Dir | Issue |
|---|---|
| `demo_tools/` | `.pym` scripts referenced by `demo_v03.py` (only demo that partially works) |
| `agents/` | Root-level Grail scripts (echo, add_numbers, pwd, ls, etc.) — not referenced by any working code |
| `agents/shellper_demo/` | 18 `.pym` shell utility scripts — orphaned |
| `agents/code_helper/` | `.pym` scripts referenced by broken `step10_code_agent.py` |

### Source-level issues

| File | Issue |
|---|---|
| `src/structured_agents/client/factory.py` | Duplicate `build_client` — also defined in `client/openai.py` |
| `src/structured_agents/exceptions.py` | Exists but never imported/exported |
| `src/structured_agents/types.py:14-18` | `KernelConfig` class — dead code, not a dataclass, never used |

### Docs directory

| File | Issue |
|---|---|
| `docs/plans/V03_IMPLEMENTATION_GUIDE.md` | Historical planning doc |
| `docs/plans/V03_CONCEPT.md` | Historical concept doc |
| `docs/plans/2026-02-25-workspace-demo-refactor.md` | Refactor plan for broken workspace demo |
| `docs/plans/2026-02-25-qwen3-xgrammar-fix.md` | Fix plan |

### .analysis directory (existing)

| File | Issue |
|---|---|
| `.analysis/config_review.md` | Existing review — keep |
| `.analysis/test_review.md` | Existing review — keep |
| `.analysis/source_review.md` | Existing review — keep |

---

## 6. Complete Stale/Broken Artifact List

### Tier 1: Actively Misleading (should fix or remove first)

1. `README.md` — documents phantom API
2. `ARCHITECTURE.md` — documents non-existent modules
3. `demo/workspace_agent_demo.py` — imports 7+ non-existent packages
4. `demo/demo_steps/step01_verify_vllm.py` through `step14_reasoning_agent.py` (13 files) — all broken at import
5. `demo/demo_steps/test_grammar_modes.py` — broken at import

### Tier 2: Dead Code in Source

6. `src/structured_agents/types.py` `KernelConfig` class (lines 14-18)
7. `src/structured_agents/client/factory.py` — duplicate `build_client`
8. `src/structured_agents/exceptions.py` — never imported

### Tier 3: Orphaned Support Files

9. `demo/agents/workspace_agent/` — entire bundle config tree (bundle.yaml, .pym scripts, Grail artifacts)
10. `demo/demo_steps/scripts/` — Grail scripts for broken demos
11. `demo/demo_steps/agents/` — Grail agent for broken demos
12. `agents/` — root-level Grail scripts (6 tools + shellper_demo with 18 scripts)
13. `demo_tools/` — 3 `.pym` scripts (referenced by only partially-working `demo_v03.py`)

### Tier 4: Stale Documentation

14. `V031_REFACTORING_GUIDE.md`
15. `V031_REFACTORING_PLAN.md`
16. `CODE_REVIEW.md`
17. `demo/WORKSPACE_AGENT_DEMO_IMPROVEMENT.md`
18. `demo/WORKSPACE_AGENT_CONVO.md`
19. `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md`
20. `demo/DEMO_IMPLEMENTATION_PLAN.md`
21. `demo/DEMO_CONCEPT.md`
22. `demo/overview.md`
23. `docs/plans/V03_IMPLEMENTATION_GUIDE.md`
24. `docs/plans/V03_CONCEPT.md`
25. `docs/plans/2026-02-25-workspace-demo-refactor.md`
26. `docs/plans/2026-02-25-qwen3-xgrammar-fix.md`

### Tier 5: Runtime Artifacts

27. `demo/logs/` — 5 log files
28. `demo/__pycache__/`
29. `demo/agents/workspace_agent/state/`
30. Various `run.log` files inside Grail script directories

---

## 7. Root Cause

The codebase underwent a v0.3.0 refactor that collapsed ~51 files into ~20. The refactor successfully simplified the internal architecture to 5 core concepts (Tool, ModelAdapter, DecodingConstraint, Kernel, Agent). However:

1. **README and ARCHITECTURE.md were never updated** — they still describe the pre-refactor or aspirational API
2. **All demo_steps were written against an API (API B) that was planned but never built** — they import from `plugins`, `backends`, `registries`, `tool_sources`, `bundles` packages that don't exist
3. **The workspace_agent_demo was the "gold standard" demo** targeting API B — entirely broken
4. **Only `demo_v03.py` uses the actual v0.3.0 API** — and even it hits runtime bugs when calling the server

The codebase is in a state where the implementation went one direction (simplified v0.3.0) while all supporting materials (docs, demos, planning) went another direction (feature-rich API B), and neither side was reconciled.
