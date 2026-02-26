# Configuration & Architecture Review: structured-agents v0.3.0

**Date:** 2026-02-26
**Scope:** pyproject.toml, ARCHITECTURE.md, README.md, __init__.py, demo scripts, .pym agents

---

## 1. pyproject.toml

### Version
- `version = "0.3.0"` -- correct.

### Dependencies

| Dependency | Declared | Notes |
|---|---|---|
| pydantic>=2.0 | Yes | Not used anywhere in v0.3.0 source (types.py uses dataclasses, not Pydantic). Dead dependency. |
| httpx>=0.25 | Yes | Only used in `demo/workspace_agent_demo.py` preflight check, not in library core. Questionable as a hard dep. |
| openai>=1.0 | Yes | Correct -- needed by `client/openai.py`. |
| pyyaml>=6.0 | Yes | Used in `agent.py` for bundle loading. Correct. |
| jinja2>=3.0 | Yes | Not imported anywhere in v0.3.0 source tree. Dead dependency (was likely used by old bundle template system). |
| grail | Yes (unpinned, git source) | Correct -- needed for GrailTool. |
| fsdantic | Yes (git source) | Not imported anywhere in v0.3.0 source tree. Dead dependency. |
| xgrammar==0.1.29 | Yes (pinned) | Not imported in any v0.3.0 source module. The grammar package (`grammar/config.py`, `grammar/pipeline.py`) defines config/pipeline abstractions but does not import xgrammar itself. Dead dependency at library level (may be needed at runtime by vLLM). |
| vllm>=0.15.1 | Yes | Not imported anywhere in library source. vLLM is the server, not a library import. Should be an optional/dev dependency, not a hard install requirement. Installing vllm pulls ~10GB of CUDA wheels. |

### CRITICAL: vllm as hard dependency
Declaring `vllm>=0.15.1` as a hard install dependency means `pip install structured-agents` will attempt to install the entire vLLM server stack including CUDA libraries. This is almost certainly wrong -- the library communicates with vLLM over HTTP via the OpenAI-compatible API. vLLM should be an optional dependency or removed entirely from install requirements.

### Build system
- Uses hatchling, packages from `src/structured_agents`. Correct.
- `tool.hatch.build.targets.wheel.packages = ["src/structured_agents"]` -- correct.

### Dev dependencies
- pytest, pytest-asyncio, respx -- reasonable.

### Commented-out dependency
- `cairn` is commented out in `[tool.uv.sources]`. Should be removed if not needed.

---

## 2. Public API (__init__.py)

### v0.3.0 API surface

The `__init__.py` exports a clean, well-organized set of symbols grouped by domain:

- **Types:** Message, ToolCall, ToolResult, ToolSchema, TokenUsage, StepResult, RunResult
- **Tools:** Tool, GrailTool
- **Models:** ModelAdapter, QwenResponseParser
- **Grammar:** DecodingConstraint, ConstraintPipeline
- **Events:** Observer, NullObserver, Event, + 6 event types
- **Core:** AgentKernel, Agent, AgentManifest
- **Client:** LLMClient, OpenAICompatibleClient, build_client

All imports resolve to actual modules. Verified against source tree.

### Missing from public API

| Symbol | Location | Should export? |
|---|---|---|
| `KernelConfig` | `types.py:14` | YES -- referenced by README and demo_steps scripts but NOT exported from `__init__.py` |
| `CompletionResponse` | `client/__init__.py` | Maybe -- useful for custom client implementations |
| `discover_tools` | `tools/__init__.py` | Maybe -- used in demo_v03.py via direct grail import |
| `ResponseParser` | `models/__init__.py` | Maybe -- protocol for custom parsers |
| `FunctionGemmaResponseParser` | `models/__init__.py` | Maybe -- only other parser |
| `StructuredAgentsError` hierarchy | `exceptions.py` | YES -- users need to catch errors |
| `load_manifest` | `agent.py` | Maybe -- alternative to Agent.from_bundle |

### CRITICAL: KernelConfig not exported
`KernelConfig` is defined in `types.py` but NOT in `__init__.py`'s `__all__`. The README Quick Start code, ARCHITECTURE.md, and multiple demo_steps scripts all reference `from structured_agents import KernelConfig`. This import will fail.

### Inconsistency: Two API styles coexist

The v0.3.0 `__init__.py` exports `AgentKernel` with constructor params `(client, adapter, tools, observer, ...)`, while the README and workspace demo show `AgentKernel(config=KernelConfig(...), plugin=..., tool_source=...)`. These are **two completely different constructor signatures**. The actual `kernel.py` uses the `(client, adapter, tools, observer)` style. The README code will not work.

---

## 3. ARCHITECTURE.md vs. Implementation

### Major discrepancies

| ARCHITECTURE.md says | Actual v0.3.0 source | Severity |
|---|---|---|
| `structured_agents.plugins` module with `ComposedModelPlugin`, `FunctionGemmaPlugin`, `QwenPlugin` | No `plugins/` package exists. Models use `ModelAdapter` + `ResponseParser`. | HIGH |
| `structured_agents.tool_sources` with `RegistryBackendToolSource` | No `tool_sources/` package exists. Kernel takes `tools: list[Tool]` directly. | HIGH |
| `ToolRegistry` and `ToolBackend` separation (`PythonBackend`, `GrailBackend`, `PythonRegistry`, `GrailRegistry`) | No `backends/` or `registries/` packages exist. | HIGH |
| `structured_agents.bundles` with `AgentBundle`, `bundle.yaml` loading | No `bundles/` package exists. `agent.py` has a minimal `load_manifest`. | HIGH |
| `CompositeObserver` for fanning out events | No `CompositeObserver` in source. Only `Observer` protocol and `NullObserver`. | MEDIUM |
| `HistoryStrategy` for history trimming | Not implemented. `max_history_messages` field exists but unused. | MEDIUM |
| `ToolExecutionStrategy` for parallel execution | Not implemented. `max_concurrency` field on kernel handles this. | LOW |
| `GrammarConfig` with modes (ebnf, structural_tag, json_schema) | Grammar package has `DecodingConstraint` and `ConstraintPipeline`, different abstraction. | MEDIUM |

**Verdict:** ARCHITECTURE.md describes a pre-v0.3.0 or planned future architecture, NOT the current implementation. It is essentially a design document for features that were either removed during the v0.3.0 refactor or not yet implemented. It will mislead any developer or agent trying to understand the codebase.

---

## 4. README.md vs. Implementation

### Quick Start code
The README Quick Start imports `KernelConfig`, `FunctionGemmaPlugin`, `RegistryBackendToolSource`, `PythonBackend`, `PythonRegistry` -- **none of which exist in the v0.3.0 source** (except `KernelConfig` which exists but isn't exported).

The README's `AgentKernel` constructor uses `config=`, `plugin=`, `tool_source=` -- the actual constructor takes `client=`, `adapter=`, `tools=`.

### Tool Sources section
References `GrailBackend`, `GrailBackendConfig`, `GrailRegistry`, `GrailRegistryConfig`, `RegistryBackendToolSource` -- none exist.

### Bundles section
References `load_bundle` from `structured_agents` -- not exported. References `bundle.get_plugin()`, `bundle.build_initial_messages()`, `bundle.build_tool_source()` -- `AgentManifest` has none of these methods.

### Observability section
References `CompositeObserver` -- does not exist.

### Parallel Tool Execution section
References `ToolExecutionStrategy` -- does not exist.

**Verdict:** The README describes an API that does not match the v0.3.0 implementation. Nearly every code example will fail.

---

## 5. Demo Scripts

### demo_v03.py (root)
- Uses `__init__.py` exports directly. **Should work** as all imports resolve.
- Uses `GrailTool`, `ModelAdapter`, `AgentKernel(client=, adapter=, tools=)` -- matches actual API.
- The `DemoObserver` uses `emit(event)` pattern -- matches `Observer` protocol.
- `build_client({...})` pattern -- matches `client/factory.py`.
- **Status: FUNCTIONAL** (assuming vLLM server is available)

### demo/workspace_agent_demo.py
- Imports from 7 non-existent modules: `bundles`, `bundles.loader`, `observer`, `registries.grail`, `backends.grail`, `tool_sources.registry_backend`, `plugins.qwen`, `plugins.registry`.
- Also imports `KernelConfig`, `ToolExecutionStrategy` from `structured_agents` -- neither exported.
- References `GrammarConfig` from `grammar.config` -- actual module has `DecodingConstraint`.
- **Status: COMPLETELY BROKEN** -- will crash on import.

### demo/demo_steps/ (step01-step14)
- Multiple scripts import `KernelConfig` and `QwenPlugin` from `structured_agents` -- neither exported.
- **Status: BROKEN** -- will crash on import.

---

## 6. .pym Agent Scripts

### demo_tools/ (3 files)
- `add.pym`, `multiply.pym`, `truncate.pym` -- use `from grail import external, Input` or `from grail import Input`.
- `add.pym` and `multiply.pym` import `external` but never use it (unused import).
- Structure is minimal and correct for grail 3.0.0 convention (Input declarations, computation, bare result expression).

### agents/code_helper/ (2 files)
- `generate_docstring.pym`, `summarize_code.pym` -- use `from grail import Input`.
- Properly structured.

### agents/shellper_demo/ (20 files)
- Shell command wrappers (ls, cat, grep, find, etc.).
- Use `from grail import Input` pattern.
- These appear to be demo/test tools simulating shell operations with hardcoded responses.
- `ls.pym` returns hardcoded file lists, not actual filesystem operations.

### demo/agents/workspace_agent/ (6 .pym files + bundle.yaml)
- Properly structured grail scripts.
- Use `from grail import Input` pattern.
- Include externals.json, inputs.json, check.json, stubs.pyi -- full grail toolchain artifacts.
- `bundle.yaml` is well-structured but references the pre-v0.3.0 `plugin: "qwen"` and `GrammarConfig` schema.

---

## 7. Packaging Issues

### Wheel contents
`tool.hatch.build.targets.wheel.packages = ["src/structured_agents"]` will package only the library source. The `agents/`, `demo/`, `demo_tools/` directories are NOT included in the wheel. This is correct for a library distribution.

### Missing py.typed marker
No `py.typed` file exists in `src/structured_agents/`. For a library that emphasizes full typing, this marker should be present so downstream type checkers respect the type annotations.

### No entry points
No console scripts or entry points defined. This is fine for a library-only package.

---

## 8. Leftover / Stale Artifacts

| Item | Issue |
|---|---|
| `demo/workspace_agent_demo.py` | Imports from 7+ non-existent modules. Pre-v0.3.0 code that was never updated. |
| `demo/demo_steps/step01-step14` | Import `KernelConfig`, `QwenPlugin` which don't exist in public API. Pre-v0.3.0. |
| `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md` | Planning doc, should not ship. |
| `demo/WORKSPACE_AGENT_DEMO_IMPROVEMENT.md` | Planning doc. |
| `demo/WORKSPACE_AGENT_CONVO.md` | Conversation log. |
| `demo/DEMO_IMPLEMENTATION_PLAN.md` | Planning doc. |
| `demo/DEMO_CONCEPT.md` | Planning doc. |
| `demo/demo_steps/*/run.log` | Runtime logs checked into repo. |
| `demo/__pycache__/` | Should be gitignored. |
| `ARCHITECTURE.md` | Describes pre-v0.3.0 architecture with modules that don't exist. |
| `README.md` | All code examples use pre-v0.3.0 API. |
| Commented `cairn` in pyproject.toml | Dead reference. |

---

## 9. Summary of Critical Findings

### P0 - Blocking
1. **vllm is a hard install dependency** -- will force ~10GB CUDA install on `pip install structured-agents`. Should be optional or removed.
2. **README code examples are all broken** -- every example uses a pre-v0.3.0 API (`KernelConfig`, `FunctionGemmaPlugin`, `RegistryBackendToolSource`, `CompositeObserver`, etc.) that doesn't exist.
3. **ARCHITECTURE.md describes a different codebase** -- references 6+ modules (`plugins`, `bundles`, `tool_sources`, `registries`, `backends`, `observer`) that don't exist in v0.3.0.
4. **workspace_agent_demo.py is completely broken** -- imports from 7+ non-existent packages.

### P1 - High
5. **KernelConfig not exported** from `__init__.py` but used in multiple demo scripts and README.
6. **4 dead dependencies** in pyproject.toml: pydantic, jinja2, fsdantic, httpx (not used in library core).
7. **Exception hierarchy not exported** -- `StructuredAgentsError` and subclasses exist but are not in `__init__.py`.

### P2 - Medium
8. **No py.typed marker** for downstream type checker support.
9. **Run logs and __pycache__ checked into repo** under demo/.
10. **Unused `external` import** in demo_tools .pym files.
11. **`max_history_messages` on AgentKernel** is defined but never used -- history grows unbounded.

---

## 10. Type Errors (from static analysis)

The following type errors exist in the v0.3.0 source:

### kernel.py / demo_v03.py -- list covariance
- `AgentKernel.tools` is typed `list[Tool]`, but `list[GrailTool]` is passed. `list` is invariant; should use `Sequence[Tool]` instead. (3 occurrences in demo_v03.py)

### models/parsers.py -- ToolCall/dict confusion
- `QwenResponseParser.parse()` assigns `list[ToolCall]` to a variable typed `list[dict[str, Any]] | None`, then returns the wrong type in error path. The parser's internal type handling is inconsistent.

### client/openai.py -- OpenAI SDK type mismatches (5 errors)
- Passes `list[dict[str, Any]]` where OpenAI SDK expects `Iterable[ChatCompletionMessageParam]`.
- Passes `str` for `tool_choice` where SDK expects `Literal['none', 'auto', 'required'] | ChatCompletionNamedToolChoiceParam`.
- Accesses `.function` on `ChatCompletionMessageCustomToolCall` which doesn't have that attribute.
- These indicate the client wrapper was written against a different version of the `openai` SDK.
