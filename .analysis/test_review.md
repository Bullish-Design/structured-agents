# Test Suite Review - structured-agents v0.3.0

**Reviewer:** Code Review Agent
**Date:** 2026-02-26
**Scope:** All 12 test files + fixtures in `tests/`

---

## Executive Summary

The test suite is dangerously thin for a v0.3.0 refactor. Across 12 test files and ~350 lines of test code, most tests verify only the happy path with trivial assertions. Critical modules (`exceptions.py`, `agent.py`, `kernel.py` run loop, response parsers) have zero or near-zero meaningful coverage. The "integration" test is fully mocked, meaning no actual integration is tested. Several tests assert correct behavior but would also pass on broken implementations, providing false confidence.

---

## 1. Per-File Analysis

### 1.1 `tests/test_types.py` (33 lines, 4 tests)

**What's tested:**
- `Message` creation and `to_openai_format()` (simple case)
- `ToolCall.create()` factory method
- `ToolResult.is_error` property

**Critical gaps:**
- **`Message.to_openai_format()` with tool_calls**: The method has branches for `tool_calls`, `tool_call_id`, and `name` fields (`src/structured_agents/types.py:43-61`). None of these branches are tested. The only test uses a bare `role + content` message.
- **`ToolResult.to_message()`**: Never tested (`src/structured_agents/types.py:109-116`). This is used in the kernel's run loop to convert tool results to messages.
- **`ToolSchema.to_openai_format()`**: Never tested (`src/structured_agents/types.py:135-144`).
- **`ToolCall.arguments_json`**: Never tested (`src/structured_agents/types.py:78-83`). This property does `json.dumps()` and is used in `to_openai_format()`.
- **`StepResult` and `RunResult`**: No construction/validation tests.
- **`KernelConfig`**: Not tested at all (class at `src/structured_agents/types.py:14-18`).
- **Frozen dataclass enforcement**: No test verifies that `Message`, `ToolCall`, etc. are actually immutable (they use `frozen=True`).
- **Edge cases**: Empty content, `None` content, messages with both content and tool_calls simultaneously.

### 1.2 `tests/test_tools/test_grail_tool.py` (24 lines, 1 test)

**What's tested:**
- Happy-path execution with a mock script returning a dict.

**Critical gaps:**
- **Error handling path**: `GrailTool.execute()` has a `try/except` block (`src/structured_agents/tools/grail.py:35-41`) that catches exceptions and returns `ToolResult(is_error=True)`. This is never tested.
- **`context=None` path**: When `context` is None, `call_id` becomes `"unknown"` (`src/structured_agents/tools/grail.py:30`). Not tested.
- **String result handling**: The execute method has `if not isinstance(result, str)` logic (`src/structured_agents/tools/grail.py:28`). Only dict results are tested; string results are not.
- **`discover_tools()`**: Never tested (`src/structured_agents/tools/grail.py:44-47`). Currently a stub returning `[]`, but test fixtures exist in `tests/fixtures/grail_tools/` that are never used.
- **Mock quality issue**: `MockContext` is an ad-hoc class that only has `call_id`. If `Tool.execute` ever needs more from context, this won't catch it. The `context` parameter in `GrailTool.execute` accepts `Any`, hiding type issues.
- **Schema generation**: The test checks `tool.schema.name` but doesn't verify `description` or `parameters` are generated correctly from the script. The current implementation hardcodes `description=f"Tool: {script.name}"` and empty parameters (`src/structured_agents/tools/grail.py:17`), which means schema introspection from `.pym` scripts is untested.

### 1.3 `tests/test_grammar/test_pipeline.py` (22 lines, 2 tests)

**What's tested:**
- `DecodingConstraint` default values.
- `ConstraintPipeline.constrain()` returns `None` for empty tools list.

**Critical gaps:**
- **`ConstraintPipeline.constrain()` with actual tools**: The non-empty tools path (`src/structured_agents/grammar/pipeline.py:29` - `return self._builder(tools, self._config)`) is never tested.
- **`GrammarConfig`**: The second config dataclass at `src/structured_agents/grammar/config.py:16-33` is never tested. It has different defaults from `DecodingConstraint` (e.g., `allow_parallel_calls=True` vs `False`, `send_tools_to_api=True` vs `False`). It's unclear which config class is canonical.
- **Non-default `DecodingConstraint` values**: No test constructs a constraint with `strategy="json_schema"` or `allow_parallel_calls=True`.
- **Builder error propagation**: What happens if the builder raises? Not tested.
- **No xgrammar/vLLM grammar integration**: The fixtures directory has grail tools, but no tests exercise actual EBNF or JSON schema grammar generation. This is the core differentiator of the library.

### 1.4 `tests/test_models/test_adapter.py` (37 lines, 2 tests)

**What's tested:**
- `ModelAdapter` creation with basic fields.
- `format_messages` default behavior (simple message).

**Critical gaps:**
- **`_default_format_tools()`**: Never tested (`src/structured_agents/models/adapter.py:40-42`).
- **`_default_format_messages()` with tools argument**: The method appends a system message with tool info when `tools` is non-empty (`src/structured_agents/models/adapter.py:34-37`). This branch is never tested (the test passes `[]` for tools).
- **Custom `format_messages` / `format_tools` callables**: The adapter accepts custom formatters. None are tested.
- **`__post_init__` default-setting logic**: Uses `object.__setattr__` on a frozen dataclass (`src/structured_agents/models/adapter.py:21-24`). This is fragile and not tested for correctness.
- **`response_parser` is typed `Any`**: No test verifies the parser protocol is enforced.
- **`MockParser`**: The mock's `parse` method signature matches `ResponseParser.parse` but returns `(content, [])` always. Tests don't verify that the adapter actually uses the parser correctly.

### 1.5 `tests/test_events/test_observer.py` (39 lines, 2 tests)

**What's tested:**
- `NullObserver.emit()` doesn't raise.
- Ad-hoc `TestObserver` collects events.

**Critical gaps:**
- **`Observer` protocol compliance**: `TestObserver` in the test is not actually checked against the `Observer` protocol. It just has an `emit` method. No `isinstance` check or `runtime_checkable` verification.
- **All 7 event types**: Only `KernelStartEvent` and `ToolCallEvent` are instantiated. The other 5 event types (`KernelEndEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `ToolResultEvent`, `TurnCompleteEvent`) are imported but never tested.
- **Event immutability**: Events use `frozen=True` but no test verifies immutability.
- **Event data integrity**: No test verifies event field values after construction.
- **Observer integration with kernel**: The kernel emits events (`src/structured_agents/kernel.py:149-155`), but only `KernelStartEvent` is emitted in the current code. No test verifies the kernel-observer wiring works end-to-end.

### 1.6 `tests/test_kernel/test_basic.py` (52 lines, 1 test)

**What's tested:**
- Single `kernel.step()` call with mocked client returning a simple text response (no tool calls).

**Critical gaps:**
- **`kernel.run()` loop**: Not tested here at all. The run loop logic (`src/structured_agents/kernel.py:138-201`) with turn counting, termination conditions, message accumulation is only tested in the integration test.
- **Tool execution during step**: The step test uses a mock tool but the mock response has `tool_calls=None`, so tool execution never actually happens. The tool execution logic in `step()` (`src/structured_agents/kernel.py:108-129`) is untested.
- **Unknown tool handling**: `execute_one` returns an error `ToolResult` for unknown tools (`src/structured_agents/kernel.py:110-116`). Not tested.
- **Concurrent tool execution**: The `max_concurrency > 1` branch (`src/structured_agents/kernel.py:122-129`) using `asyncio.Semaphore` is never tested.
- **Tool name resolution by string**: The `isinstance(t, str)` branch in step (`src/structured_agents/kernel.py:62-65`) is never tested.
- **Grammar constraint building**: The `grammar_builder` is set to `lambda t, c: None`, so grammar constraint logic is never exercised.
- **`max_history_messages`**: Field exists on `AgentKernel` but is never used in the code and never tested.
- **Observer event emission**: The kernel emits `KernelStartEvent` in `run()` but no other events. This is likely incomplete implementation, and no test catches this.
- **Edge case - empty messages list**: Not tested.
- **Edge case - `max_turns=0`**: Not tested.

### 1.7 `tests/test_agent/test_bundle.py` (28 lines, 1 test)

**What's tested:**
- `Agent.from_bundle()` with fully mocked dependencies returns a non-None agent.

**Critical gaps:**
- **`assert agent is not None`**: This is the only assertion. It doesn't verify the agent is correctly configured - kernel, manifest, tools, adapter, etc. are all unchecked.
- **`Agent.run()`**: Never tested (`src/structured_agents/agent.py:95-108`).
- **`Agent.close()`**: Never tested.
- **`load_manifest()`**: Never tested directly (`src/structured_agents/agent.py:33-50`). The mock patches it entirely. There are actual fixtures in `tests/fixtures/sample_bundle/bundle.yaml` that could be used.
- **`AgentManifest`**: Never tested for correct field parsing from YAML.
- **Bundle YAML parsing**: `load_manifest` handles directory paths vs file paths (`src/structured_agents/agent.py:36-37`). Neither branch is tested with real files.
- **Mock quality**: Three nested `with patch` blocks completely bypass all real logic. The test proves only that `Agent.from_bundle` calls those three functions - not that it does anything useful with their results.
- **Overrides parameter**: `from_bundle` accepts `**overrides` (`src/structured_agents/agent.py:67`) but never uses them. Not tested.
- **System prompt from manifest**: `Agent.run()` injects the system prompt from `manifest.system_prompt` (`src/structured_agents/agent.py:98`). Not tested.

### 1.8 `tests/test_client/test_openai.py` (37 lines, 1 test)

**What's tested:**
- `OpenAICompatibleClient.chat_completion()` happy path with mocked internal `_client`.

**Critical gaps:**
- **Response with tool_calls**: The mock returns `tool_calls=None`. The tool_calls parsing branch (`src/structured_agents/client/openai.py:56-67`) is never tested.
- **Usage extraction**: The test mock has usage but the test never asserts `result.usage` values.
- **Error handling**: No test for API errors, timeouts, malformed responses, empty choices list.
- **`close()` method**: Not tested.
- **`extra_body` parameter**: Grammar constraints are passed via `extra_body`. Not tested that it's forwarded correctly.
- **Mock quality issue**: `patch.object(client, "_client")` replaces the entire `AsyncOpenAI` instance, meaning the test doesn't verify that `OpenAICompatibleClient.__init__` correctly initializes the underlying client.
- **`to_dict()` on response**: The mock has `mock_response.to_dict.return_value = {}`. If the real OpenAI response doesn't have `to_dict()` (it uses `model_dump()` in newer versions), this would hide a production bug.

### 1.9 `tests/test_client/test_factory.py` (10 lines, 1 test)

**What's tested:**
- `build_client()` returns an `OpenAICompatibleClient` instance.

**Critical gaps:**
- **Config field mapping**: No assertion that `base_url`, `model`, `api_key`, `timeout` are correctly passed through. The test only checks `isinstance`.
- **Default values**: No test for missing config keys and their defaults.
- **Duplicate implementation**: There are TWO `build_client` functions - one in `src/structured_agents/client/openai.py:89-96` and one in `src/structured_agents/client/factory.py:10-17`. The factory module imports from `openai.py`. The test imports from `structured_agents.client` which re-exports from `openai.py`. The `client/factory.py` version may be dead code. No test catches this.

### 1.10 `tests/test_integration/test_full_agent.py` (92 lines, 1 test)

**What's tested:**
- Two-turn agent loop: first turn returns a tool call, second turn returns text. Verifies `turn_count=2`, `termination_reason="no_tool_calls"`, and tool was called once.

**Critical issues:**

1. **This is NOT an integration test.** Everything is mocked: the client, the tool, the adapter's grammar builder. A true integration test would use real components wired together with at most the LLM client mocked.

2. **Response parser inconsistency**: The test uses `QwenResponseParser` with tool_calls in OpenAI dict format (with `"function"` key). The parser's `parse()` method at `src/structured_agents/models/parsers.py:24-31` processes these. However, the XML parsing path (`_parse_xml_tool_calls`) is never exercised. Since the library's differentiator is grammar-constrained output, the XML/structural tag parsing path is arguably more important.

3. **Tool execution call_id mismatch**: The mock tool's `execute` returns `ToolResult(call_id="call_123", ...)` hardcoded, but the kernel calls `tool.execute(tc.arguments, None)` at `src/structured_agents/kernel.py:117`. The `None` context means `GrailTool` would set `call_id="unknown"`. The mock hides this because it returns a pre-built result. In production, the `call_id` would not match the tool call's ID.

4. **`max_turns` boundary**: Test uses `max_turns=2` and the loop happens to exit at turn 2 with `"no_tool_calls"`. There's no test for actually hitting the `max_turns` limit (where `termination_reason` would remain `"max_turns"`).

5. **Missing event emission verification**: The kernel emits `KernelStartEvent` but the test doesn't verify this. No observer is attached.

6. **Tool result message format**: After tool execution, the kernel calls `result.to_message()` to append tool results to history. The test doesn't verify the message format or history contents.

### 1.11 `tests/test_public_api.py` (52 lines, 3 tests)

**What's tested:**
- All `__all__` exports are non-None.
- `__version__` exists and is a string.
- Core classes are importable and have correct `__name__`.

**Assessment:** These are reasonable smoke tests. However:
- **Missing exports**: `FunctionGemmaResponseParser` is in `models/__init__.py` `__all__` but not in the top-level `__all__`. No test catches this discrepancy.
- **`GrammarConfig`** is exported from `grammar/config.py` but not from any `__init__.py`. Not tested.
- **`CompletionResponse`** is in `client/__init__.py` `__all__` but not top-level `__all__`. Not tested.
- **`discover_tools`** is in `tools/__init__.py` `__all__` but not top-level. Not tested.
- **`exceptions` module**: All 5 exception classes are never exported at the top level and never tested.

### 1.12 `tests/__init__.py` (1 line, empty)

Standard empty init file. No issues.

---

## 2. Module-Level Coverage Gaps

### 2.1 `exceptions.py` - ZERO test coverage

Five exception classes defined (`src/structured_agents/exceptions.py:1-47`):
- `StructuredAgentsError`
- `KernelError` (with `turn` and `phase` fields)
- `ToolExecutionError` (with `tool_name`, `call_id`, `code` fields)
- `PluginError`
- `BundleError`
- `BackendError`

None are tested. None are imported in any test. None are even raised anywhere in the current source code. This suggests either:
1. Exception handling hasn't been implemented yet (likely given it's a refactor), or
2. The exceptions are dead code.

Either way, there should be tests verifying construction and that the kernel/tools actually raise them in error conditions.

### 2.2 Response Parsers - Near-zero coverage

`src/structured_agents/models/parsers.py` contains:
- `QwenResponseParser` - Only tested indirectly through integration test (OpenAI-format tool_calls only)
- `FunctionGemmaResponseParser` - Never tested. Its `parse()` method delegates to `QwenResponseParser().parse()` (line 70), which is a code smell (creates a new instance each call).
- XML tool call parsing (`_parse_xml_tool_calls`) - Never tested despite being a key differentiator.

**Missing parser tests:**
- Malformed JSON in tool call arguments
- Multiple tool calls in one response
- Mixed content + tool calls
- XML `<tool_call>` with invalid JSON inside
- Nested/escaped JSON in arguments
- Empty `<tool_call></tool_call>` tags
- Tool call with missing `name` field

### 2.3 `load_manifest()` - Zero direct coverage

The function at `src/structured_agents/agent.py:33-50` parses YAML and constructs `AgentManifest`. It handles:
- Directory path vs file path (`src/structured_agents/agent.py:36-37`)
- Default values for missing fields
- `system_prompt` extraction (but note: the actual fixture `bundle.yaml` doesn't have a `system_prompt` field - it has `initial_context.system_prompt`)

**Bug**: `load_manifest()` reads `data.get("system_prompt", "")` but the bundle YAML fixture uses `initial_context.system_prompt`. This means `load_manifest` would always return empty `system_prompt` for real bundles. No test catches this.

**Bug**: `agents_dir` is computed as `Path(bundle_path).parent / data.get("agents_dir", "agents")` but the fixture YAML has no `agents_dir` field. The path would be `<parent>/agents` by default, but the fixture tools are in `tools/`, not `agents/`.

---

## 3. Test Anti-Patterns

### 3.1 Weak Assertions

Multiple tests use assertions that would pass on broken implementations:

| Test | Assertion | Problem |
|------|-----------|---------|
| `test_agent_from_bundle_minimal` | `assert agent is not None` | Any non-None return passes. Doesn't verify agent state. |
| `test_model_adapter_creation` | `assert adapter.grammar_builder is not None` | Just checks the lambda was stored. |
| `test_grail_tool_execute` | `assert "42" in result.output` | Would pass if output was `"error: 42 not found"`. Should assert exact output. |
| `test_build_client_returns_openai_client` | `isinstance` check only | Doesn't verify config was applied. |

### 3.2 Over-Mocking

The test suite mocks so aggressively that it often tests mock wiring rather than actual behavior:

- `test_agent_from_bundle_minimal`: 3 nested patches mock away all real logic.
- `test_openai_client_chat_completion`: Patches `_client` attribute, bypassing initialization.
- `test_full_agent_loop`: Called an "integration" test but every external boundary is mocked.

### 3.3 No Shared Fixtures / conftest.py

There is no `conftest.py` anywhere in the test tree. Common objects (mock clients, adapters, tools) are duplicated across files. This leads to:
- Inconsistent mock setup between `test_kernel/test_basic.py` and `test_integration/test_full_agent.py`
- No shared fixture for `ModelAdapter` with real parser
- No fixture using the actual grail tools in `tests/fixtures/`

### 3.4 No Negative Tests

The entire suite contains zero negative/failure-path tests:
- No test for invalid tool arguments
- No test for tool execution failure
- No test for malformed API responses
- No test for exceeding `max_turns`
- No test for empty tool list behavior
- No test for duplicate tool names
- No test for missing required fields on dataclasses

### 3.5 No Parametrized Tests

Despite several places where parametrization would be natural (different message roles, different parser inputs, different event types, different DecodingConstraint strategies), no tests use `@pytest.mark.parametrize`.

---

## 4. Fixture Analysis

### 4.1 `tests/fixtures/grail_tools/`

Contains two `.pym` scripts (`add_numbers.pym`, `context_info.pym`) with full grail compilation artifacts (monty_code, inputs.json, check.json, etc.). These are NEVER used in any test. They could be used to test:
- `discover_tools()` (currently a stub)
- Real `GrailTool` construction from `.pym` files
- Tool schema generation from grail inputs

### 4.2 `tests/fixtures/sample_bundle/`

Contains a complete bundle with `bundle.yaml` and two `.pym` tools. NEVER used in any test. Could test:
- `load_manifest()` with real YAML
- `Agent.from_bundle()` with real bundle structure
- Would expose the `system_prompt` parsing bug noted in 2.3

---

## 5. Structural Issues

### 5.1 Duplicate `build_client` Function

Two identical implementations exist:
- `src/structured_agents/client/factory.py:10-17`
- `src/structured_agents/client/openai.py:89-96`

The `client/__init__.py` imports from `openai.py`. The `factory.py` is imported in `agent.py`. This is confusing and error-prone. Tests don't verify they behave identically.

### 5.2 Missing `conftest.py`

No pytest configuration beyond `pyproject.toml`. No shared fixtures, no common mocks, no test helpers.

### 5.3 `asyncio_mode = "auto"` but `@pytest.mark.asyncio` decorators

The `pyproject.toml` sets `asyncio_mode = "auto"` which should make `@pytest.mark.asyncio` unnecessary. Several tests still use the decorator. This is harmless but inconsistent.

### 5.4 No Test Markers

No custom markers for slow tests, integration tests, or tests requiring specific backends. As the suite grows, this will make selective test running difficult.

---

## 6. Critical Missing Test Scenarios

### Priority 1 (Blocks confidence in core loop)

1. **Kernel `run()` hitting `max_turns`**: Verify `termination_reason="max_turns"` when the model keeps making tool calls.
2. **Kernel `step()` with tool execution**: Test that when model returns tool_calls, the kernel actually calls the right tool with correct arguments and appends results.
3. **Unknown tool name handling in kernel**: Test the error result for non-existent tools.
4. **`QwenResponseParser._parse_xml_tool_calls()`**: This is the grammar-constrained output parser. Must be tested with realistic XML tool call content.
5. **`load_manifest()` with real bundle.yaml**: Would catch the system_prompt field mismatch bug.

### Priority 2 (Important for correctness)

6. **`Message.to_openai_format()` with tool_calls**: Test the full serialization path.
7. **`GrailTool.execute()` error path**: Test exception handling in tool execution.
8. **`ConstraintPipeline.constrain()` with tools**: Test the builder is called correctly.
9. **`OpenAICompatibleClient` with tool_calls response**: Test tool call extraction from API response.
10. **Concurrent tool execution (`max_concurrency > 1`)**: Test the semaphore-bounded parallel path.

### Priority 3 (Completeness)

11. **Exception class construction and attributes**.
12. **`FunctionGemmaResponseParser` distinct behavior** (currently a passthrough - is this intentional?).
13. **Event type construction for all 7 event types**.
14. **`ToolResult.to_message()` conversion**.
15. **`ToolSchema.to_openai_format()` output**.
16. **Agent lifecycle: `from_bundle()` -> `run()` -> `close()`**.

---

## 7. Tests That May Pass But Shouldn't

### 7.1 `test_full_agent_loop` termination_reason

The test asserts `result.termination_reason == "no_tool_calls"` at line 87. This is technically correct for the current implementation, but the kernel source has a 20-line TODO comment (`src/structured_agents/kernel.py:167-188`) acknowledging that `"no_tool_calls"` is ambiguous. The test enshrines this ambiguous behavior without documenting the ambiguity.

### 7.2 `test_constraint_pipeline_returns_none_when_no_tools`

Tests that `constrain([])` returns `None`. But the implementation short-circuits before calling the builder (`src/structured_agents/grammar/pipeline.py:27-28`). The mock_builder (`lambda tools, config: None`) would also return None for non-empty tools. The test proves the empty-check works but the mock would mask a builder bug.

### 7.3 `test_model_adapter_format_messages_default`

Asserts `result[0]["role"] == "user"` at line 36. This would pass even if `to_openai_format()` returned garbage in all other fields. It tests one field of potentially many.

---

## 8. Recommendations

1. **Add `conftest.py`** with shared fixtures for mock clients, adapters, tools, and a fixture that loads the sample bundle.
2. **Write parser unit tests** for `QwenResponseParser` and `FunctionGemmaResponseParser` with parametrized inputs covering XML tool calls, malformed JSON, multiple calls, etc.
3. **Write real integration tests** using the fixtures in `tests/fixtures/sample_bundle/` with only the LLM client mocked.
4. **Add negative tests** for all error paths: tool execution failure, unknown tools, max_turns exceeded, malformed responses.
5. **Fix the `load_manifest()` bug** where `system_prompt` is read from wrong YAML path, then add a test using the real fixture.
6. **Resolve the duplicate `build_client`** between `client/factory.py` and `client/openai.py`.
7. **Add exception handling tests** or remove unused exception classes.
8. **Use `@pytest.mark.parametrize`** for response parser tests, event type tests, and message format tests.
9. **Remove `@pytest.mark.asyncio`** decorators since `asyncio_mode = "auto"` is set.
10. **Add a `conftest.py` marker** for tests that require grail to be installed vs pure unit tests.

---

## 9. Quantitative Summary

| Metric | Value |
|--------|-------|
| Total test files | 12 |
| Total test functions | 16 |
| Total test lines (approx) | 350 |
| Source modules | 16 |
| Source modules with 0 test coverage | 3 (`exceptions.py`, `client/factory.py` direct, `grammar/config.py` `GrammarConfig`) |
| Source modules with trivial coverage | 8 |
| Negative/error-path tests | 0 |
| Parametrized tests | 0 |
| Tests using real fixtures | 0 |
| `conftest.py` files | 0 |
| True integration tests (non-mocked) | 0 |
