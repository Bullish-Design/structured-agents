# Workspace Agent Demo Review

## 1. Runtime Error Analysis

### Error Description

Running `uv run demo/workspace_agent_demo.py` fails at Section 2 (Single-Turn with Observer) with:

```
TypeError: 'NoneType' object is not subscriptable
```

at `src/structured_agents/client/openai_compat.py:56`:

```python
choice = response.choices[0]
```

### Call Chain

1. `workspace_agent_demo.py:288` — `agent.process_message(query, max_turns=3)`
2. `workspace_agent_demo.py:232` — `self.kernel.run(initial_messages=messages, ...)`
3. `kernel.py:344` — `step_result = await self.step(messages, tools, ...)`
4. `kernel.py:155` — `response = await self._client.chat_completion(...)`
5. `openai_compat.py:54` — `response = await self._client.chat.completions.create(**kwargs)`
6. `openai_compat.py:56` — `choice = response.choices[0]` **CRASH**

### Root Cause Analysis

#### What is sent to vLLM

The kernel's `step()` method (`kernel.py:130-163`) constructs the following API call:

- `messages`: formatted conversation (system + user)
- `tools`: OpenAI-style tool definitions (6 tools from bundle)
- `tool_choice`: `"auto"` (from `KernelConfig` default)
- `extra_body`: `{"structured_outputs": {"type": "structural_tag", "structural_tag": "<StructuralTag JSON string>"}}`
- `model`: `Qwen/Qwen3-4B-Instruct-2507-FP8`

This means vLLM receives **both** OpenAI `tools` definitions **and** `structured_outputs` with a `structural_tag` grammar constraint simultaneously.

#### Why `response.choices` is `None`

Investigation of vLLM 0.15.1 source (`.context/vllm/vllm-0.15.1/`) reveals:

- `ChatCompletionResponse.choices` is typed as `list[ChatCompletionResponseChoice]` (NOT Optional) in `entrypoints/openai/engine/protocol.py`
- vLLM cannot return a response where `choices` is literally `None`
- Error paths return `ErrorResponse` (a different type entirely)

The most probable explanation is that vLLM returned an **`ErrorResponse`** (a JSON error object), and the OpenAI Python client either:
1. Parsed it into a response object where `choices` is set to `None` (client-side parsing issue)
2. Returned a response with an empty `choices` list `[]` (causing `IndexError`, not `TypeError`)
3. Raised an exception that was caught by the generic `except Exception` at `openai_compat.py:98` and re-raised as `KernelError`, which then surfaced as a `TypeError` during response parsing

**The `TypeError: 'NoneType' object is not subscriptable` suggests the OpenAI client received an error response and set `response.choices = None` rather than raising a proper API error.** This happens when vLLM returns an HTTP 200 with error content (e.g., an xgrammar compilation failure), which the OpenAI client doesn't treat as an HTTP error but also can't fully parse into a valid `ChatCompletion` object.

#### The `"type"` Field in `structured_outputs` — NOT the Root Cause

The `to_vllm_payload()` method in `src/structured_agents/grammar/artifacts.py:31-37` includes a `"type": "structural_tag"` key:

```python
def to_vllm_payload(self) -> dict[str, Any]:
    return {
        "structured_outputs": {
            "type": "structural_tag",           # <-- not a valid field
            "structural_tag": self.tag.model_dump_json(),
        }
    }
```

vLLM's `StructuredOutputsParams` dataclass (`.context/vllm/vllm-0.15.1/vllm/sampling_params.py:33-46`) has NO `type` field. However, since `StructuredOutputsParams` is a **Pydantic dataclass** with default `extra="ignore"`, the `"type"` key is **silently discarded** during deserialization. This is NOT the cause of the error.

The same applies to `EBNFGrammar` (`"type": "grammar"`) and `JsonSchemaGrammar` (`"type": "json"`) — all have the same unnecessary `"type"` field that is silently ignored.

#### The Real Problem: `send_tools_to_api` Is Never Checked

The `GrammarConfig` dataclass (`src/structured_agents/grammar/config.py:14`) defines:

```python
send_tools_to_api: bool = True
```

With documentation stating:
> When True (default), tools are sent to vLLM which may override the grammar constraint with its own JSON schema for tool calling.
> When False, tools are NOT sent to vLLM. This is needed for EBNF mode to work properly.

**However, the kernel's `step()` method NEVER checks `self.grammar_config.send_tools_to_api`.** At `kernel.py:133-135`:

```python
formatted_tools = (
    self.plugin.format_tools(resolved_tools) if resolved_tools else None
)
```

Tools are ALWAYS sent when `resolved_tools` is non-empty. The `send_tools_to_api` flag has no effect.

#### How `tools` + `structural_tag` Interact in vLLM 0.15.1

When both are present with `tool_choice="auto"`:

1. **`_preprocess_chat()`** (`.context/vllm/vllm-0.15.1/vllm/entrypoints/openai/engine/serving.py:1257`) calls `tool_parser.adjust_request()` BEFORE `to_sampling_params()`
2. **`adjust_request()`** (`.context/vllm/vllm-0.15.1/vllm/tool_parsers/abstract_tool_parser.py:56-84`) calls `get_json_schema_from_tools()` which returns `None` for `tool_choice="auto"` (`.context/vllm/vllm-0.15.1/vllm/tool_parsers/utils.py:229`)
3. Because the schema is `None`, `adjust_request()` does NOT override `structured_outputs`
4. The `structural_tag` constraint passes through to the sampling params

This means the **combination should work** for `tool_choice="auto"`. The structural_tag grammar constrains generation, and vLLM's tool parser attempts post-hoc text parsing on the result.

The likely failure point is **xgrammar structural_tag compilation** — if the `StructuralTag` JSON payload is malformed or incompatible with xgrammar 0.1.29's expectations, xgrammar could fail to compile the grammar, causing vLLM to return an error response.

#### Possible Contributing Factors

1. **xgrammar version mismatch**: The `StructuralTag` object is from xgrammar 0.1.29 (`.context/xgrammar-0.1.29/`). If the installed xgrammar version on the vLLM server differs, the serialized `StructuralTag` JSON may be incompatible.

2. **Grammar compilation failure**: If xgrammar cannot compile the structural_tag grammar for the given tool schemas (e.g., deeply nested parameters, unsupported JSON schema features), vLLM may return an error.

3. **`model_dump_json()` output format**: The `StructuralTag.model_dump_json()` call at `artifacts.py:35` must produce a JSON string that vLLM can pass to `StructuredOutputsParams(structural_tag=...)`. Since vLLM's `structural_tag` field is typed as `str | None`, the string value should be parseable by xgrammar on the server side.

### Recommended Fixes

#### Fix 1: Implement `send_tools_to_api` in the Kernel (Bug Fix)

```python
# kernel.py, in step() method, around line 133
formatted_tools = (
    self.plugin.format_tools(resolved_tools)
    if resolved_tools and self.grammar_config.send_tools_to_api
    else None
)
```

This implements the documented behavior and prevents tools from being sent alongside the grammar constraint when not desired.

#### Fix 2: Defensive `response.choices` Handling (Robustness)

```python
# openai_compat.py, around line 56
if not response.choices:
    raise KernelError(
        f"LLM returned no choices. Raw response: {response.model_dump()}",
        phase="model_call",
    )
choice = response.choices[0]
```

This converts a cryptic `TypeError`/`IndexError` into an actionable error message with the raw response for debugging.

#### Fix 3: Remove Unnecessary `"type"` Keys from Payload (Cleanup)

While not the root cause, the `"type"` keys in all three grammar artifact payloads are unnecessary noise:

```python
# artifacts.py - StructuralTagGrammar.to_vllm_payload()
def to_vllm_payload(self) -> dict[str, Any]:
    return {
        "structured_outputs": {
            "structural_tag": self.tag.model_dump_json(),
        }
    }
```

Similarly for `EBNFGrammar` (remove `"type": "grammar"`) and `JsonSchemaGrammar` (remove `"type": "json"`).

#### Fix 4: Add Diagnostic Logging to `chat_completion` (Debugging)

```python
# openai_compat.py, before the API call
logger.debug(
    "Chat completion request: model=%s, tools=%d, extra_body=%s",
    model or self._config.model,
    len(tools) if tools else 0,
    extra_body,
)
```

#### Fix 5: Test with `send_tools_to_api=False` (Workaround)

In `demo/agents/workspace_agent/bundle.yaml`:

```yaml
grammar:
  mode: "structural_tag"
  allow_parallel_calls: true
  args_format: "permissive"
  send_tools_to_api: false    # <-- add this
```

This prevents tools from being sent to vLLM alongside the structural_tag grammar. The model still sees tool definitions in the system prompt (via message formatting), and the structural_tag grammar constrains output format. The response parser then extracts tool calls from the constrained output.

---

## 2. Demo Code Review

### File: `demo/workspace_agent_demo.py` (641 lines)

### Architecture

The demo uses a `WorkspaceAgent` class (line 180) that composes:
- `AgentBundle` from `load_bundle()`
- `GrailRegistry` + `GrailBackend` → `RegistryBackendToolSource`
- `DemoObserver` + `MetricsObserver` → `CompositeObserver`
- `AgentKernel` with bundle-derived plugin and grammar config

It runs 11 sections sequentially, each demonstrating a different library feature.

### Issues Found

#### Issue 1: `send_tools_to_api` Not Wired (Severity: High)

As discussed in the root cause analysis, the kernel ignores `GrammarConfig.send_tools_to_api`. The demo's Section 4 sets `send_tools_to_api=False` for EBNF mode (`line 339`), but this has no effect:

```python
("ebnf", GrammarConfig(mode="ebnf", send_tools_to_api=False)),
```

The kernel still sends tools to vLLM, which then overrides the EBNF grammar with its own JSON schema tool constraint.

#### Issue 2: Result Type Confusion in Section 2 (Severity: Medium)

Section 2 (`section_2_single_turn`, line 279) calls `agent.process_message()` which returns a `RunResult`, but the print statements at lines 291-293 reference `result.tool_calls` which is NOT a field on `RunResult`:

```python
print(f"    Tool calls: {len(result.tool_calls) if result.tool_calls else 0}")
```

`RunResult` has: `final_message`, `history`, `turn_count`, `termination_reason`, `final_tool_result`, `total_usage`. It does NOT have `tool_calls`. This would produce an `AttributeError` even if the LLM call succeeded.

#### Issue 3: Shared Observer State Across Sections (Severity: Medium)

The `WorkspaceAgent` creates observers once (lines 200-202) but reuses them across multiple sections. The `DemoObserver.events` list accumulates events from ALL sections, which means:

- Section 5 (line 392-396) filters `tool_call` events from `agent.demo_observer.events`, getting events from sections 2, 3, 5
- Section 11 (line 600) reports total event count from ALL sections
- Event counts are misleading because they're cumulative

The observers should be reset between sections or scoped per-section.

#### Issue 4: `uuid` Import Unused (Severity: Low)

Line 4 imports `uuid` but it's never used in the demo.

#### Issue 5: No Error Handling for vLLM Connectivity (Severity: Medium)

The demo assumes vLLM is available at `remora-server:8000`. There's no connectivity check before running all 11 sections. If the server is down, Section 2 fails immediately with an unhelpful error. The DEMO_IMPLEMENTATION_PLAN Step 1 describes a connectivity check, but the actual demo doesn't implement it.

#### Issue 6: `WorkspaceAgent.process_message` Returns `RunResult` Not `StepResult` (Severity: Low)

The function name and Section 2's title ("Single-Turn") suggest a single step, but `process_message` always calls `kernel.run()`, which loops until termination. For a true single-turn demo, it should call `kernel.step()` directly.

#### Issue 7: State Directory Not Cleaned Between Runs (Severity: Low)

`STATE_DIR` (`demo/agents/workspace_agent/state/`) is created at module level (line 38-39) and persists across demo runs. Tasks added in previous runs affect subsequent runs (e.g., `list_entries` returns stale tasks). The demo should either clean the state directory at startup or use a temporary directory.

#### Issue 8: `build_externals` Function Uses Sync I/O in Async Functions (Severity: Low)

Lines 49-64 define `async def write_file`, `async def read_file`, etc., but they use synchronous `open()`, `os.listdir()`, and `os.path.exists()` calls. These block the event loop. They should use `aiofiles` or `asyncio.to_thread()`.

#### Issue 9: Section 6 Resource Leak (Severity: Low)

`create_kernel_for_query` (line 411) creates a new `GrailBackend` for each query but calls `backend.shutdown()` only once at line 454. In the concurrent execution path (line 487-488), three backends are created via `asyncio.gather` but each shuts down independently, which is correct. However, if any query fails, the backend may not be cleaned up.

#### Issue 10: Missing `__all__` or Public API Boundary (Severity: Low)

The demo imports from internal modules (`structured_agents.bundles.loader`, `structured_agents.registries.grail`, `structured_agents.backends.grail`, `structured_agents.plugins.registry`). While functional, a gold-standard demo should import from the public API (`structured_agents`) wherever possible.

---

## 3. Library API Coverage Matrix

### Symbols Exported from `structured_agents.__init__` (48 total)

| Symbol | Category | Demonstrated | Section(s) | Notes |
|--------|----------|:---:|---|---|
| `AgentKernel` | Core | YES | 2-8 | Used via `WorkspaceAgent` |
| `KernelConfig` | Config | YES | 2-8 | Multiple configurations shown |
| `Message` | Types | YES | 2-4 | Built from bundle templates |
| `ToolCall` | Types | NO | — | Never constructed directly; only seen via results |
| `ToolCall.create()` | Factory | NO | — | Not demonstrated |
| `ToolExecutionStrategy` | Config | YES | 2 | `mode="concurrent"` at line 209 |
| `ToolResult` | Types | PARTIAL | 7 | Seen in error events, not inspected directly |
| `ToolSchema` | Types | INDIRECT | 1 | Via `bundle.tool_schemas` |
| `StepResult` | Types | YES | 4 | Direct `kernel.step()` usage |
| `RunResult` | Types | YES | 2-3 | Via `process_message()` return |
| `TokenUsage` | Types | YES | 3, 8 | Printed in summary |
| `ModelPlugin` | Protocol | INDIRECT | — | Used via QwenPlugin |
| `FunctionGemmaPlugin` | Plugin | NO | — | Never instantiated or used |
| `QwenPlugin` | Plugin | YES | 1, 9 | Primary plugin, also in plugin swap |
| `ToolBackend` | Protocol | INDIRECT | — | Via GrailBackend |
| `PythonBackend` | Backend | NO | — | Not demonstrated |
| `CompositeBackend` | Backend | NO | — | Not demonstrated |
| `GrailBackend` | Backend | YES | 2-8 | Primary backend |
| `GrailBackendConfig` | Config | YES | 2-8 | Multiple instances |
| `ToolSource` | Protocol | INDIRECT | — | Via RegistryBackendToolSource |
| `RegistryBackendToolSource` | Composition | YES | 2-8 | Primary tool source |
| `ContextProvider` | Type Alias | YES | 2-8 | `_provide_context` at line 223 |
| `AgentBundle` | Bundle | YES | 1 | `load_bundle()` return type |
| `load_bundle` | Function | YES | 1, 4, 6, 9-10 | Multiple uses |
| `Observer` | Protocol | INDIRECT | — | Via DemoObserver (structural conformance) |
| `NullObserver` | Observer | YES | 6 | Used in batched inference |
| `CompositeObserver` | Observer | YES | 2, 11 | Combines Demo + Metrics observers |
| `KernelStartEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `KernelEndEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `ModelRequestEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `ModelResponseEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `ToolCallEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `ToolResultEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `TurnCompleteEvent` | Event | YES | 2-8 | Handled by DemoObserver |
| `HistoryStrategy` | Protocol | NO | — | Never shown explicitly |
| `SlidingWindowHistory` | History | DEFAULT | — | Used implicitly (kernel default) |
| `KeepAllHistory` | History | NO | — | Not demonstrated |
| `LLMClient` | Protocol | NO | — | Not demonstrated (injectable client) |
| `OpenAICompatibleClient` | Client | INDIRECT | — | Created internally by kernel |
| `build_client` | Factory | NO | — | Never called directly |
| `CompletionResponse` | Types | NO | — | Never shown directly |
| `StructuredAgentsError` | Exception | NO | — | Not caught or raised |
| `KernelError` | Exception | NO | — | Not caught explicitly |
| `ToolExecutionError` | Exception | NO | — | Not demonstrated |
| `PluginError` | Exception | NO | — | Not demonstrated |
| `BundleError` | Exception | NO | — | Not demonstrated |
| `BackendError` | Exception | NO | — | Not demonstrated |
| `GrammarConfig` | Config | YES | 4, 6 | Multiple modes shown |

### Additional Internal Symbols Used by Demo

| Symbol | Module | Demonstrated |
|--------|--------|:---:|
| `PluginRegistry` | `plugins.registry` | YES (Section 9) |
| `get_plugin` | `plugins.registry` | NO (uses `PluginRegistry.get()` instead) |
| `GrailRegistry` | `registries.grail` | YES (Section 10) |
| `GrailRegistryConfig` | `registries.grail` | YES (Section 10) |

### Coverage Summary

| Category | Total | Demonstrated | Coverage |
|----------|-------|-------------|----------|
| Core (Kernel) | 1 | 1 | 100% |
| Config types | 4 | 3 | 75% |
| Data types | 7 | 5 | 71% |
| Plugins | 3 | 1 | 33% |
| Backends | 4 | 1 | 25% |
| Tool Sources | 3 | 2 | 67% |
| Bundles | 2 | 2 | 100% |
| Observer | 9 | 8 | 89% |
| History | 3 | 0 | 0% |
| Client | 3 | 0 | 0% |
| Exceptions | 6 | 0 | 0% |
| Grammar | 1 | 1 | 100% |
| **Total** | **48** | **24** | **50%** |

---

## 4. Feature Gaps

### High Priority (Core Library Features Not Shown)

#### 4.1 Exception Handling

None of the 6 exception types are demonstrated. The demo's Section 7 ("Error Handling") tests with a nonexistent task, but catches errors via observer events — it never shows `try/except` with library exception types. A gold-standard demo should show:

```python
from structured_agents import KernelError, ToolExecutionError

try:
    result = await kernel.run(...)
except KernelError as e:
    print(f"Kernel error in phase '{e.phase}': {e}")
except ToolExecutionError as e:
    print(f"Tool '{e.tool_name}' failed (call {e.call_id}): {e}")
```

#### 4.2 Injectable `LLMClient`

The `AgentKernel` accepts an optional `client: LLMClient` parameter for dependency injection. This enables testing with mock clients and custom client implementations. Not demonstrated.

#### 4.3 `PythonBackend` + `PythonRegistry`

The Python-native tool system (no Grail dependency) is a significant feature for simple use cases and testing. Not demonstrated.

#### 4.4 History Strategies

Neither `SlidingWindowHistory` configuration nor `KeepAllHistory` are explicitly shown. The kernel uses `SlidingWindowHistory` by default, but the demo never shows:
- Configuring window size via `max_history_messages`
- Swapping to `KeepAllHistory`
- The effect of history trimming on long conversations

### Medium Priority (Useful Patterns Not Shown)

#### 4.5 `ToolCall.create()` Factory

The convenience factory for creating tool calls with auto-generated IDs is useful for testing and manual tool invocations.

#### 4.6 `CompositeBackend` + `CompositeRegistry`

Combining multiple backends/registries is a core architectural pattern (e.g., Grail tools + Python tools in the same agent). Not demonstrated.

#### 4.7 Direct `kernel.step()` Usage

Section 4 uses `kernel.step()` directly, but the pattern is not highlighted as a distinct usage mode vs. `kernel.run()`. A dedicated section showing step-by-step manual control would be valuable.

#### 4.8 `build_client()` Direct Usage

Using `build_client()` to create a standalone client for direct LLM calls (without the kernel) is a useful escape hatch. Not shown.

#### 4.9 `FunctionGemmaPlugin`

The second plugin implementation. Section 9 lists it via `PluginRegistry` but never instantiates or uses it.

### Low Priority (Nice-to-Have)

#### 4.10 `ContextProvider` on Tools

Tool-level context providers (via `tool_source.context_providers()`) are distinct from the per-run `context_provider` parameter. This distinction is not demonstrated.

#### 4.11 `model_override` via Context

The kernel checks `context.get("model_override")` at `kernel.py:333-338` to dynamically switch models per-turn. Not demonstrated.

#### 4.12 `CompletionResponse` Direct Inspection

Showing the raw `CompletionResponse` structure (content, tool_calls, usage, finish_reason, raw_response) would help users understand what the client returns.

---

## 5. Demo vs. Implementation Plan Alignment

The `demo/DEMO_IMPLEMENTATION_PLAN.md` describes a phased, 11-step incremental approach. The actual demo (`workspace_agent_demo.py`) diverges significantly:

| Plan Step | Plan Description | Demo Implementation | Gap |
|-----------|-----------------|--------------------|----|
| Step 1 | Verify vLLM connectivity | Not implemented | No connectivity check |
| Step 2 | Basic chat without tools | Not implemented as standalone | Skipped |
| Step 3-4 | Grail script execution | Implicit via agent | Not a standalone demo |
| Step 5 | Grail Dispatcher (no LLM) | Not implemented | Different architecture |
| Step 6 | Chat Agent (no tools) | Not implemented | Different architecture |
| Step 7 | Grammar-constrained decoding | Section 4 (partial) | Grammar modes shown but not as standalone |
| Step 8-9 | Shell agent with tools | Not implemented | Different agent type |
| Step 10 | Code agent | Not implemented | Different agent type |
| Step 11 | Full orchestration | Sections 1-11 (partial) | Single workspace agent, not multi-agent |

The plan envisions a multi-agent orchestration demo with different agent types (chat, shell, code, dispatcher). The actual demo is a single workspace agent exercising different library features. While the demo covers more library API surface, it doesn't demonstrate the multi-agent patterns described in the plan.

---

## 6. Recommendations

### Immediate Fixes (Required for Demo to Run)

1. **Implement `send_tools_to_api` in the kernel** — The kernel at `kernel.py:133-135` must check `self.grammar_config.send_tools_to_api` before including `formatted_tools` in the API call.

2. **Add defensive `response.choices` check** — At `openai_compat.py:56`, guard against `None` or empty `choices` with a clear error message.

3. **Fix `result.tool_calls` AttributeError in Section 2** — `RunResult` does not have a `tool_calls` attribute. Use `result.turn_count` or inspect `result.history` instead.

### Recommended Improvements

4. **Add vLLM connectivity check** — Section 0 or a pre-flight check before running any sections.

5. **Reset observer state between sections** — Add `agent.demo_observer.events.clear()` between sections, or create a fresh observer per section.

6. **Clean state directory at startup** — Remove or recreate `STATE_DIR` at the beginning of `main()` to ensure deterministic runs.

7. **Remove unused `uuid` import** at line 4.

8. **Use `asyncio.to_thread()` for sync I/O** in `build_externals` functions.

### Feature Coverage Additions

9. **Add a PythonBackend section** — Show Python-native tools without Grail dependency.

10. **Add an exception handling section** — Demonstrate `try/except` with `KernelError`, `ToolExecutionError`, showing error recovery patterns.

11. **Add a history strategy section** — Show `KeepAllHistory` vs. `SlidingWindowHistory` with configurable window size.

12. **Add an injectable client section** — Show creating a mock `LLMClient` for testing, or using `build_client()` directly.

13. **Add a CompositeBackend section** — Show combining Grail + Python backends in a single agent.

14. **Import from public API** — Replace internal imports (`structured_agents.bundles.loader`, `structured_agents.registries.grail`, etc.) with public `structured_agents` imports where available.

### Remove from Payload

15. **Remove `"type"` keys from grammar artifact payloads** — The `"type"` field in `EBNFGrammar.to_vllm_payload()`, `StructuralTagGrammar.to_vllm_payload()`, and `JsonSchemaGrammar.to_vllm_payload()` is silently ignored by vLLM but adds unnecessary noise. Remove it from all three.

---

## 7. Files Referenced

| File | Lines | Role |
|------|-------|------|
| `demo/workspace_agent_demo.py` | 641 | Demo script under review |
| `demo/DEMO_IMPLEMENTATION_PLAN.md` | 1144 | Implementation plan |
| `demo/agents/workspace_agent/bundle.yaml` | 42 | Agent bundle configuration |
| `src/structured_agents/kernel.py` | 423 | Core kernel (agent loop) |
| `src/structured_agents/client/openai_compat.py` | 107 | OpenAI-compatible client |
| `src/structured_agents/grammar/artifacts.py` | 58 | Grammar artifacts with `to_vllm_payload()` |
| `src/structured_agents/grammar/config.py` | 25 | Grammar configuration |
| `src/structured_agents/plugins/qwen.py` | 36 | Qwen plugin |
| `src/structured_agents/plugins/qwen_components.py` | 148 | Qwen component implementations |
| `src/structured_agents/plugins/composed.py` | 72 | Composed plugin base class |
| `src/structured_agents/__init__.py` | 116 | Public API exports (48 symbols) |
| `.context/vllm/vllm-0.15.1/vllm/sampling_params.py` | — | `StructuredOutputsParams` definition |
| `.context/vllm/vllm-0.15.1/vllm/entrypoints/openai/chat_completion/protocol.py` | — | Chat completion request parsing |
| `.context/vllm/vllm-0.15.1/vllm/entrypoints/openai/engine/protocol.py` | — | `OpenAIBaseModel` with `extra="allow"` |
| `.context/vllm/vllm-0.15.1/vllm/tool_parsers/abstract_tool_parser.py` | — | Tool parser `adjust_request()` |
| `.context/vllm/vllm-0.15.1/vllm/tool_parsers/utils.py` | — | `get_json_schema_from_tools()` |
