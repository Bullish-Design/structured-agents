# Workspace Demo Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 6 failing tests, fix demo issues, and expand the demo to cover ~85% of the library's public API (up from 50%).

**Architecture:** The demo (`demo/workspace_agent_demo.py`) is a single-file showcase of `structured-agents`. Some of the library's implementation bugs (kernel, client, grammar artifacts) were already fixed in commit `2b2e23d`, but 6 tests still assert the old behavior. This plan first fixes the tests, then iteratively improves the demo.

**Tech Stack:** Python 3.12, pytest (asyncio_mode="auto"), uv, vLLM 0.15.1, xgrammar 0.1.29

**Current State (as of commit `2b2e23d`):**
- `kernel.py:133-135` — ALREADY checks `self.grammar_config.send_tools_to_api` ✓
- `openai_compat.py:63-67` — ALREADY guards `response.choices` ✓
- `artifacts.py` — ALREADY removed `"type"` keys from all three `to_vllm_payload()` methods ✓
- **6 tests still assert the old `"type"` key behavior** ← This plan fixes these
- Demo has no `result.tool_calls` bug (was already fixed to `result.turn_count`) ✓

---

## Part 1: Fix Failing Tests (6 tests)

### Task 1: Fix `test_artifacts.py` — Remove `"type"` Key Assertions

**Files:**
- Modify: `tests/test_grammar/test_artifacts.py:13-41`

**Step 1: Update `test_ebnf_payload` assertion**

The current test at line 16-18 asserts:
```python
assert payload == {
    "structured_outputs": {"type": "grammar", "grammar": 'root ::= "ok"'}
}
```

The implementation now produces (artifacts.py:16-21):
```python
return {
    "structured_outputs": {
        "grammar": self.grammar,
    }
}
```

Change to:
```python
assert payload == {
    "structured_outputs": {"grammar": 'root ::= "ok"'}
}
```

**Step 2: Update `test_structural_tag_payload` assertion**

The current test at line 31 asserts:
```python
assert payload["structured_outputs"]["type"] == "structural_tag"
```

Remove this line. The remaining assertions at lines 32-33 are correct:
```python
assert "structural_tag" in payload["structured_outputs"]
assert payload["structured_outputs"]["structural_tag"] == tag.model_dump_json()
```

**Step 3: Update `test_json_schema_payload` assertion**

The current test at line 40 asserts:
```python
assert payload["structured_outputs"]["type"] == "json"
```

Remove this line. The remaining assertion at line 41 is correct:
```python
assert payload["structured_outputs"]["json"]["json_schema"] == schema
```

**Step 4: Run the tests**

Run: `uv run pytest tests/test_grammar/test_artifacts.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add tests/test_grammar/test_artifacts.py
git commit -m "fix(tests): remove stale 'type' key assertions from artifact tests"
```

---

### Task 2: Fix `test_function_gemma_builder.py` — Remove `"type"` Key Assertion

**Files:**
- Modify: `tests/test_grammar/test_function_gemma_builder.py:73`

**Step 1: Update `test_build_structural_tag` assertion**

The current test at line 73 asserts:
```python
assert payload["structured_outputs"]["type"] == "structural_tag"
```

Remove this line entirely. The test at line 71 already verifies `isinstance(grammar, StructuralTagGrammar)`, and line 72 calls `to_vllm_payload()`. To maintain meaningful validation, replace the removed line with:

```python
assert "structural_tag" in payload["structured_outputs"]
```

**Step 2: Run the test**

Run: `uv run pytest tests/test_grammar/test_function_gemma_builder.py -v`
Expected: 6 passed

**Step 3: Commit**

```bash
git add tests/test_grammar/test_function_gemma_builder.py
git commit -m "fix(tests): remove stale 'type' key assertion from function_gemma builder test"
```

---

### Task 3: Fix `test_qwen3_builder.py` — Remove `"type"` Key Assertion

**Files:**
- Modify: `tests/test_grammar/test_qwen3_builder.py:46`

**Step 1: Update `test_build_structural_tag_single_tool` assertion**

The current test at line 46 asserts:
```python
assert payload["structured_outputs"]["type"] == "structural_tag"
```

Replace with:
```python
assert "structural_tag" in payload["structured_outputs"]
```

**Step 2: Run the test**

Run: `uv run pytest tests/test_grammar/test_qwen3_builder.py -v`
Expected: 8 passed

**Step 3: Commit**

```bash
git add tests/test_grammar/test_qwen3_builder.py
git commit -m "fix(tests): remove stale 'type' key assertion from qwen3 builder test"
```

---

### Task 4: Fix `test_function_gemma.py` — Remove `"type"` Key in Plugin Test

**Files:**
- Modify: `tests/test_plugins/test_function_gemma.py:54-56`

**Step 1: Update `test_extra_body_with_grammar` assertion**

The current test at line 54-56 asserts:
```python
assert result == {
    "structured_outputs": {"type": "grammar", "grammar": "some grammar"}
}
```

Change to:
```python
assert result == {
    "structured_outputs": {"grammar": "some grammar"}
}
```

**Step 2: Run the test**

Run: `uv run pytest tests/test_plugins/test_function_gemma.py -v`
Expected: 5 passed

**Step 3: Commit**

```bash
git add tests/test_plugins/test_function_gemma.py
git commit -m "fix(tests): remove stale 'type' key assertion from function_gemma plugin test"
```

---

### Task 5: Run Full Test Suite — Verify All 6 Failures Resolved

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: 0 failed, 105+ passed

**Step 2: If any failures remain, fix them before proceeding**

---

## Part 2: Demo Script Improvements

### Task 6: Remove Unused `uuid` Import

**Files:**
- Modify: `demo/workspace_agent_demo.py:1-6`

**Step 1: Remove the unused import**

Current line 4:
```python
from asyncio import run
```

Wait — re-read the current imports. The file no longer has `import uuid` (it was already removed in the refactor). Verify by reading lines 1-6 of the demo. If `uuid` is present, remove it. If not, skip this task.

**Step 2: Run the demo imports**

Run: `uv run python -c "import demo.workspace_agent_demo"`
Expected: No ImportError

---

### Task 7: Add vLLM Connectivity Pre-Flight Check

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add a connectivity check function before `main()`**

Add this function after the `WorkspaceAgent` class definition (around line 255):

```python
async def preflight_check(base_url: str) -> bool:
    """Check vLLM server connectivity before running demo."""
    import httpx

    health_url = base_url.replace("/v1", "/health")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(health_url)
            if resp.status_code == 200:
                print(f"  vLLM server at {base_url}: OK")
                return True
            print(f"  vLLM server at {base_url}: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  vLLM server at {base_url}: UNREACHABLE ({e})")
        return False
```

**Step 2: Call pre-flight check at the start of `main()`**

Add at the top of `main()`, before `agent = WorkspaceAgent(AGENT_DIR)`:

```python
base_url = "http://remora-server:8000/v1"
print("\n  Pre-flight: Checking vLLM connectivity...")
if not await preflight_check(base_url):
    print("\n  ABORT: Cannot reach vLLM server. Start it first.")
    return
```

**Step 3: Verify httpx is available**

Run: `uv run python -c "import httpx; print(httpx.__version__)"`
Expected: Version string (httpx is a dependency of openai). If not available, use `aiohttp` or the openai client directly.

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "feat(demo): add vLLM connectivity pre-flight check"
```

---

### Task 8: Reset Observer State Between Sections

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add a `reset_observers` method to `WorkspaceAgent`**

Add to the `WorkspaceAgent` class (after `close` method):

```python
def reset_observers(self) -> None:
    """Reset observer state between demo sections."""
    self.demo_observer.events.clear()
    self.metrics_observer.model_durations.clear()
    self.metrics_observer.tool_durations.clear()
```

**Step 2: Call `reset_observers()` between sections in `main()`**

In the `main()` function, add `agent.reset_observers()` before each section that uses the shared agent (sections 2, 3, 5, 7, 8, 11). Example:

```python
await section_1_bundle_loading(AGENT_DIR)

agent.reset_observers()
await section_2_single_turn(agent)

agent.reset_observers()
await section_3_multi_turn(agent)

await section_4_grammar_modes(AGENT_DIR)

agent.reset_observers()
await section_5_concurrent_tools(agent)

await section_6_batched_inference(AGENT_DIR)

agent.reset_observers()
await section_7_error_handling(agent)

# Section 8 intentionally keeps metrics from section 7
await section_8_summary(agent)

await section_9_plugin_swap(AGENT_DIR)
await section_10_registry_discovery(AGENT_DIR)

# Section 11 shows cumulative observer data, so don't reset
await section_11_composite_observer(agent)
```

**Step 3: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "fix(demo): reset observer state between sections for accurate per-section metrics"
```

---

### Task 9: Clean State Directory at Startup

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add state cleanup at the start of `main()`**

Add after the pre-flight check and before `agent = WorkspaceAgent(AGENT_DIR)`:

```python
# Clean state directory for deterministic demo runs
import shutil
if STATE_DIR.exists():
    shutil.rmtree(STATE_DIR)
STATE_DIR.mkdir(parents=True, exist_ok=True)
print(f"  State directory cleaned: {STATE_DIR}")
```

**Step 2: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "fix(demo): clean state directory at startup for deterministic runs"
```

---

### Task 10: Fix Sync I/O in Async `build_externals` Functions

**Files:**
- Modify: `demo/workspace_agent_demo.py:42-71`

**Step 1: Wrap sync I/O calls with `asyncio.to_thread()`**

Replace the `build_externals` function body. The current functions use sync `open()`, `os.makedirs()`, `os.listdir()`, `os.path.exists()` inside `async def`. Wrap them:

```python
def build_externals(
    agent_id: str, context: dict[str, Any]
) -> dict[str, Callable[..., Any]]:
    async def ensure_dir(path: str) -> None:
        await asyncio.to_thread(os.makedirs, path, exist_ok=True)

    async def write_file(path: str, content: str) -> None:
        def _write() -> None:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        await asyncio.to_thread(_write)

    async def read_file(path: str) -> str:
        def _read() -> str:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        return await asyncio.to_thread(_read)

    async def list_dir(path: str) -> list[str]:
        def _list() -> list[str]:
            try:
                return sorted(os.listdir(path))
            except FileNotFoundError:
                return []
        return await asyncio.to_thread(_list)

    async def file_exists(path: str) -> bool:
        return await asyncio.to_thread(os.path.exists, path)

    return {
        "ensure_dir": ensure_dir,
        "write_file": write_file,
        "read_file": read_file,
        "list_dir": list_dir,
        "file_exists": file_exists,
    }
```

**Step 2: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "fix(demo): use asyncio.to_thread for sync I/O in build_externals"
```

---

### Task 11: Update `bundle.yaml` for Structural Tag Mode

**Files:**
- Modify: `demo/agents/workspace_agent/bundle.yaml`

**Step 1: Read current bundle.yaml**

Check if `send_tools_to_api` is already set.

**Step 2: Ensure grammar section includes `send_tools_to_api: false` for structural_tag mode**

If the grammar section has `mode: "structural_tag"`, add `send_tools_to_api: false` if not already present. With structural_tag mode, the grammar constraint handles tool calling format — sending tools to vLLM can cause conflicts.

```yaml
grammar:
  mode: "structural_tag"
  allow_parallel_calls: true
  args_format: "permissive"
  send_tools_to_api: false
```

**Step 3: Commit**

```bash
git add demo/agents/workspace_agent/bundle.yaml
git commit -m "fix(demo): set send_tools_to_api=false for structural_tag mode in bundle"
```

---

## Part 3: Demo Feature Coverage Additions

### Task 12: Add Section 0 — Direct LLM Client Usage

**Demonstrates:** `build_client()`, `CompletionResponse`, `LLMClient` protocol, `KernelConfig`

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add import for `build_client` and `CompletionResponse`**

Add to the imports from `structured_agents`:
```python
from structured_agents.client.factory import build_client
from structured_agents.client.protocol import CompletionResponse
```

**Step 2: Add the section function**

Add before `section_1_bundle_loading`:

```python
async def section_0_direct_client(base_url: str, model: str) -> None:
    """Section 0: Direct LLM Client Usage (no kernel, no tools)."""
    print("\n" + "=" * 70)
    print("Section 0: Direct LLM Client Usage")
    print("=" * 70)

    config = KernelConfig(base_url=base_url, model=model)
    client = build_client(config)

    try:
        response: CompletionResponse = await client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Be concise."},
                {"role": "user", "content": "What is 2+2? Answer in one word."},
            ],
            max_tokens=32,
            temperature=0.0,
        )

        print(f"\n  CompletionResponse fields:")
        print(f"    content: {response.content}")
        print(f"    tool_calls: {response.tool_calls}")
        print(f"    finish_reason: {response.finish_reason}")
        print(f"    usage: {response.usage}")
        print(f"    raw_response keys: {list(response.raw_response.keys()) if response.raw_response else 'N/A'}")
    finally:
        await client.close()
```

**Step 3: Call it from `main()` as the first section**

Add before `await section_1_bundle_loading(AGENT_DIR)`:
```python
await section_0_direct_client(base_url, model="Qwen/Qwen3-4B-Instruct-2507-FP8")
```

Note: `base_url` is already defined from the pre-flight check in Task 7.

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "feat(demo): add Section 0 demonstrating direct LLM client usage"
```

---

### Task 13: Add PythonBackend + PythonRegistry Section

**Demonstrates:** `PythonBackend`, `PythonRegistry`, `RegistryBackendToolSource`, `ToolCall.create()`

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add imports**

```python
from structured_agents.backends.python import PythonBackend
from structured_agents.registries.python import PythonRegistry
```

Note: `PythonRegistry` is already imported in the test files but not in the demo. `PythonBackend` and `PythonRegistry` are both in `structured_agents.__init__`.

**Step 2: Add the section function**

Add after section 10 (registry discovery):

```python
async def section_12_python_backend() -> None:
    """Section 12: PythonBackend — Tools Without Grail."""
    print("\n" + "=" * 70)
    print("Section 12: PythonBackend — Tools Without Grail")
    print("=" * 70)

    # 1. Create a PythonRegistry and register tools
    registry = PythonRegistry()

    async def calculate(expression: str) -> str:
        """Evaluate a math expression."""
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    async def greet(name: str, greeting: str = "Hello") -> str:
        """Generate a greeting message."""
        return f"{greeting}, {name}!"

    registry.register("calculate", calculate)
    registry.register("greet", greet)

    print(f"\n  Registered tools: {registry.list_tools()}")

    # 2. Show auto-generated schemas
    for tool_name in registry.list_tools():
        schema = registry.resolve(tool_name)
        if schema:
            print(f"\n  --- {tool_name} ---")
            print(f"    Description: {schema.description}")
            print(f"    Parameters: {schema.parameters}")
            print(f"    Backend: {schema.backend}")

    # 3. Execute via PythonBackend
    backend = PythonBackend(registry=registry)
    tool_source = RegistryBackendToolSource(registry, backend)

    # Use ToolCall.create() for auto-generated IDs
    call = ToolCall.create(name="calculate", arguments={"expression": "6 * 7"})
    print(f"\n  ToolCall.create() -> id={call.id}, name={call.name}")

    schema = registry.resolve("calculate")
    result = await backend.execute(call, schema, context={})
    print(f"  Result: {result.output} (is_error={result.is_error})")

    # 4. Use with AgentKernel
    kernel = AgentKernel(
        config=KernelConfig(
            base_url="http://remora-server:8000/v1",
            model="Qwen/Qwen3-4B-Instruct-2507-FP8",
            temperature=0.0,
            max_tokens=256,
        ),
        plugin=QwenPlugin(),
        tool_source=tool_source,
        grammar_config=GrammarConfig(mode="structural_tag", send_tools_to_api=False),
    )

    step_result = await kernel.step(
        messages=[
            Message(role="system", content="You are a calculator. Use the calculate tool."),
            Message(role="user", content="What is 15 * 23?"),
        ],
        tools=[schema for name in registry.list_tools() if (schema := registry.resolve(name))],
    )

    print(f"\n  Kernel step with PythonBackend:")
    print(f"    Tool calls: {len(step_result.tool_calls)}")
    if step_result.tool_calls:
        tc = step_result.tool_calls[0]
        print(f"    First call: {tc.name}({tc.arguments})")
    if step_result.tool_results:
        print(f"    Result: {step_result.tool_results[0].output}")

    await kernel.close()
```

**Step 3: Call from `main()` after section 11**

```python
await section_12_python_backend()
```

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "feat(demo): add Section 12 demonstrating PythonBackend + PythonRegistry"
```

---

### Task 14: Add Exception Handling Section

**Demonstrates:** `KernelError`, `ToolExecutionError`, `StructuredAgentsError`, exception `phase` and `tool_name` attributes

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add imports**

```python
from structured_agents import KernelError, ToolExecutionError, StructuredAgentsError
```

**Step 2: Add the section function**

```python
async def section_13_exception_handling() -> None:
    """Section 13: Exception Handling with Library Exceptions."""
    print("\n" + "=" * 70)
    print("Section 13: Exception Handling")
    print("=" * 70)

    # 1. KernelError — connection failure
    print("\n  --- KernelError: Bad server URL ---")
    bad_kernel = AgentKernel(
        config=KernelConfig(
            base_url="http://localhost:1/v1",  # Non-existent server
            model="test",
            timeout=2.0,
        ),
        plugin=QwenPlugin(),
    )

    try:
        await bad_kernel.step(
            messages=[Message(role="user", content="hello")],
            tools=[],
        )
    except KernelError as e:
        print(f"    Caught KernelError: {e}")
        print(f"    Phase: {e.phase}")
        print(f"    Turn: {e.turn}")
    except StructuredAgentsError as e:
        print(f"    Caught StructuredAgentsError: {e}")
    finally:
        await bad_kernel.close()

    # 2. ToolExecutionError — show structure
    print("\n  --- ToolExecutionError: Manual construction ---")
    err = ToolExecutionError(
        message="File not found: /tmp/missing.txt",
        tool_name="read_file",
        call_id="call_abc123",
        code="FILE_NOT_FOUND",
    )
    print(f"    message: {err}")
    print(f"    tool_name: {err.tool_name}")
    print(f"    call_id: {err.call_id}")
    print(f"    code: {err.code}")

    # 3. Exception hierarchy
    print("\n  --- Exception Hierarchy ---")
    print(f"    KernelError is StructuredAgentsError: {issubclass(KernelError, StructuredAgentsError)}")
    print(f"    ToolExecutionError is StructuredAgentsError: {issubclass(ToolExecutionError, StructuredAgentsError)}")
    print(f"    StructuredAgentsError is Exception: {issubclass(StructuredAgentsError, Exception)}")
```

**Step 3: Call from `main()`**

```python
await section_13_exception_handling()
```

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "feat(demo): add Section 13 demonstrating exception handling patterns"
```

---

### Task 15: Add History Strategy Section

**Demonstrates:** `HistoryStrategy`, `SlidingWindowHistory`, `KeepAllHistory`

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add imports**

```python
from structured_agents.history import KeepAllHistory, SlidingWindowHistory
```

**Step 2: Add the section function**

```python
async def section_14_history_strategies() -> None:
    """Section 14: History Management Strategies."""
    print("\n" + "=" * 70)
    print("Section 14: History Management Strategies")
    print("=" * 70)

    # Build a sample conversation history
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Turn 1: Hello"),
        Message(role="assistant", content="Turn 1: Hi there!"),
        Message(role="user", content="Turn 2: What's the weather?"),
        Message(role="assistant", content="Turn 2: I don't know."),
        Message(role="user", content="Turn 3: Tell me a joke"),
        Message(role="assistant", content="Turn 3: Why did the chicken..."),
        Message(role="user", content="Turn 4: Another one"),
        Message(role="assistant", content="Turn 4: A horse walks into a bar..."),
    ]

    print(f"\n  Total messages: {len(messages)}")
    print(f"  First message role: {messages[0].role}")

    # 1. SlidingWindowHistory (default)
    sliding = SlidingWindowHistory()
    trimmed = sliding.trim(messages, max_messages=5)
    print(f"\n  --- SlidingWindowHistory (max_messages=5) ---")
    print(f"    Input: {len(messages)} messages")
    print(f"    Output: {len(trimmed)} messages")
    print(f"    Kept system prompt: {trimmed[0].role == 'system'}")
    print(f"    Messages kept:")
    for m in trimmed:
        preview = m.content[:40] if m.content else "N/A"
        print(f"      [{m.role}] {preview}")

    # 2. KeepAllHistory
    keep_all = KeepAllHistory()
    trimmed_all = keep_all.trim(messages, max_messages=5)
    print(f"\n  --- KeepAllHistory (max_messages=5, ignored) ---")
    print(f"    Input: {len(messages)} messages")
    print(f"    Output: {len(trimmed_all)} messages")
    print(f"    Note: KeepAllHistory ignores max_messages, keeps everything")
```

**Step 3: Call from `main()`**

```python
await section_14_history_strategies()
```

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "feat(demo): add Section 14 demonstrating history management strategies"
```

---

### Task 16: Add CompositeBackend Section

**Demonstrates:** `CompositeBackend`, `CompositeRegistry`, combining Grail + Python backends

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Add imports**

```python
from structured_agents.backends.composite import CompositeBackend
from structured_agents.registries.composite import CompositeRegistry
```

**Step 2: Add the section function**

```python
async def section_15_composite_backend(bundle_dir: Path) -> None:
    """Section 15: CompositeBackend — Combining Multiple Backends."""
    print("\n" + "=" * 70)
    print("Section 15: CompositeBackend — Combining Backends")
    print("=" * 70)

    # 1. Set up Grail backend (from bundle)
    grail_registry_config = GrailRegistryConfig(
        agents_dir=bundle_dir, use_grail_check=False
    )
    grail_registry = GrailRegistry(grail_registry_config)
    grail_backend_config = GrailBackendConfig(grail_dir=bundle_dir)
    grail_backend = GrailBackend(
        grail_backend_config, externals_factory=build_externals
    )

    # 2. Set up Python backend with extra tools
    python_registry = PythonRegistry()

    async def current_time() -> str:
        """Get the current UTC time."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    python_registry.register("current_time", current_time)

    python_backend = PythonBackend(registry=python_registry)

    # 3. Combine with CompositeRegistry + CompositeBackend
    composite_registry = CompositeRegistry([grail_registry, python_registry])
    composite_backend = CompositeBackend()
    composite_backend.register("grail", grail_backend)
    composite_backend.register("python", python_backend)

    # 4. Show combined tool list
    all_tools = composite_registry.list_tools()
    print(f"\n  Combined tools from Grail + Python: {all_tools}")

    for tool_name in all_tools:
        schema = composite_registry.resolve(tool_name)
        if schema:
            print(f"    {tool_name} -> backend={schema.backend}")

    # 5. Execute a Python tool through the composite
    tool_source = RegistryBackendToolSource(composite_registry, composite_backend)
    call = ToolCall.create(name="current_time", arguments={})
    schema = composite_registry.resolve("current_time")
    result = await composite_backend.execute(call, schema, context={})
    print(f"\n  Execute 'current_time' via CompositeBackend:")
    print(f"    Result: {result.output}")

    grail_backend.shutdown()
```

**Step 3: Call from `main()`**

```python
await section_15_composite_backend(AGENT_DIR)
```

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "feat(demo): add Section 15 demonstrating CompositeBackend with mixed Grail + Python tools"
```

---

### Task 17: Update Imports to Use Public API

**Files:**
- Modify: `demo/workspace_agent_demo.py`

**Step 1: Check which imports can use the public API**

Current internal imports:
```python
from structured_agents.bundles import load_bundle                    # in __init__
from structured_agents.bundles.loader import AgentBundle             # in __init__
from structured_agents.grammar.config import GrammarConfig           # in __init__
from structured_agents.observer import CompositeObserver, ...        # in __init__
from structured_agents.registries.grail import GrailRegistry, GrailRegistryConfig  # NOT in __init__
from structured_agents.backends.grail import GrailBackend, GrailBackendConfig      # NOT in __init__
from structured_agents.tool_sources.registry_backend import RegistryBackendToolSource  # in __init__
from structured_agents.plugins.qwen import QwenPlugin                # in __init__
from structured_agents.plugins.registry import PluginRegistry, get_plugin  # NOT in __init__
```

Symbols that ARE in `structured_agents.__init__` and can be imported from the top-level:
- `load_bundle`, `AgentBundle`
- `GrammarConfig`
- All observer types
- `RegistryBackendToolSource`
- `QwenPlugin`
- `PythonBackend`, `PythonRegistry`
- `CompositeBackend`
- `build_client`, `CompletionResponse`, `LLMClient`
- `KernelError`, `ToolExecutionError`, `StructuredAgentsError`
- `KeepAllHistory`, `SlidingWindowHistory`

Symbols NOT in `__init__` (keep internal imports):
- `GrailRegistry`, `GrailRegistryConfig`
- `GrailBackend`, `GrailBackendConfig`
- `PluginRegistry`, `get_plugin`
- `CompositeRegistry`

**Step 2: Consolidate public API imports**

Replace the current import block with:

```python
from structured_agents import (
    AgentKernel,
    KernelConfig,
    Message,
    ToolCall,
    ToolExecutionStrategy,
    ToolResult,
    QwenPlugin,
    GrammarConfig,
    PythonBackend,
    PythonRegistry,
    CompositeBackend,
    RegistryBackendToolSource,
    KeepAllHistory,
    SlidingWindowHistory,
    KernelError,
    ToolExecutionError,
    StructuredAgentsError,
    load_bundle,
    AgentBundle,
    build_client,
    CompletionResponse,
    NullObserver,
    CompositeObserver,
    KernelStartEvent,
    KernelEndEvent,
    ModelRequestEvent,
    ModelResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnCompleteEvent,
)

# Internal imports — not in public API
from structured_agents.registries.grail import GrailRegistry, GrailRegistryConfig
from structured_agents.backends.grail import GrailBackend, GrailBackendConfig
from structured_agents.plugins.registry import PluginRegistry
from structured_agents.registries.composite import CompositeRegistry
```

**Step 3: Verify imports work**

Run: `uv run python -c "from demo.workspace_agent_demo import *"` (or just import the module)
Expected: No ImportError

**Step 4: Commit**

```bash
git add demo/workspace_agent_demo.py
git commit -m "refactor(demo): use public structured_agents API for imports where possible"
```

---

## Part 4: Final Validation

### Task 18: Run Full Test Suite

**Step 1:** Run: `uv run pytest tests/ -v`
Expected: 0 failures

### Task 19: Verify Demo Loads Without Import Errors

**Step 1:** Run: `uv run python -c "import demo.workspace_agent_demo; print('OK')"`
Expected: `OK`

### Task 20: Verify Demo Runs (if vLLM available)

**Step 1:** Run: `uv run demo/workspace_agent_demo.py`
Expected: All sections execute or gracefully report vLLM unavailability via pre-flight check

---

## Files Modified Summary

| File | Tasks | Changes |
|------|-------|---------|
| `tests/test_grammar/test_artifacts.py` | 1 | Remove `"type"` key assertions |
| `tests/test_grammar/test_function_gemma_builder.py` | 2 | Remove `"type"` key assertion |
| `tests/test_grammar/test_qwen3_builder.py` | 3 | Remove `"type"` key assertion |
| `tests/test_plugins/test_function_gemma.py` | 4 | Remove `"type"` key assertion |
| `demo/workspace_agent_demo.py` | 6-17 | Pre-flight check, observer reset, state cleanup, async I/O, 4 new sections, import cleanup |
| `demo/agents/workspace_agent/bundle.yaml` | 11 | Add `send_tools_to_api: false` |
