# V0.3.1 Refactoring Plan

**Date:** 2026-02-26  
**Based on:** CODE_REVIEW.md, .analysis/test_review.md, .analysis/source_review.md, .analysis/config_review.md

---

## Overview

The v0.3.0 refactor achieved a simplified architecture (~20 files, 5 core concepts) but is incomplete. Three core differentiating features are non-functional, there are 3 runtime bugs, and the test suite provides false confidence.

---

## Phase 1: P0 - Release Blockers

### 1.1 Fix Runtime Bugs

| ID | Issue | File | Fix |
|----|-------|------|-----|
| BUG-1 | `response.to_dict()` crashes every completion | `client/openai.py:82` | Change to `response.model_dump()` |
| BUG-2 | Parser drops tool call IDs, breaking correlation | `models/parsers.py:30` | Use `ToolCall(id=tc["id"], name=func["name"], arguments=args)` instead of `ToolCall.create()` |
| BUG-3 | Tool context always `None`, call_id always "unknown" | `kernel.py:117` | Pass `tc` (ToolCall object) as context to `tool.execute(tc.arguments, tc)` |

### 1.2 Implement Core Features

| ID | Issue | File | Fix |
|----|-------|------|-----|
| FEAT-1 | Grail integration is entirely stubbed | `tools/grail.py:44-47` | Implement `discover_tools()` with `grail.load()`, add schema introspection from `@external` functions and `Input()` declarations |
| FEAT-2 | Grammar-constrained decoding pipeline is inert | `agent.py:75` | Wire `ConstraintPipeline` in `Agent.from_bundle()`, pass grammar config to kernel |
| FEAT-3 | Observer/event system is 85% dead | `kernel.py` | Emit all 7 event types: `ModelRequestEvent`, `ModelResponseEvent`, `ToolCallEvent`, `ToolResultEvent`, `TurnCompleteEvent`, `KernelEndEvent` |

### 1.3 Fix Dependencies

| ID | Issue | Fix |
|----|-------|-----|
| DEP-1 | `vllm>=0.15.1` as hard dependency | Remove from install requirements or move to optional extras (`pip install structured-agents[vllm]`) |
| DEP-2 | Dead dependencies: pydantic, jinja2, fsdantic, httpx | Remove from pyproject.toml |
| DEP-3 | Commented-out `cairn` in sources | Remove entirely |

---

## Phase 2: P1 - Production Readiness

### 2.1 Code Quality

| ID | Issue | File | Fix |
|----|-------|------|-----|
| ARCH-1 | Duplicate `build_client` function | `client/factory.py` and `client/openai.py:89-96` | Remove one, keep consistent return type |
| ARCH-2 | `ModelAdapter.__post_init__` mutates frozen dataclass | `adapter.py:21-24` | Use factory classmethod or non-optional fields with defaults |
| ARCH-3 | Default message formatter uses `str()` | `adapter.py:34-37` | Use `json.dumps()` for tool serialization |
| ARCH-4 | No adapter registry | `agent.py:73` | Add model-to-parser mapping in `from_bundle()` |
| ARCH-5 | `_tool_map()` rebuilds O(n) per step | `kernel.py:48-49` | Cache as instance attribute |
| ARCH-6 | Hardcoded vLLM URL | `agent.py:82` | Read from bundle manifest or environment |
| ARCH-7 | No `CompositeObserver` | `events/observer.py` | Add `CompositeObserver` to fan out to multiple observers |
| ARCH-8 | `ConstraintPipeline` adds indirection | `grammar/pipeline.py` | Consider plain function or keep with justification |

### 2.2 Type Safety

| ID | Issue | File | Fix |
|----|-------|------|-----|
| TYPE-1 | `script: Any, limits: Any` | `tools/grail.py:12` | Type as `grail.GrailScript`, `grail.Limits \| None` |
| TYPE-2 | `context: Any` in Tool.execute | `tools/protocol.py:14` | Create `ToolCallContext` dataclass |
| TYPE-3 | `response_parser: Any` | `models/adapter.py:15` | Type as `ResponseParser` protocol |
| TYPE-4 | `grammar_builder` 2nd arg `Any` | `models/adapter.py:14` | Use `DecodingConstraint` |
| TYPE-5 | `tools: list[Tool]` invariant | `kernel.py:40-41` | Use `Sequence[Tool]` |
| TYPE-6 | OpenAI SDK type mismatches | `client/openai.py:43-45` | Use proper SDK types (`ChatCompletionMessageParam`) |
| TYPE-7 | `RunResult` missing `slots=True` | `types.py:176` | Add `slots=True` to frozen dataclass |
| TYPE-8 | Variable shadowing in parser | `models/parsers.py:35` | Fix type consistency |

### 2.3 Dead Code Removal

| ID | Item | File | Fix |
|----|------|------|-----|
| DEAD-1 | `KernelConfig` | `types.py:14-18` | Remove or use as base for AgentKernel |
| DEAD-2 | `GrammarConfig` | `grammar/config.py:16-33` | Remove or unify with `DecodingConstraint` |
| DEAD-3 | `ToolResult.output_str` | `types.py:104-106` | Remove |
| DEAD-4 | `FunctionGemmaResponseParser` | `models/parsers.py:63-70` | Remove or implement distinct behavior |
| DEAD-5 | Exception hierarchy (5 classes) | `exceptions.py` | Either implement usage or remove |
| DEAD-6 | `max_history_messages` unused | `kernel.py:43` | Implement or remove |
| DEAD-7 | `**overrides` parameter | `agent.py:67` | Implement or remove |

---

## Phase 3: P2 - Quality Improvements

### 3.1 Test Suite

| ID | Issue | Fix |
|----|-------|-----|
| TEST-1 | Zero negative tests | Add tests for: tool execution failure, unknown tools, max_turns exhaustion, malformed responses |
| TEST-2 | Over-mocking | Write real integration tests using `tests/fixtures/sample_bundle/` |
| TEST-3 | No `conftest.py` | Add shared fixtures for mock clients, adapters, tools |
| TEST-4 | Weak assertions | Strengthen assertions to verify exact behavior |
| TEST-5 | Parser has no coverage | Add unit tests for `QwenResponseParser._parse_xml_tool_calls()` |
| TEST-6 | load_manifest bug | Fix `system_prompt` path (`initial_context.system_prompt`), add test with real fixture |
| TEST-7 | Remove redundant decorators | Remove `@pytest.mark.asyncio` (asyncio_mode="auto" set) |
| TEST-8 | Add parametrized tests | Use `@pytest.mark.parametrize` for parsers, events, messages |

### 3.2 Documentation

| ID | Issue | Fix |
|----|-------|-----|
| DOC-1 | README.md completely stale | Rewrite all code examples for v0.3.0 API |
| DOC-2 | ARCHITECTURE.md describes different codebase | Update to reflect actual v0.3.0 architecture |
| DOC-3 | Demo scripts broken | Fix or remove broken demos: `demo/workspace_agent_demo.py`, `demo/demo_steps/` |
| DOC-4 | Stale artifacts | Remove: planning docs, run logs, `__pycache__` |

### 3.3 Packaging

| ID | Issue | Fix |
|----|-------|-----|
| PKG-1 | Missing `py.typed` marker | Add `src/structured_agents/py.typed` |
| PKG-2 | KernelConfig not exported | Add to `__init__.py` `__all__` |
| PKG-3 | Exception hierarchy not exported | Add to `__init__.py` `__all__` |
| PKG-4 | Observer not passed to Agent | Fix `Agent.from_bundle()` to pass observer to kernel |

---

## Phase 4: Additional Fixes

### 4.1 Module-Level Issues

| ID | Issue | File | Fix |
|----|-------|------|-----|
| MOD-1 | `discover_tools` not exported top-level | Add to `__init__.py` |
| MOD-2 | `ResponseParser` protocol not exported | Add to `models/__init__.py` |
| MOD-3 | json.loads without error handling | `models/parsers.py:29` Add try/except |
| MOD-4 | tool_choice="none" with no tools | `kernel.py:87` Omit parameter when tools empty |
| MOD-5 | Concurrent tool errors not isolated | `kernel.py:119-129` Handle individual tool exceptions |
| MOD-6 | agents_dir path resolution bug | `agent.py:45` Fix parent path computation |
| MOD-7 | grammar_config hardcoded to None | `agent.py:29` Read from YAML |
| MOD-8 | Short tool call IDs | `types.py:89` Use 12+ hex chars |
| MOD-9 | No error event type | Add `ErrorEvent` to events/types.py |

---

## Implementation Order

```
Phase 1 (P0 - Blockers):
  1. Fix BUG-1, BUG-2, BUG-3 (runtime crashes)
  2. Implement FEAT-1 (Grail discovery)
  3. Implement FEAT-2 (grammar pipeline)
  4. Implement FEAT-3 (event emission)
  5. Fix DEP-1 (vllm dependency)

Phase 2 (P1 - Production):
  6. Fix ARCH-1 through ARCH-8
  7. Fix TYPE-1 through TYPE-8
  8. Remove DEAD-1 through DEAD-7

Phase 3 (P2 - Quality):
  9. Expand test suite (TEST-1 through TEST-8)
  10. Update documentation (DOC-1 through DOC-4)
  11. Fix packaging issues (PKG-1 through PKG-4)

Phase 4 (Extras):
  12. Fix MOD-1 through MOD-9
```

---

## Files to Modify

### Core Source Files
- `src/structured_agents/client/openai.py` - BUG-1, ARCH-1
- `src/structured_agents/models/parsers.py` - BUG-2, TYPE-8, MOD-3
- `src/structured_agents/kernel.py` - BUG-3, ARCH-5, ARCH-8, FEAT-3, MOD-4, MOD-5
- `src/structured_agents/tools/grail.py` - FEAT-1, TYPE-1
- `src/structured_agents/tools/protocol.py` - TYPE-2
- `src/structured_agents/models/adapter.py` - ARCH-2, ARCH-3, TYPE-3, TYPE-4
- `src/structured_agents/agent.py` - ARCH-4, ARCH-6, MOD-6, MOD-7, PKG-4
- `src/structured_agents/types.py` - DEAD-1, DEAD-3, MOD-8
- `src/structured_agents/grammar/config.py` - DEAD-2
- `src/structured_agents/grammar/pipeline.py` - ARCH-8
- `src/structured_agents/exceptions.py` - DEAD-5
- `src/structured_agents/events/observer.py` - ARCH-7
- `src/structured_agents/events/types.py` - MOD-9
- `src/structured_agents/client/factory.py` - ARCH-1 (remove file)
- `src/structured_agents/__init__.py` - PKG-2, PKG-3

### Config Files
- `pyproject.toml` - DEP-1, DEP-2, DEP-3

### Test Files
- Create `tests/conftest.py` - TEST-3
- Add comprehensive parser tests - TEST-5
- Add integration tests with fixtures - TEST-2
- Add negative tests - TEST-1
- Fix weak assertions - TEST-4

### Documentation
- `README.md` - DOC-1
- `ARCHITECTURE.md` - DOC-2
- Remove stale demo files - DOC-3, DOC-4

### New Files
- `src/structured_agents/py.typed` - PKG-1
- `src/structured_agents/events/types.py` (add ErrorEvent) - MOD-9

---

## Notes

- The v0.3.0 architecture is sound - the issue is incomplete implementation
- Prioritize Phase 1 before any release
- Tests should be added alongside each fix to prevent regression
- Use vendored `.context/` sources for vLLM/xgrammar behavior verification
