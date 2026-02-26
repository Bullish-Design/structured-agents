# Test Suite & Configuration Analysis

**Repository:** structured-agents v0.3.0
**Generated:** 2026-02-26
**Python:** >=3.13

---

## 1. Complete Test File Listing

| # | Test File | Module Under Test |
|---|-----------|-------------------|
| 1 | `tests/test_integration/test_full_agent.py` | Full agent loop (kernel + tools + client) |
| 2 | `tests/test_public_api.py` | Package `__init__.py` exports |
| 3 | `tests/test_kernel/test_basic.py` | `structured_agents.kernel.AgentKernel` |
| 4 | `tests/test_types.py` | `structured_agents.types` |
| 5 | `tests/test_tools/test_grail_tool.py` | `structured_agents.tools.grail.GrailTool` |
| 6 | `tests/test_models/test_adapter.py` | `structured_agents.models.adapter.ModelAdapter` |
| 7 | `tests/test_agent/test_bundle.py` | `structured_agents.agent.Agent.from_bundle` |
| 8 | `tests/test_client/test_factory.py` | `structured_agents.client.factory.build_client` |
| 9 | `tests/test_client/test_openai.py` | `structured_agents.client.openai.OpenAICompatibleClient` |
| 10 | `tests/test_grammar/test_pipeline.py` | `structured_agents.grammar.pipeline.ConstraintPipeline` + `DecodingConstraint` |
| 11 | `tests/test_events/test_observer.py` | `structured_agents.events.observer.NullObserver` + Observer pattern |
| 12 | `tests/__init__.py` | Empty init (package marker only) |

**Total test files:** 11 (excluding `__init__.py`)
**Total test functions:** 16

---

## 2. Per-File Detailed Analysis

### 2.1 `tests/test_integration/test_full_agent.py`

- **Tests:** 1 (`test_full_agent_loop`)
- **Type:** Async integration test
- **What it tests:** Full agent loop — model makes a tool call on turn 1, returns text on turn 2. Verifies `RunResult.turn_count`, `termination_reason`, and that the tool was called exactly once.
- **Fixtures/Mocks:**
  - `AsyncMock` for LLM client with stateful `call_count` to vary responses per turn
  - `MagicMock(spec=Tool)` for tool with hardcoded `ToolSchema` and `ToolResult`
  - Real `ModelAdapter` with `QwenResponseParser`
  - No pytest fixtures used — all setup inline
- **Notable:** Uses `CompletionResponse` dataclass directly, manually constructs `MagicMock` for `usage` field

### 2.2 `tests/test_public_api.py`

- **Tests:** 3 (`test_all_exports_importable`, `test_version_exists`, `test_core_classes_importable`)
- **Type:** Synchronous smoke tests
- **What it tests:** All `__all__` exports are importable, `__version__` exists, and 14 specific core classes/functions are importable by name
- **Fixtures/Mocks:** None
- **Notable:** Good API contract test; guards against accidental export removal

### 2.3 `tests/test_kernel/test_basic.py`

- **Tests:** 1 (`test_kernel_step_basic`)
- **Type:** Async unit test
- **What it tests:** `AgentKernel.step()` with a mock client that returns a simple text response (no tool calls). Asserts `response_message.content == "Hello"`.
- **Fixtures/Mocks:**
  - `AsyncMock` for client with canned `CompletionResponse`
  - `MagicMock(spec=Tool)` with `ToolSchema` and `ToolResult`
  - Real `ModelAdapter` with `QwenResponseParser`
- **Notable:** Only tests the "no tool calls" path through `step()`. Does NOT test tool execution within `step()`, concurrency, or unknown-tool error handling.

### 2.4 `tests/test_types.py`

- **Tests:** 4 (`test_message_creation`, `test_message_to_openai_format`, `test_tool_call_create`, `test_tool_result_error_property`)
- **Type:** Synchronous unit tests
- **What it tests:** Basic construction and properties of `Message`, `ToolCall`, `ToolResult`
- **Fixtures/Mocks:** None
- **Notable:** Does NOT test `TokenUsage`, `ToolSchema`, `StepResult`, `RunResult`, `KernelConfig`, or `Message.to_message()` / `ToolResult.to_message()`. Minimal property-level checks only.

### 2.5 `tests/test_tools/test_grail_tool.py`

- **Tests:** 1 (`test_grail_tool_execute`)
- **Type:** Async unit test
- **What it tests:** `GrailTool.execute()` success path — mock script returns `{"result": 42}`, verifies `is_error == False` and output contains "42".
- **Fixtures/Mocks:**
  - `MagicMock` for grail script object with `name` and `run` attributes
  - Inline `MockContext` class with `call_id`
- **Notable:** Does NOT test the error path (exception handling in `execute`), `discover_tools()`, or schema generation from real `.pym` files.

### 2.6 `tests/test_models/test_adapter.py`

- **Tests:** 2 (`test_model_adapter_creation`, `test_model_adapter_format_messages_default`)
- **Type:** Synchronous unit tests
- **What it tests:** `ModelAdapter` construction and default `format_messages` behavior
- **Fixtures/Mocks:**
  - Inline `MockParser` dataclass (does NOT implement `ResponseParser` protocol properly — uses a dataclass instead of a Protocol-conforming class)
- **Notable:** Does NOT test `format_tools`, `grammar_builder` invocation, or `response_parser` integration. `MockParser` is a `@dataclass` which is unusual for a protocol mock.

### 2.7 `tests/test_agent/test_bundle.py`

- **Tests:** 1 (`test_agent_from_bundle_minimal`)
- **Type:** Async unit test
- **What it tests:** `Agent.from_bundle()` with fully mocked dependencies — patches `load_manifest`, `discover_tools`, and `build_client`
- **Fixtures/Mocks:**
  - `patch("structured_agents.agent.load_manifest")` — returns `MagicMock` manifest
  - `patch("structured_agents.agent.discover_tools")` — returns `[]`
  - `patch("structured_agents.agent.build_client")` — returns `AsyncMock`
- **Notable:** Only checks `agent is not None`. Does NOT test `Agent.run()`, `Agent.close()`, `load_manifest()` with real YAML (the `sample_bundle` fixture is not used), or any error paths.

### 2.8 `tests/test_client/test_factory.py`

- **Tests:** 1 (`test_build_client_returns_openai_client`)
- **Type:** Synchronous unit test
- **What it tests:** `build_client()` returns an `OpenAICompatibleClient` instance
- **Fixtures/Mocks:** None
- **Notable:** Does NOT test default values, config key handling, or edge cases. There are TWO `build_client` functions: one in `client/factory.py` and one in `client/openai.py` — this test imports from `structured_agents.client` which re-exports from `factory.py`.

### 2.9 `tests/test_client/test_openai.py`

- **Tests:** 1 (`test_openai_client_chat_completion`)
- **Type:** Async unit test
- **What it tests:** `OpenAICompatibleClient.chat_completion()` with a mocked internal `_client` — verifies content extraction from the response.
- **Fixtures/Mocks:**
  - `patch.object(client, "_client")` to mock the `AsyncOpenAI` instance
  - Nested `MagicMock` objects for OpenAI response structure
- **Notable:** Does NOT test tool call parsing, usage extraction, `close()`, error handling, or `extra_body` passthrough. The `respx` dev dependency is declared but never used — httpx mocking could be done at a higher level.

### 2.10 `tests/test_grammar/test_pipeline.py`

- **Tests:** 2 (`test_decoding_constraint_defaults`, `test_constraint_pipeline_returns_none_when_no_tools`)
- **Type:** Synchronous unit tests
- **What it tests:** `DecodingConstraint` default values and `ConstraintPipeline.constrain()` with empty tool list
- **Fixtures/Mocks:**
  - Lambda mock builder
- **Notable:** Does NOT test `GrammarConfig`, `ConstraintPipeline` with actual tools, or any real grammar generation.

### 2.11 `tests/test_events/test_observer.py`

- **Tests:** 2 (`test_null_observer_emit`, `test_observer_pattern_matching`)
- **Type:** Async unit tests
- **What it tests:** `NullObserver.emit()` doesn't raise; custom observer collects events
- **Fixtures/Mocks:**
  - Inline `TestObserver` class
- **Notable:** Tests 2 of 7 event types (`KernelStartEvent`, `ToolCallEvent`). Does NOT test `KernelEndEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `ToolResultEvent`, or `TurnCompleteEvent`.

---

## 3. Test Coverage Gap Analysis

### 3.1 Completely Untested Source Modules

| Source Module | File | Lines | Notes |
|---|---|---|---|
| `exceptions.py` | `src/structured_agents/exceptions.py` | 47 | 5 exception classes, none tested |
| `grammar/__init__.py` | `src/structured_agents/grammar/__init__.py` | — | Package init |
| `grammar/config.GrammarConfig` | `src/structured_agents/grammar/config.py:16-33` | 18 | `GrammarConfig` dataclass not tested (only `DecodingConstraint` is) |

### 3.2 Partially Tested Modules — Missing Coverage

| Module | What IS Tested | What is NOT Tested |
|---|---|---|
| **kernel.py** | `step()` happy path (no tools), `run()` with tool loop | `step()` with tool execution, `step()` with unknown tool, concurrent tool execution (`max_concurrency > 1`), `run()` hitting `max_turns`, `_tool_map()` edge cases, observer event emission during `run()` |
| **types.py** | `Message`, `ToolCall.create()`, `ToolResult.is_error` | `TokenUsage`, `ToolSchema` validation, `StepResult`, `RunResult`, `KernelConfig`, `ToolResult.to_message()`, `Message` with `tool_calls` |
| **agent.py** | `Agent.from_bundle()` (mocked) | `Agent.run()`, `Agent.close()`, `load_manifest()` with real YAML, `AgentManifest` defaults |
| **tools/grail.py** | `GrailTool.execute()` success | `GrailTool.execute()` error path, `discover_tools()` (stub — returns `[]`) |
| **models/parsers.py** | Indirectly via `QwenResponseParser` in integration | `QwenResponseParser.parse()` with API tool calls, `_parse_xml_tool_calls()`, `FunctionGemmaResponseParser`, XML edge cases, malformed JSON |
| **client/openai.py** | `chat_completion()` basic content | Tool call extraction, `TokenUsage` construction, `close()`, error handling, `extra_body` |
| **grammar/pipeline.py** | `constrain()` with no tools | `constrain()` with tools present |
| **grammar/config.py** | `DecodingConstraint` defaults | `GrammarConfig` entirely |
| **events/types.py** | `KernelStartEvent`, `ToolCallEvent` | `KernelEndEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `ToolResultEvent`, `TurnCompleteEvent` |
| **events/observer.py** | `NullObserver.emit()` | No concrete `Observer` implementation tested |

### 3.3 Critical Missing Tests

1. **Response parser logic** — `QwenResponseParser._parse_xml_tool_calls()` is untested. This is the grammar-constrained decoding output parsing, a core feature.
2. **Error paths** — No test covers any exception from `exceptions.py`. No test triggers `ToolExecutionError`, `KernelError`, `BundleError`, etc.
3. **Kernel tool execution** — `AgentKernel.step()` tool dispatch path is only tested via integration test; no unit test isolates tool execution, unknown-tool handling, or concurrent execution.
4. **`discover_tools()`** — The tool discovery function is a stub returning `[]`. No test validates future implementation.
5. **`load_manifest()` with real YAML** — The `sample_bundle` fixture exists but is never loaded in any test.
6. **`FunctionGemmaResponseParser`** — Entirely untested second parser implementation.

---

## 4. pyproject.toml Dependency Analysis

### 4.1 Runtime Dependencies

| Dependency | Version | Actually Used In Source? | Notes |
|---|---|---|---|
| `pydantic>=2.0` | >=2.0 | **Not directly observed** | Not imported in any `src/` file examined. May be used transitively by `fsdantic` or `grail`. Potential dead dependency. |
| `httpx>=0.25` | >=0.25 | **No** | Not imported anywhere. `openai` SDK uses it internally. Could be removed as a direct dependency. |
| `openai>=1.0` | >=1.0 | **Yes** | Used in `client/openai.py` via `AsyncOpenAI` |
| `pyyaml>=6.0` | >=6.0 | **Yes** | Used in `agent.py` via `yaml.safe_load()` |
| `jinja2>=3.0` | >=3.0 | **Not observed** | Not imported in any source file examined. Listed in `bundle.yaml` user_template suggests intended usage. Currently dead. |
| `grail` | git source | **Yes** | Used in fixture `.pym` files (`from grail import Input`). Referenced in `tools/grail.py` via `discover_tools()` stub. |
| `fsdantic` | git source | **Not observed** | Not imported in any examined source file. Potential dead dependency or future-use. |
| `xgrammar==0.1.29` | pinned | **Not observed** | Not imported in any source file. Expected for grammar-constrained decoding but integration not yet implemented. |
| `vllm>=0.15.1` | >=0.15.1 | **Not observed** | Not imported in any source file. Expected as the inference backend but no direct integration code found. |

### 4.2 Dev Dependencies

| Dependency | Version | Used? | Notes |
|---|---|---|---|
| `pytest>=8.0` | >=8.0 | **Yes** | Test runner |
| `pytest-asyncio>=0.23` | >=0.23 | **Yes** | Used via `asyncio_mode = "auto"` in config and `@pytest.mark.asyncio` decorators |
| `respx>=0.21` | >=0.21 | **No** | HTTP mocking library, never imported in any test file. Dead dev dependency. |

### 4.3 Dependency Concerns

1. **`pydantic`** — Listed but not visibly imported. If only used by `fsdantic`/`grail`, it should be a transitive dependency, not direct.
2. **`httpx`** — Only needed transitively by `openai`. Should not be a direct dependency.
3. **`jinja2`** — Listed but not imported. The `bundle.yaml` has `user_template: "Handle: {{ input }}"` suggesting Jinja rendering was planned but not implemented.
4. **`fsdantic`** — Git dependency with no visible usage.
5. **`xgrammar==0.1.29`** — Pinned exactly but not imported. The `.context/xgrammar/` vendored docs exist, but no integration code has been written yet.
6. **`vllm>=0.15.1`** — Listed but not imported. Same as xgrammar — planned but not integrated.
7. **`respx`** — Dev dependency never used. Tests mock `openai` objects directly instead.

### 4.4 Build System

- **Build backend:** `hatchling`
- **Wheel packages:** `src/structured_agents` (single package)
- **Pytest config:** `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- No coverage configuration (`pytest-cov` not present)
- No mypy configuration in `pyproject.toml`
- No linting/formatting tool configuration

---

## 5. Fixture Files Analysis

### 5.1 `tests/fixtures/grail_tools/add_numbers.pym`

- **Type:** Grail script (Monty Python-style)
- **Purpose:** Adds two integers `x` and `y`, returns `{"sum": x + y}`
- **Used by:** No test directly loads this file. Tests in `test_grail_tool.py` mock the script object instead.
- **Status:** **UNUSED in tests**

### 5.2 `tests/fixtures/grail_tools/add_numbers/` (compiled artifacts)

| File | Purpose | Used? |
|---|---|---|
| `monty_code.py` | Auto-generated executed code | No |
| `inputs.json` | Input schema (x: int, y: int) | No |
| `externals.json` | External dependencies list (empty) | No |
| `check.json` | Grail validation results | No |
| `stubs.pyi` | Type stubs | No |
| `run.log` | Execution log showing `{'sum': 8}` | No |

**Status:** All **UNUSED**. These appear to be pre-compiled grail artifacts checked in for reference but never loaded by any test.

### 5.3 `tests/fixtures/grail_tools/context_info.pym`

- **Type:** Grail script
- **Purpose:** Returns `{"context_name": context_name}` with a default input
- **Used by:** No test
- **Status:** **UNUSED**

### 5.4 `tests/fixtures/sample_bundle/`

| File | Purpose | Used? |
|---|---|---|
| `bundle.yaml` | Agent bundle manifest (model: function_gemma, tools: echo + submit_result, max_turns: 3) | No |
| `tools/echo.pym` | Echo tool script | No |
| `tools/submit_result.pym` | Termination tool script | No |

**Status:** All **UNUSED**. `test_agent/test_bundle.py` patches `load_manifest()` instead of loading this real fixture.

### 5.5 Fixture Usage Summary

**0 out of 11 fixture files are used by any test.** All tests use inline mocks/MagicMocks instead of the carefully prepared fixture data. This represents significant wasted setup and a missed opportunity for integration-level testing.

---

## 6. Structural Issues

### 6.1 No conftest.py Files

There are no `conftest.py` files in the `tests/` directory or any subdirectory. This means:
- No shared fixtures across test modules
- No session-scoped setup/teardown
- Each test file re-creates its own mocks (significant duplication)
- Common patterns (mock client, mock tool, mock adapter) are repeated verbatim across 4+ files

**Recommendation:** Create `tests/conftest.py` with shared fixtures for `mock_client`, `mock_tool`, `mock_adapter`, and `sample_messages`.

### 6.2 Missing `__init__.py` Files in Test Subdirectories

The following test subdirectories lack `__init__.py`:
- `tests/test_integration/`
- `tests/test_kernel/`
- `tests/test_tools/`
- `tests/test_models/`
- `tests/test_agent/`
- `tests/test_client/`
- `tests/test_grammar/`
- `tests/test_events/`

This works with pytest's default discovery but can cause import issues with some configurations.

### 6.3 Duplicate `build_client` Functions

Two implementations exist:
1. `src/structured_agents/client/factory.py:10` — canonical factory
2. `src/structured_agents/client/openai.py:89` — duplicate in the OpenAI module

Both have identical logic. The `client/__init__.py` re-exports from `factory.py`. The duplicate in `openai.py` is dead code.

### 6.4 Test Depth is Shallow

Most test files contain only 1-2 tests covering the absolute minimum happy path. The average test count per file is **1.45 tests**. No test explores:
- Error handling / exception paths
- Edge cases (empty inputs, None values, malformed data)
- Boundary conditions (max_turns reached, concurrent tool execution)
- State management across turns

### 6.5 No Test for `discover_tools()`

`discover_tools()` in `tools/grail.py` is a stub that returns `[]` with a TODO comment. This is the primary tool loading mechanism and has no test to validate it once implemented.

### 6.6 Observer Integration Not Tested

`AgentKernel` accepts an `Observer` and emits events during `run()`, but no test verifies that events are actually emitted during kernel execution. The observer tests only test event objects in isolation.

### 6.7 No Coverage Tooling

No `pytest-cov` in dependencies, no coverage configuration. There's no way to measure actual line/branch coverage.

---

## 7. Summary Statistics

| Metric | Value |
|---|---|
| Total test files | 11 |
| Total test functions | 16 |
| Async tests | 7 |
| Sync tests | 9 |
| Source modules | 15 (excluding `__init__.py` files) |
| Modules with 0 tests | 3 (`exceptions.py`, `grammar/__init__.py`, `GrammarConfig`) |
| Modules with partial tests | 9 |
| Fixture files | 11 |
| Fixture files actually used | 0 |
| Shared conftest fixtures | 0 |
| Dead runtime dependencies | 4-5 (`pydantic`, `httpx`, `jinja2`, `fsdantic`, possibly `xgrammar`/`vllm`) |
| Dead dev dependencies | 1 (`respx`) |
| Duplicate code | 1 (`build_client` in two locations) |
