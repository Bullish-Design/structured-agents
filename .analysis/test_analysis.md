# Test Suite Analysis: structured-agents v0.3.0

**Date:** 2026-02-26  
**Scope:** Comprehensive analysis of tests/ directory coverage, quality, fixtures, and alignment with CODE_REVIEW.md concerns

---

## Executive Summary

The test suite consists of **12 test files** containing **16 test functions** with **zero negative tests**. While a `conftest.py` exists with shared fixtures, fixture utilization is poor (~33%). The test suite provides false confidence — it passes but fails to catch the 3 critical runtime bugs identified in CODE_REVIEW.md. Real fixtures in `tests/fixtures/` are completely unused. Most CODE_REVIEW.md concerns about test gaps remain unaddressed.

---

## 1. Test Coverage Overview

### Quantitative Metrics

| Metric | Value | Assessment |
|--------|-------|------------|
| Test files | 12 | Sparse distribution across modules |
| Test functions | 16 | ~1.3 tests per file average |
| Lines of test code | ~650 | Very low for a library of this complexity |
| Negative/error-path tests | 0 | **Critical gap** |
| Parametrized tests | 0 | No combinatorial coverage |
| Async tests | 7 (44%) | Appropriate for async library |
| Tests with mocks | 13 (81%) | Heavy mocking, limited real integration |

### Coverage by Module

| Module | Test File | Coverage | Notes |
|--------|-----------|----------|-------|
| `types.py` | `test_types.py` | 4 tests | Basic dataclass creation only |
| `agent.py` | `test_agent/test_bundle.py` | 1 test | Minimal smoke test, heavily mocked |
| `kernel.py` | `test_kernel/test_basic.py` | 1 test | Only happy path |
| `models/adapter.py` | `test_models/test_adapter.py` | 2 tests | Grammar builder not actually tested |
| `models/parsers.py` | `test_models/test_parsers_comprehensive.py` | 7 tests | **Best coverage**, but still missing XML edge cases |
| `tools/grail.py` | `test_tools/test_grail_tool.py` | 1 test | Mock-based, doesn't test real Grail integration |
| `client/factory.py` | `test_client/test_factory.py` | 1 test | Minimal smoke test |
| `client/openai.py` | `test_client/test_openai.py` | 1 test | Mocks SDK, doesn't catch BUG-1 |
| `events/` | `test_events/test_observer.py` | 2 tests | Only NullObserver tested |
| `__init__.py` (public API) | `test_public_api.py` | 3 tests | Import-only smoke tests |
| `grammar/` | — | **0 tests** | ConstraintPipeline, GrammarConfig untested |
| `tools/discover.py` | — | **0 tests** | `discover_tools()` is stubbed, no tests |
| `exceptions.py` | — | **0 tests** | 5 exception classes, never raised in tests |

### Critical Untested Code Paths

1. **`QwenResponseParser._parse_xml_tool_calls()`** — The regex-based XML parser has **zero test coverage** despite being the core grammar-constrained output parser
2. **Error handling in kernel** — `AgentKernel.step()` and `run()` have no error path tests
3. **Tool execution failure** — No tests for exceptions during tool execution
4. **Malformed API responses** — `json.loads` in parsers has no error handling tests
5. **Max turns exhaustion** — No tests for `max_turns` limit enforcement
6. **Grammar constraint pipeline** — `ConstraintPipeline` class is completely untested
7. **Real Grail integration** — `grail.load()` and `discover_tools()` never tested with real `.pym` files

---

## 2. Test Quality Analysis

### Assertion Strength

| Test | Weak Assertion | Risk |
|------|---------------|------|
| `test_agent_from_bundle_minimal` | `assert agent is not None` | Passes on broken agent with no tools |
| `test_grail_tool_execute` | `assert "42" in result.output` | Passes on error messages containing "42" |
| `test_model_adapter_creation` | `assert adapter.grammar_builder is not None` | Doesn't verify builder works |
| `test_build_client_returns_openai_client` | `assert isinstance(client, OpenAICompatibleClient)` | Doesn't verify client functions |
| `test_openai_client_chat_completion` | `assert result.content == "Hello"` | Doesn't catch BUG-1 (to_dict vs model_dump) |

### Missing Negative Tests

**Zero tests verify behavior on:**
- Tool execution raising exceptions
- Unknown tool names in responses
- `max_turns` exhaustion scenarios
- Malformed JSON in API tool_calls
- Invalid argument schemas
- Network failures in client
- Observer raising exceptions
- XML parsing failures
- Empty tool lists
- Concurrent tool execution with partial failures

### Edge Case Coverage

| Scenario | Tested? | Location |
|----------|---------|----------|
| Empty messages list | ❌ | — |
| Single tool vs multiple tools | ✅ | `test_parse_multiple_api_tool_calls` |
| Empty tool arguments | ✅ | `test_parse_empty_arguments` |
| Malformed JSON in arguments | ✅ | `test_parse_api_tool_calls_malformed_json` |
| XML with nested tags | ❌ | — |
| XML with special characters | ❌ | — |
| Very long content (>10k tokens) | ❌ | — |
| Unicode in content | ❌ | — |
| Null/None handling | ✅ | `test_parse_none_content_no_tools` |
| Concurrent tool execution | ❌ | — |

---

## 3. Fixtures Analysis

### conftest.py Contents

**Location:** `tests/conftest.py` (76 lines)

**Defined Fixtures (6 total):**

| Fixture | Type | Usage Count | Used In |
|---------|------|-------------|---------|
| `mock_client` | AsyncMock | 2 | `test_integration/test_full_agent.py`, `test_kernel/test_basic.py` |
| `adapter` | Real ModelAdapter | 0 | **Unused** |
| `sample_messages` | list[Message] | 0 | **Unused** |
| `sample_tool_schema` | ToolSchema | 0 | **Unused** |
| `sample_tool_call` | ToolCall | 0 | **Unused** |
| — | — | — | — |

**Fixture Utilization: 33% (2/6 used)**

### Fixture Quality Issues

1. **Unused fixtures waste maintenance** — 4 fixtures defined but never imported
2. **Inconsistent mock setup** — Each test file creates its own mocks instead of using shared fixtures
3. **No fixture for real Grail tools** — Despite fixtures existing in `tests/fixtures/grail_tools/`
4. **No fixture for sample bundle** — `tests/fixtures/sample_bundle/` exists but unused
5. **Missing fixtures:**
   - Real Grail script loader
   - Sample bundle manifest
   - Error-raising mock tools
   - Malformed response generators

### Real Fixtures Directory

**Location:** `tests/fixtures/`

**Contents:**
```
tests/fixtures/
├── grail_tools/
│   ├── add_numbers/
│   │   ├── monty_code.py
│   │   ├── inputs.json
│   │   ├── externals.json
│   │   ├── check.json
│   │   ├── stubs.pyi
│   │   └── run.log
│   └── context_info.pym
└── sample_bundle/
    ├── bundle.yaml
    └── tools/
        ├── echo.pym
        └── submit_result.pym
```

**Usage: 0%** — These real fixtures are never loaded or tested.

**bundle.yaml content:**
```yaml
name: test_agent
version: "1.0"
initial_context:
  system_prompt: "You are a helpful assistant."
model:
  name: "qwen"
  grammar_config: null
```

**Critical finding:** `load_manifest()` reads `data.get("system_prompt")` but the actual YAML nests it under `initial_context.system_prompt`. No test catches this because fixtures are never used.

---

## 4. Alignment with CODE_REVIEW.md Concerns

### CODE_REVIEW.md Section 6: Test Suite

| Concern | Status | Evidence |
|---------|--------|----------|
| **"Zero negative tests"** | ✅ **Still true** | No error path coverage in any test file |
| **"The 'integration' test is fully mocked"** | ✅ **Still true** | `test_full_agent_loop` mocks client, tools, grammar_builder |
| **"Real fixtures never used"** | ✅ **Still true** | `tests/fixtures/` completely ignored |
| **"QwenResponseParser._parse_xml_tool_calls() has zero coverage"** | ✅ **Still true** | Only `parse()` entry point tested, not internal `_parse_xml_tool_calls()` |
| **"load_manifest() has a latent bug"** | ✅ **Still true** | YAML structure mismatch undetected, no fixture tests |
| **"Weak assertions"** | ✅ **Still true** | Assertions like `assert agent is not None` remain |
| **"No shared fixtures"** | ⚠️ **Partially addressed** | `conftest.py` exists but underutilized |
| **"@pytest.mark.asyncio used with asyncio_mode = 'auto'"** | ✅ **Still true** | Redundant decorators in 7 tests |
| **"No conftest.py files"** | ❌ **Fixed** | `tests/conftest.py` now exists with 6 fixtures |

### Outstanding Critical Gaps

1. **BUG-1 not caught** — `test_openai_client_chat_completion` mocks `to_dict()` instead of testing real behavior
2. **BUG-2 not caught** — Parser tests added but don't cover the actual bug scenario with real API responses
3. **BUG-3 not caught** — No tests verify tool context/call_id propagation
4. **Grammar pipeline untested** — `ConstraintPipeline` class has zero coverage
5. **Event system 85% dead** — Only `KernelStartEvent` and basic observer tested, 5 other event types never emitted or tested
6. **Grail integration stubbed** — `discover_tools()` returns `[]`, no tests for real `.pym` loading

---

## 5. Recommendations

### P0 — Fix Before Release

1. **Add negative tests for the 3 runtime bugs** — Verify BUG-1, BUG-2, BUG-3 are caught
2. **Test `QwenResponseParser._parse_xml_tool_calls()` directly** — Cover regex edge cases
3. **Add real integration test** — Use `tests/fixtures/sample_bundle/` with actual file loading
4. **Fix `load_manifest()` bug** — Add test using real YAML fixture, fix path resolution

### P1 — Improve Coverage

5. **Add error path tests** — Tool execution failures, malformed responses, max_turns exhaustion
6. **Utilize or remove unused fixtures** — 4 fixtures in conftest.py are dead code
7. **Test grammar constraint pipeline** — `ConstraintPipeline.constrain()` and `GrammarConfig`
8. **Add event emission tests** — Verify all 7 event types are emitted at correct lifecycle points
9. **Test real Grail integration** — Load actual `.pym` files from fixtures

### P2 — Quality Improvements

10. **Strengthen assertions** — Replace `is not None` with actual behavior verification
11. **Remove redundant `@pytest.mark.asyncio`** — Clean up now that `asyncio_mode = "auto"`
12. **Add parametrized tests** — Cover multiple model types, response formats
13. **Add conftest.py fixtures for common setups** — Reduce duplication across test files
14. **Create fixtures for error scenarios** — Mock tools that raise exceptions, return malformed data

---

## Appendix: Test File Inventory

| File | Lines | Tests | Async | Mocks | Fixtures Used |
|------|-------|-------|-------|-------|---------------|
| `test_types.py` | 33 | 4 | 0 | 0 | 0 |
| `test_public_api.py` | 52 | 3 | 0 | 0 | 0 |
| `test_agent/test_bundle.py` | 28 | 1 | 1 | 3 | 0 |
| `test_models/test_adapter.py` | 36 | 2 | 0 | 0 | 0 |
| `test_models/test_parsers_comprehensive.py` | 92 | 7 | 0 | 0 | 0 |
| `test_tools/test_grail_tool.py` | 25 | 1 | 1 | 2 | 0 |
| `test_integration/test_full_agent.py` | 92 | 1 | 1 | 4 | 1 (`mock_client`) |
| `test_kernel/test_basic.py` | 52 | 1 | 1 | 3 | 1 (`mock_client`) |
| `test_client/test_factory.py` | 10 | 1 | 0 | 0 | 0 |
| `test_client/test_openai.py` | 37 | 1 | 1 | 2 | 0 |
| `test_events/test_observer.py` | 39 | 2 | 2 | 0 | 0 |
| `conftest.py` | 76 | — | — | — | — |
| **TOTAL** | **~650** | **16** | **7** | **14** | **2** |

---

*Analysis generated: 2026-02-26*  
*Cross-referenced with: CODE_REVIEW.md Section 6 (Test Suite)*
