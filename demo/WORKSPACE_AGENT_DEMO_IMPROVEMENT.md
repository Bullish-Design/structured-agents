# Workspace Agent Demo: Comprehensive Improvement Report

## Purpose

This report audits the current `workspace_agent_demo.py` against the full capabilities of the `structured-agents` library, identifies gaps, and provides a detailed step-by-step enhancement plan to transform the demo into a gold-standard reference implementation.

---

## Part 1: Full Capability Inventory of `structured-agents`

The following is the complete set of capabilities provided by the library. Each capability is grounded in the source code with file paths and line references.

### 1.1 AgentKernel — Orchestration Loop

**Source:** `src/structured_agents/kernel.py:46-423`

The `AgentKernel` is the central orchestration primitive. It provides:

- **`step()`** (line 108): Single-turn execution — format messages via plugin, build grammar, call LLM, parse response, execute tools (sequential or concurrent), emit observer events.
- **`run()`** (line 289): Multi-turn agentic loop — iterates `step()` up to `max_turns`, manages history trimming, accumulates token usage, checks termination conditions, returns `RunResult`.
- **Termination conditions** (line 42): `TerminationCondition = Callable[[ToolResult], bool]` — the loop stops when a tool result satisfies the condition (e.g., a `submit_result` tool).
- **Context providers** (line 97): Per-turn context injection via `ContextProvider` callbacks merged into tool execution context.
- **Model override per turn** (line 333): The context dict can contain `"model_override"` to switch models mid-run.
- **History trimming** (line 340): Automatic conversation window management via `HistoryStrategy`.
- **Token usage accumulation** (line 352): Tracks cumulative `TokenUsage` across all turns.

### 1.2 Model Plugin System

**Source:** `src/structured_agents/plugins/`

Protocol-driven, swappable model formatting/parsing:

- **`ModelPlugin` protocol** (`protocol.py:12`): `format_messages()`, `format_tools()`, `build_grammar()`, `to_extra_body()`, `parse_response()`.
- **`QwenPlugin`** (`qwen.py:15`): Qwen3-family support with XML parameter format (`<function=name><parameter=key>value</parameter></function>`).
- **`FunctionGemmaPlugin`** (`function_gemma.py:14`): FunctionGemma-family support with `<start_function_call>call:name{args}<end_function_call>` format.
- **`PluginRegistry`** (`registry.py:10`): Dynamic plugin registration/lookup by name string.
- **Component model** (`components.py`): Each plugin is composed from four independent protocols — `MessageFormatter`, `ToolFormatter`, `ResponseParser`, `GrammarProvider` — assembled via `ComposedModelPlugin`.

### 1.3 Grammar-Constrained Decoding

**Source:** `src/structured_agents/grammar/`

Three grammar modes, each producing a `GrammarArtifact` sent to vLLM via `extra_body.structured_outputs`:

| Mode | Artifact | vLLM Payload | Plugin Support |
|------|----------|-------------|----------------|
| `ebnf` | `EBNFGrammar` (`artifacts.py:11`) | `{"type": "grammar", "grammar": "..."}` | Qwen, FunctionGemma |
| `structural_tag` | `StructuralTagGrammar` (`artifacts.py:26`) | `{"type": "structural_tag", "structural_tag": {...}}` | Qwen, FunctionGemma |
| `json_schema` | `JsonSchemaGrammar` (`artifacts.py:41`) | `{"type": "json", "json": {"json_schema": {...}}}` | Qwen only |

**`GrammarConfig`** (`config.py:7`): Controls `mode`, `allow_parallel_calls`, `args_format` (`permissive`/`escaped_strings`/`json`), `send_tools_to_api`.

**Builders:**
- `Qwen3GrammarBuilder` (`builders/qwen3.py:25`): Supports all three modes.
- `FunctionGemmaGrammarBuilder` (`builders/function_gemma.py:16`): Supports `ebnf` and `structural_tag`.
- `FunctionGemmaSchemaGrammarBuilder` (`builders/schema_aware_function_gemma.py:12`): Schema-aware EBNF with recursive JSON schema to EBNF rule generation.

### 1.4 Tool Execution

**Source:** `src/structured_agents/backends/`, `src/structured_agents/tool_sources/`

**Backends:**
- **`GrailBackend`** (`backends/grail.py:39`): Executes `.pym` scripts in isolated processes via `ProcessPoolExecutor`. Supports `externals_factory`, resource limits, context providers.
- **`PythonBackend`** (`backends/python.py:14`): Executes Python callables directly. Supports sync and async handlers.
- **`CompositeBackend`** (`backends/composite.py:10`): Routes to sub-backends based on `tool_schema.backend` string.

**Tool sources:**
- **`RegistryBackendToolSource`** (`tool_sources/registry_backend.py:11`): Unifies a `ToolRegistry` (discovery) with a `ToolBackend` (execution) into a single `ToolSource`.

**Registries:**
- **`GrailRegistry`** (`registries/grail.py:23`): Auto-discovers `.pym` files, reads `.grail/*/inputs.json` for schemas.
- **`PythonRegistry`** (`registries/python.py:19`): Registers Python callables with auto-generated schemas from type hints.
- **`CompositeRegistry`** (`registries/composite.py:7`): Combines multiple registries.

**Execution strategies** (`types.py:18`):
- `ToolExecutionStrategy`: `mode` = `"concurrent"` or `"sequential"`, `max_concurrency` (default 10).
- The kernel uses `asyncio.Semaphore` for concurrent execution with configurable concurrency limits.

### 1.5 Observer / Event System

**Source:** `src/structured_agents/observer/`

Full lifecycle event hooks:

| Event | Fields |
|-------|--------|
| `KernelStartEvent` | `max_turns`, `tools_count`, `initial_messages_count` |
| `ModelRequestEvent` | `turn`, `messages_count`, `tools_count`, `model` |
| `ModelResponseEvent` | `turn`, `duration_ms`, `content`, `tool_calls_count`, `usage` |
| `ToolCallEvent` | `turn`, `tool_name`, `call_id`, `arguments` |
| `ToolResultEvent` | `turn`, `tool_name`, `call_id`, `is_error`, `duration_ms`, `output_preview` |
| `TurnCompleteEvent` | `turn`, `tool_calls_count`, `tool_results_count`, `errors_count` |
| `KernelEndEvent` | `turn_count`, `termination_reason`, `total_duration_ms` |

**Implementations:**
- `NullObserver` (`null.py`): No-op default.
- `CompositeObserver` (`composite.py`): Fan-out to multiple observers with exception isolation.

### 1.6 Bundle System

**Source:** `src/structured_agents/bundles/`

YAML-driven, self-contained agent packaging:

- **`BundleManifest`** (`schema.py:53`): Pydantic model with `name`, `version`, `model` (plugin, grammar settings), `initial_context` (system_prompt, user_template with Jinja2), `max_turns`, `termination_tool`, `tools`, `registries`.
- **`AgentBundle`** (`loader.py:29`): Loaded bundle providing `get_plugin()`, `get_grammar_config()`, `build_tool_source(backend)`, `build_initial_messages(context)`.
- **`load_bundle(directory)`** (`loader.py:194`): Reads `bundle.yaml`, validates, returns `AgentBundle`.
- **Tool overrides**: Bundle tools can override `description` and `inputs_override` from their registry-discovered schemas.
- **Context providers per tool**: `ToolReference.context_providers` specifies `.pym` scripts that run before the tool.

### 1.7 Conversation History Management

**Source:** `src/structured_agents/history.py`

- **`SlidingWindowHistory`** (line 30): Preserves system prompt + N most recent messages.
- **`KeepAllHistory`** (line 52): No trimming.
- **`HistoryStrategy` protocol** (line 10): Extensible for custom strategies.

### 1.8 Data Types

**Source:** `src/structured_agents/types.py`

| Type | Purpose |
|------|---------|
| `Message` | Immutable conversation message with `to_openai_format()` |
| `ToolCall` | Parsed tool call with `create()` classmethod |
| `ToolResult` | Execution result with `to_message()` for history injection |
| `ToolSchema` | Tool definition with `to_openai_format()`, `script_path`, `context_providers` |
| `TokenUsage` | Token statistics |
| `StepResult` | Single-turn result bundle |
| `RunResult` | Full-run result with `final_message`, `history`, `turn_count`, `termination_reason`, `total_usage` |
| `KernelConfig` | Top-level configuration including `tool_execution_strategy` |

### 1.9 Error Handling

**Source:** `src/structured_agents/exceptions.py`

Structured exception hierarchy: `StructuredAgentsError` > `KernelError` (with `turn`, `phase`), `ToolExecutionError` (with `tool_name`, `call_id`, `code`), `PluginError`, `BundleError`, `BackendError`.

### 1.10 Grail Integration Capabilities

**Source:** `.context/grail/`

- **Monty sandbox**: <1us startup, complete isolation, resource limits, deterministic execution.
- **Externals**: Host-defined async functions injected into scripts at runtime.
- **Inputs**: Typed, validated parameters with required/optional/default support.
- **Artifact system**: `.grail/` directory with `stubs.pyi`, `check.json`, `inputs.json`, `monty_code.py`, `run.log`.
- **Snapshot/pause-resume**: Serialize execution state at external function boundaries.
- **Output validation**: Optional Pydantic `output_model` for structured result validation.

### 1.11 vLLM Integration Capabilities

**Source:** `.context/vllm/vllm-0.15.1/`

- **Batched inference**: Continuous batching via scheduler, `max_num_seqs=128` concurrent sequences. Requests processed concurrently with automatic batch formation.
- **Structured outputs**: 6 constraint types (`json`, `regex`, `choice`, `grammar`, `json_object`, `structural_tag`), 4 backends (`xgrammar`, `guidance`, `outlines`, `lm-format-enforcer`).
- **Tool calling**: `tool_choice` modes (`none`/`auto`/`required`/named), 30+ model-specific parsers.
- **Async API**: `AsyncLLM` engine with `AsyncGenerator` responses.

### 1.12 xgrammar Integration

**Source:** `.context/xgrammar-0.1.29/`

- **Token masking**: Compressed bitmask over vocabulary, Triton CUDA kernel for GPU-accelerated application.
- **Structural tags**: Composable `TagFormat`, `OrFormat`, `SequenceFormat`, `GrammarFormat`, `ConstStringFormat`, `SchemaFormat` — JSON-config DSL for complex output formats.
- **Grammar composition**: `Grammar.concat()` and `Grammar.union()` for combining grammars.
- **Batch processing**: `BatchGrammarMatcher` for parallel multi-threaded batch masking.

---

## Part 2: Current Demo Audit

### What the demo currently does

The `workspace_agent_demo.py` (286 lines) implements a `WorkspaceAgent` class that:

1. **Connects to vLLM** via `build_client()` with `KernelConfig` targeting Qwen3.
2. **Uses QwenPlugin** for message formatting, tool formatting, grammar building, and response parsing.
3. **Uses GrailBackend** with `externals_factory` to execute `.pym` tool scripts.
4. **Defines 5 tool schemas** manually (add_entry, update_entry, list_entries, summarize_state, format_summary).
5. **Sends natural language queries** to the model with `structural_tag` grammar constraints.
6. **Parses model tool calls** and executes them via GrailBackend.
7. **Handles nested tool calls** — `summarize_state` returns a `nested_tool_call` dict that triggers `format_summary`.
8. **Maintains inbox/outbox** lists (though the main loop uses `send_to_model()` rather than `process_message()`).
9. **Manages workspace state** via plain text files in `state/` directory.

### Capability coverage matrix

| # | Capability | Status | Details |
|---|-----------|--------|---------|
| 1 | AgentKernel orchestration loop | **NOT USED** | Demo manually calls `client.chat_completion()` instead of using `AgentKernel.step()` or `.run()`. This is the single biggest gap. |
| 2 | Multi-turn conversations | **NOT DEMONSTRATED** | Each query is independent. Tool results are not fed back to the model for follow-up reasoning. No conversation history across turns. |
| 3 | Observer/event system | **NOT DEMONSTRATED** | No observer is attached. No lifecycle events are logged or displayed. |
| 4 | Grammar modes | **PARTIAL** | Only `structural_tag` mode is shown. `ebnf` and `json_schema` modes are not demonstrated. |
| 5 | Concurrent tool execution | **NOT DEMONSTRATED** | `ToolExecutionStrategy` is not configured. Only sequential, single tool call execution occurs. |
| 6 | Context providers | **NOT DEMONSTRATED** | No `.pym` context provider scripts exist. No tool uses `context_providers` field. |
| 7 | Bundle system | **NOT DEMONSTRATED** | No `bundle.yaml` exists for the workspace agent. Tool schemas are manually constructed. |
| 8 | Swappable model plugins | **NOT DEMONSTRATED** | Only `QwenPlugin` is used. Plugin swapping/registry is not shown. |
| 9 | Token usage tracking | **NOT CAPTURED** | `TokenUsage` from `CompletionResponse.usage` is discarded. `StepResult.usage` and `RunResult.total_usage` are not used. |
| 10 | Batched inference / async throughput | **NOT DEMONSTRATED** | Queries are processed sequentially. vLLM's batched inference advantage (processing multiple concurrent requests efficiently) is not shown. |
| 11 | Error handling patterns | **MINIMAL** | No structured error handling. No `try/except` around tool execution. Tool errors are not gracefully reported. |
| 12 | Message history management | **NOT DEMONSTRATED** | No `HistoryStrategy` is used. No `SlidingWindowHistory` or `KeepAllHistory`. |
| 13 | GrailRegistry auto-discovery | **NOT DEMONSTRATED** | Tool schemas are manually defined. `GrailRegistry` auto-scanning from `inputs.json` is not used. |
| 14 | RegistryBackendToolSource | **NOT DEMONSTRATED** | No unified `ToolSource` is constructed. Backend and registry are not composed. |
| 15 | PythonBackend / CompositeBackend | **NOT DEMONSTRATED** | Only `GrailBackend` is used directly. No hybrid tool sources. |
| 16 | Termination conditions | **NOT DEMONSTRATED** | No termination tool pattern (e.g., `submit_result`). |
| 17 | Jinja2 prompt templating | **NOT DEMONSTRATED** | System prompt is hardcoded. No template rendering. |
| 18 | ToolCall.create() factory | **NOT USED** | Manual `ToolCall` construction with hardcoded IDs. |
| 19 | RunResult inspection | **NOT DEMONSTRATED** | No demonstration of `RunResult.turn_count`, `termination_reason`, `total_usage`, `history`. |
| 20 | Parallel tool calls (model-generated) | **NOT DEMONSTRATED** | Only first tool call is executed (line 239: `tool_call = tool_calls[0]`). |

### Architectural issues in current demo

1. **Bypasses the kernel entirely**: The demo reimplements a subset of `AgentKernel.step()` manually — message formatting, LLM call, response parsing, tool execution. This is the exact pattern the kernel was designed to eliminate.

2. **Manual nested tool call handling**: The `execute_tool()` method checks for `nested_tool_call` in parsed output and recursively calls itself. The kernel's multi-turn loop handles this pattern natively — a tool result is fed back as a message, and the model decides whether to call another tool.

3. **No `ToolSource` composition**: The demo creates a `GrailBackend` directly and calls `backend.execute()`, bypassing the `ToolSource` abstraction that unifies discovery and execution.

4. **Inbox/outbox is vestigial**: `process_message()` exists but is never called in `main()`. The main loop uses `send_to_model()` which doesn't use inbox/outbox at all.

5. **State_dir injection is fragile**: Every tool schema includes `state_dir` as a parameter, and `execute_tool()` injects it at runtime. This should use context providers or the kernel's context mechanism instead.

---

## Part 3: Step-by-Step Enhancement Plan

### Overview

The enhancement transforms the demo from a manual LLM-call wrapper into a proper `AgentKernel`-driven system that demonstrates the full library. The workspace agent scenario remains the same (task management with inbox/outbox), but the implementation shifts to library best practices.

The demo will be restructured into sections, each demonstrating a specific capability, culminating in a fully-integrated run.

---

### Step 1: Create a `bundle.yaml` for the Workspace Agent

**Goal:** Replace manual `ToolSchema` construction with the bundle system.

**What to create:** `demo/agents/workspace_agent/bundle.yaml`

```yaml
name: "workspace_agent"
version: "1.0"
model:
  plugin: "qwen"
  grammar:
    mode: "structural_tag"
    allow_parallel_calls: true
    args_format: "permissive"
initial_context:
  system_prompt: |
    You are a workspace management assistant. You manage tasks with priorities
    and statuses. Use the provided tools to fulfill user requests.
    Always use tools when the user asks to create, update, list, or summarize tasks.
  user_template: "{{ input }}"
max_turns: 10
termination_tool: "submit_result"
tools:
  - name: "add_entry"
    registry: "grail"
    description: "Add or replace a workspace entry (task) with name, status, priority, and note."
  - name: "update_entry"
    registry: "grail"
    description: "Update an existing workspace entry's status, priority, or note."
  - name: "list_entries"
    registry: "grail"
    description: "List workspace entries, optionally filtered by priority."
  - name: "summarize_state"
    registry: "grail"
    description: "Summarize all workspace entries and format the summary."
  - name: "format_summary"
    registry: "grail"
    description: "Format a raw summary string into a styled output."
  - name: "submit_result"
    registry: "grail"
    description: "Submit a final result to end the conversation."
registries:
  - type: "grail"
    config:
      agents_dir: "."
```

**What else to create:** A `submit_result.pym` tool that acts as the termination signal:

```python
from grail import Input

result: str = Input("result", description="The final result to submit")

{"submitted": result}
```

**Why this matters:** The bundle system is the recommended packaging mechanism. It provides:
- Declarative configuration (no Python code for schema wiring)
- Jinja2 prompt templating
- Automatic tool resolution via registries
- Grammar configuration co-located with agent definition
- Portability and reproducibility

---

### Step 2: Create a Context Provider for `state_dir` Injection

**Goal:** Replace the fragile `state_dir` injection in `execute_tool()` with a proper context provider.

**What to create:** `demo/agents/workspace_agent/workspace_context.pym`

```python
from grail import Input

workspace_path: str = Input("workspace_path", default="")

{"state_dir": workspace_path}
```

**What to modify:** Update the tool schemas (or bundle tools) to reference this context provider:

```yaml
tools:
  - name: "add_entry"
    registry: "grail"
    context_providers:
      - "workspace_context.pym"
```

**What to modify in `.pym` scripts:** Remove `state_dir` from `Input()` declarations. Instead, the context provider's output is prepended to the tool result by `GrailBackend`, and the `state_dir` value flows through the execution context.

**Alternative approach:** Since `GrailBackend.execute()` merges context into inputs when `agent_id` is present (`grail.py:240`), a simpler approach is to pass `state_dir` via the kernel's `context_provider`:

```python
async def provide_workspace_context() -> dict[str, Any]:
    return {"state_dir": str(STATE_DIR), "agent_id": AGENT_ID}
```

This is cleaner and avoids modifying the `.pym` scripts. The kernel's `run()` method accepts `context_provider` and calls it every turn.

---

### Step 3: Build a `RegistryBackendToolSource`

**Goal:** Replace direct `GrailBackend.execute()` calls with a proper `ToolSource`.

**Current pattern (anti-pattern):**
```python
backend = GrailBackend(config, externals_factory=build_externals)
result = await backend.execute(tool_call, schema, {"agent_id": AGENT_ID})
```

**Target pattern (best practice):**
```python
from structured_agents import RegistryBackendToolSource, GrailRegistry

registry = GrailRegistry(GrailRegistryConfig(agents_dir=AGENT_DIR))
backend = GrailBackend(GrailBackendConfig(grail_dir=AGENT_DIR), externals_factory=build_externals)
tool_source = RegistryBackendToolSource(registry=registry, backend=backend)
```

Or, even better, use the bundle:

```python
bundle = load_bundle(AGENT_DIR)
tool_source = bundle.build_tool_source(backend)
```

**Why this matters:** `ToolSource` unifies schema discovery and execution. The kernel requires a `ToolSource` — it cannot work with a bare backend.

---

### Step 4: Implement a `LoggingObserver`

**Goal:** Create and attach an observer that logs all kernel lifecycle events to the console, demonstrating the event system.

**What to create:** A `DemoObserver` class within the demo script:

```python
from structured_agents import (
    Observer, KernelStartEvent, KernelEndEvent,
    ModelRequestEvent, ModelResponseEvent,
    ToolCallEvent, ToolResultEvent, TurnCompleteEvent,
)

class DemoObserver:
    """Observer that logs all kernel events for demo visibility."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def on_kernel_start(self, event: KernelStartEvent) -> None:
        print(f"  [KERNEL] Starting: {event.tools_count} tools, max {event.max_turns} turns")
        self.events.append({"type": "kernel_start", "event": event})

    async def on_model_request(self, event: ModelRequestEvent) -> None:
        print(f"  [MODEL REQUEST] Turn {event.turn}: {event.messages_count} messages, {event.tools_count} tools")
        self.events.append({"type": "model_request", "event": event})

    async def on_model_response(self, event: ModelResponseEvent) -> None:
        usage_str = ""
        if event.usage:
            usage_str = f" | tokens: {event.usage.prompt_tokens}p/{event.usage.completion_tokens}c"
        print(f"  [MODEL RESPONSE] Turn {event.turn}: {event.duration_ms}ms, {event.tool_calls_count} tool calls{usage_str}")
        self.events.append({"type": "model_response", "event": event})

    async def on_tool_call(self, event: ToolCallEvent) -> None:
        print(f"  [TOOL CALL] Turn {event.turn}: {event.tool_name}({event.arguments})")
        self.events.append({"type": "tool_call", "event": event})

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        status = "ERROR" if event.is_error else "OK"
        print(f"  [TOOL RESULT] Turn {event.turn}: {event.tool_name} [{status}] {event.duration_ms}ms")
        self.events.append({"type": "tool_result", "event": event})

    async def on_turn_complete(self, event: TurnCompleteEvent) -> None:
        print(f"  [TURN {event.turn} COMPLETE] {event.tool_calls_count} calls, {event.errors_count} errors")
        self.events.append({"type": "turn_complete", "event": event})

    async def on_kernel_end(self, event: KernelEndEvent) -> None:
        print(f"  [KERNEL] Ended: {event.turn_count} turns, reason={event.termination_reason}, {event.total_duration_ms}ms")
        self.events.append({"type": "kernel_end", "event": event})

    async def on_error(self, error: Exception, context: str) -> None:
        print(f"  [ERROR] {context}: {error}")
        self.events.append({"type": "error", "error": str(error), "context": context})
```

**Why this matters:** The observer pattern is a core library feature. Showing event flow gives users visibility into the kernel's internal operations and serves as a template for building monitoring, metrics, and debugging tools.

---

### Step 5: Rewrite `WorkspaceAgent` to Use `AgentKernel`

**Goal:** Replace manual LLM calling with `AgentKernel.step()` and `AgentKernel.run()`.

This is the most impactful change. The current `send_to_model()` method manually reimplements what the kernel does. The rewrite should:

```python
class WorkspaceAgent:
    def __init__(self, bundle_dir: Path) -> None:
        self.bundle = load_bundle(bundle_dir)
        self.backend = GrailBackend(
            GrailBackendConfig(grail_dir=bundle_dir),
            externals_factory=build_externals,
        )
        self.tool_source = self.bundle.build_tool_source(self.backend)
        self.observer = DemoObserver()
        self.kernel = AgentKernel(
            config=KernelConfig(
                base_url="http://remora-server:8000/v1",
                model="Qwen/Qwen3-4B-Instruct-2507-FP8",
                temperature=0.0,
                max_tokens=512,
                tool_execution_strategy=ToolExecutionStrategy(mode="concurrent"),
            ),
            plugin=self.bundle.get_plugin(),
            tool_source=self.tool_source,
            observer=self.observer,
            grammar_config=self.bundle.get_grammar_config(),
        )
        self.inbox: list[dict[str, Any]] = []
        self.outbox: list[dict[str, Any]] = []

    async def process_message(self, user_input: str) -> RunResult:
        """Process a natural language message through the full agent loop."""
        self.inbox.append({"text": user_input, "timestamp": time.time()})

        messages = self.bundle.build_initial_messages({"input": user_input})

        result = await self.kernel.run(
            initial_messages=messages,
            tools=self.bundle.tool_schemas,
            max_turns=5,
            termination=lambda r: r.name == "submit_result",
            context_provider=self._provide_context,
        )

        self.outbox.append({
            "input": user_input,
            "final_message": result.final_message.content,
            "turns": result.turn_count,
            "termination_reason": result.termination_reason,
            "total_usage": result.total_usage,
        })

        return result

    async def _provide_context(self) -> dict[str, Any]:
        return {"state_dir": str(STATE_DIR), "agent_id": AGENT_ID}

    async def close(self) -> None:
        await self.kernel.close()
        self.backend.shutdown()
```

**Key changes:**
- `AgentKernel.run()` handles the multi-turn loop, history, token tracking, and termination.
- The observer logs every event automatically.
- Context is injected via `context_provider` per turn.
- Tool schemas come from the bundle.
- Results are captured in the outbox with full metadata.
- Nested tool calls are handled naturally by the multi-turn loop (the model sees the first tool result and decides whether to call another tool).

---

### Step 6: Demonstrate Multi-Turn Conversations

**Goal:** Show the model receiving tool results and reasoning about them across multiple turns.

**Scenario:**
```
User: "Add a task 'Review Q3 metrics' with high priority, then list all tasks and summarize them."
```

With `AgentKernel.run()` and `max_turns=5`:
1. **Turn 1:** Model calls `add_entry` with name="Review Q3 metrics", priority="high".
2. **Turn 2:** Model sees the add result, calls `list_entries`.
3. **Turn 3:** Model sees the list, calls `summarize_state`.
4. **Turn 4:** Model sees the summary and calls `submit_result` with the final answer.

The demo should print each turn's events via the observer, showing the natural multi-turn flow.

**Why this matters:** Multi-turn tool calling is the core value proposition of `AgentKernel`. The current demo's single-shot pattern doesn't demonstrate this.

---

### Step 7: Demonstrate All Three Grammar Modes

**Goal:** Show `ebnf`, `structural_tag`, and `json_schema` grammar modes side-by-side.

**Implementation:** Run the same query with three different `GrammarConfig` settings:

```python
async def demo_grammar_modes(agent_dir: Path) -> None:
    """Demonstrate all three grammar constraint modes."""
    modes = [
        ("ebnf", GrammarConfig(mode="ebnf", send_tools_to_api=False)),
        ("structural_tag", GrammarConfig(mode="structural_tag")),
        ("json_schema", GrammarConfig(mode="json_schema")),
    ]
    for mode_name, grammar_config in modes:
        print(f"\n--- Grammar mode: {mode_name} ---")
        kernel = AgentKernel(
            config=config,
            plugin=QwenPlugin(),
            tool_source=tool_source,
            grammar_config=grammar_config,
        )
        result = await kernel.step(
            messages=[
                Message(role="developer", content="You are a task manager."),
                Message(role="user", content="Add a task 'Test grammar' with low priority"),
            ],
            tools=tool_source.list_tools(),
        )
        print(f"  Tool calls: {[(tc.name, tc.arguments) for tc in result.tool_calls]}")
        await kernel.close()
```

**Important note on `ebnf` mode:** When using EBNF grammar, `send_tools_to_api` must be `False` to prevent vLLM from overriding the grammar with its own tool-call constrained decoding. This is documented in `GrammarConfig` (`config.py:7`).

---

### Step 8: Demonstrate Concurrent Tool Execution

**Goal:** Show `ToolExecutionStrategy(mode="concurrent")` processing multiple tool calls in parallel.

**Scenario:** Ask the model to perform multiple operations simultaneously:

```
User: "Add three tasks at once: 'Design review' (high), 'Code cleanup' (low), 'Write tests' (medium)"
```

With parallel calls enabled in grammar config (`allow_parallel_calls=True`) and concurrent execution strategy, the model can emit multiple `<function=add_entry>` calls in a single response, and the kernel executes them concurrently via `asyncio.gather()` with a `Semaphore`.

**Configuration:**
```python
config = KernelConfig(
    ...,
    tool_execution_strategy=ToolExecutionStrategy(mode="concurrent", max_concurrency=3),
)
grammar_config = GrammarConfig(mode="structural_tag", allow_parallel_calls=True)
```

**Why this matters:** This demonstrates vLLM's batched inference advantage — multiple tool executions happen concurrently, and the observer events show the parallel execution timing.

---

### Step 9: Demonstrate Batched Async Inference

**Goal:** Show vLLM's batched inference processing by sending multiple independent agent queries concurrently.

**Implementation:** Use `asyncio.gather()` to process multiple workspace messages simultaneously:

```python
async def demo_batched_inference(agent: WorkspaceAgent) -> None:
    """Send multiple queries concurrently to leverage vLLM batching."""
    queries = [
        "Add task 'API redesign' with high priority",
        "Add task 'Update docs' with medium priority",
        "List all tasks",
        "Add task 'Fix CI pipeline' with high priority",
    ]

    print("Sending all queries concurrently...")
    start = time.monotonic()
    results = await asyncio.gather(
        *(agent.process_single_query(q) for q in queries)
    )
    elapsed = time.monotonic() - start
    print(f"All {len(queries)} queries completed in {elapsed:.2f}s")

    print("\nSequential baseline:")
    start = time.monotonic()
    for q in queries:
        await agent.process_single_query(q)
    elapsed = time.monotonic() - start
    print(f"Sequential: {elapsed:.2f}s")
```

**Why this matters:** vLLM's continuous batching scheduler (`max_num_seqs=128`) automatically batches concurrent requests for GPU efficiency. This demo shows the throughput advantage of async processing — a key reason to use vLLM over synchronous inference.

**Note:** Each concurrent query needs its own kernel `step()` call (or separate kernel instances), since the kernel's `run()` is designed for a single conversation. The demo should use `kernel.step()` directly for independent single-turn queries.

---

### Step 10: Demonstrate Swappable Model Plugins

**Goal:** Show that the same agent can work with different model plugins by swapping them at construction time.

**Implementation:**

```python
async def demo_plugin_swap() -> None:
    """Show plugin swapping via PluginRegistry."""
    from structured_agents.plugins.registry import get_plugin, list_plugins

    print(f"Available plugins: {list_plugins()}")

    for plugin_name in ["qwen", "function_gemma"]:
        plugin = get_plugin(plugin_name)
        print(f"\n--- Plugin: {plugin.name} ---")
        print(f"  Supports EBNF: {plugin.supports_ebnf}")
        print(f"  Supports structural_tag: {plugin.supports_structural_tags}")
        print(f"  Supports json_schema: {plugin.supports_json_schema}")

        # Show how the same tools format differently per plugin
        formatted_tools = plugin.format_tools(tool_schemas)
        print(f"  Formatted tools sample: {json.dumps(formatted_tools[0], indent=2)[:200]}...")
```

**Note:** Actually running both plugins against the same vLLM server requires models that match each plugin's expected format. The demo can show the formatting differences without requiring both models to be loaded. If only Qwen3 is available, the FunctionGemma plugin demo can be format-only.

---

### Step 11: Demonstrate Token Usage Tracking and `RunResult` Inspection

**Goal:** Show comprehensive run metadata capture.

**Implementation:**

```python
async def demo_run_result_inspection(agent: WorkspaceAgent) -> None:
    """Show full RunResult inspection."""
    result = await agent.process_message("Add task 'Quarterly review' then summarize all tasks")

    print(f"\n--- RunResult Inspection ---")
    print(f"  Turns taken: {result.turn_count}")
    print(f"  Termination reason: {result.termination_reason}")
    print(f"  Final message: {result.final_message.content[:200]}")

    if result.total_usage:
        print(f"  Token usage:")
        print(f"    Prompt tokens: {result.total_usage.prompt_tokens}")
        print(f"    Completion tokens: {result.total_usage.completion_tokens}")
        print(f"    Total tokens: {result.total_usage.total_tokens}")

    print(f"  Conversation history ({len(result.history)} messages):")
    for msg in result.history:
        role = msg.role
        content_preview = (msg.content or "")[:80]
        tool_info = f" [tools: {len(msg.tool_calls)}]" if msg.tool_calls else ""
        print(f"    {role}: {content_preview}{tool_info}")
```

---

### Step 12: Add Structured Error Handling

**Goal:** Demonstrate graceful error handling patterns.

**What to add to `.pym` scripts:** Consistent error returns:

```python
# In each .pym script, wrap main logic:
try:
    # ... main logic ...
    result = {"status": "ok", ...}
except Exception as exc:
    result = {"error": str(exc)}

result
```

**What to add to the demo:** Error scenarios:

```python
async def demo_error_handling(agent: WorkspaceAgent) -> None:
    """Show error handling patterns."""
    # Try to update a non-existent entry
    result = await agent.process_message("Update the task 'nonexistent_task' to completed")
    # The tool returns {"error": "Entry 'nonexistent_task' does not exist"}
    # The model sees this error and can report it to the user

    # Show observer capturing the error event
    error_events = [e for e in agent.observer.events if e.get("type") == "tool_result" and e["event"].is_error]
    print(f"Error events captured: {len(error_events)}")
```

---

### Step 13: Demonstrate `CompositeObserver`

**Goal:** Show how multiple observers can be attached simultaneously.

**Implementation:**

```python
from structured_agents import CompositeObserver

class MetricsObserver:
    """Observer that collects timing metrics."""
    def __init__(self) -> None:
        self.model_durations: list[int] = []
        self.tool_durations: list[int] = []

    async def on_model_response(self, event: ModelResponseEvent) -> None:
        self.model_durations.append(event.duration_ms)

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        self.tool_durations.append(event.duration_ms)

    # ... other methods as no-ops ...

    def summary(self) -> str:
        avg_model = sum(self.model_durations) / len(self.model_durations) if self.model_durations else 0
        avg_tool = sum(self.tool_durations) / len(self.tool_durations) if self.tool_durations else 0
        return f"Model avg: {avg_model:.0f}ms, Tool avg: {avg_tool:.0f}ms"

# Combine observers
observer = CompositeObserver([DemoObserver(), MetricsObserver()])
```

---

### Step 14: Demonstrate GrailRegistry Auto-Discovery

**Goal:** Show that tool schemas can be auto-discovered from `.pym` files and their `.grail/*/inputs.json` artifacts.

**Implementation:**

```python
from structured_agents.registries.grail import GrailRegistry, GrailRegistryConfig

async def demo_registry_discovery() -> None:
    """Show auto-discovery of tool schemas from .pym files."""
    registry = GrailRegistry(GrailRegistryConfig(agents_dir=AGENT_DIR))

    print("Discovered tools:")
    for tool_name in registry.list_tools():
        schema = registry.resolve(tool_name)
        if schema:
            print(f"  {tool_name}: {schema.description}")
            print(f"    Parameters: {json.dumps(schema.parameters, indent=4)}")
```

**Prerequisite:** Run `grail check` on all `.pym` files to generate `inputs.json` artifacts. The demo should include this as a setup step.

---

### Step 15: Restructure the Demo with Sections

**Goal:** Organize the demo into clearly labeled sections that progressively demonstrate capabilities.

**Target structure for `workspace_agent_demo.py`:**

```python
async def main() -> None:
    # =========================================================================
    # Section 1: Bundle Loading & Configuration
    # =========================================================================
    # - Load bundle.yaml
    # - Show auto-resolved tool schemas
    # - Show grammar config from bundle
    # - Show Jinja2 prompt rendering

    # =========================================================================
    # Section 2: AgentKernel with Observer — Single-Turn
    # =========================================================================
    # - Create kernel with DemoObserver
    # - Execute kernel.step() with a simple query
    # - Show observer event output
    # - Show StepResult inspection

    # =========================================================================
    # Section 3: Multi-Turn Agent Loop
    # =========================================================================
    # - Execute kernel.run() with a complex multi-step query
    # - Show multi-turn conversation flow via observer events
    # - Show RunResult with turn count, termination reason, token usage

    # =========================================================================
    # Section 4: Grammar Modes Comparison
    # =========================================================================
    # - Same query with ebnf, structural_tag, json_schema
    # - Show grammar artifacts

    # =========================================================================
    # Section 5: Concurrent Tool Execution
    # =========================================================================
    # - Multiple parallel tool calls in one model response
    # - Observer events showing concurrent execution timing

    # =========================================================================
    # Section 6: Batched Async Inference
    # =========================================================================
    # - Multiple independent queries sent concurrently
    # - Timing comparison vs sequential

    # =========================================================================
    # Section 7: Error Handling
    # =========================================================================
    # - Intentional error scenario
    # - Observer captures error events
    # - Model handles tool errors gracefully

    # =========================================================================
    # Section 8: Plugin & Configuration Showcase
    # =========================================================================
    # - Plugin registry listing
    # - Plugin capability comparison
    # - Token usage summary
    # - Metrics observer summary
```

---

## Part 4: Implementation Priority

| Priority | Step | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Step 5: Rewrite to use AgentKernel | High | Highest — transforms the demo from anti-pattern to best practice |
| **P0** | Step 4: Implement DemoObserver | Low | High — immediate visibility into kernel internals |
| **P0** | Step 3: Build RegistryBackendToolSource | Low | High — required for AgentKernel |
| **P1** | Step 1: Create bundle.yaml | Low | High — demonstrates recommended packaging |
| **P1** | Step 6: Multi-turn conversations | Medium | High — core value proposition |
| **P1** | Step 15: Restructure with sections | Medium | High — demo clarity and usability |
| **P2** | Step 7: Grammar modes comparison | Medium | Medium — educational value |
| **P2** | Step 8: Concurrent tool execution | Low | Medium — performance showcase |
| **P2** | Step 9: Batched async inference | Medium | Medium — vLLM advantage showcase |
| **P2** | Step 11: RunResult inspection | Low | Medium — completeness |
| **P3** | Step 2: Context providers | Low | Low-Medium — cleaner architecture |
| **P3** | Step 10: Plugin swap demo | Low | Low — format-only without second model |
| **P3** | Step 12: Error handling | Low | Low — robustness |
| **P3** | Step 13: CompositeObserver | Low | Low — demonstrates composition |
| **P3** | Step 14: GrailRegistry auto-discovery | Low | Low — demonstrates convenience |

---

## Part 5: Files to Create/Modify

### New files
| File | Purpose |
|------|---------|
| `demo/agents/workspace_agent/bundle.yaml` | Bundle manifest |
| `demo/agents/workspace_agent/submit_result.pym` | Termination tool |
| `demo/agents/workspace_agent/workspace_context.pym` | Context provider (optional) |

### Files to modify
| File | Changes |
|------|---------|
| `demo/workspace_agent_demo.py` | Complete rewrite to use AgentKernel, bundle, observer, ToolSource |
| `demo/agents/workspace_agent/add_entry.pym` | Add error handling wrapper |
| `demo/agents/workspace_agent/update_entry.pym` | Add error handling wrapper |
| `demo/agents/workspace_agent/list_entries.pym` | Add error handling wrapper |
| `demo/agents/workspace_agent/summarize_state.pym` | Remove `nested_tool_call` pattern (kernel handles multi-turn) |
| `demo/agents/workspace_agent/format_summary.pym` | Add error handling wrapper |

### Files to ensure exist (via `grail check`)
| File | Purpose |
|------|---------|
| `demo/agents/workspace_agent/.grail/*/inputs.json` | Auto-generated schemas for GrailRegistry |

---

## Part 6: Verification Criteria

The enhanced demo should satisfy all of these:

1. **Runs end-to-end** with `python demo/workspace_agent_demo.py` against the vLLM server.
2. **Uses `AgentKernel`** — no direct `client.chat_completion()` calls.
3. **Uses `bundle.yaml`** — no manual `ToolSchema` construction in the main demo flow.
4. **Shows observer events** — every kernel event is logged to console.
5. **Shows multi-turn flow** — at least one query requires 2+ turns to complete.
6. **Shows grammar modes** — at least 2 of 3 modes are demonstrated.
7. **Shows concurrent execution** — at least one concurrent tool execution with timing.
8. **Shows batched inference** — concurrent queries with timing comparison.
9. **Shows token usage** — cumulative token counts are printed.
10. **Shows `RunResult`** — turn count, termination reason, history are inspected.
11. **Shows error handling** — at least one intentional error scenario handled gracefully.
12. **Each section is independently understandable** — clear section headers, explanations, and expected output.

---

## Part 7: Expected Demo Output (Sketch)

```
=== Workspace Agent Demo: structured-agents Gold Standard ===

--- Section 1: Bundle Loading ---
  Loaded bundle: workspace_agent v1.0
  Plugin: qwen (supports: ebnf, structural_tag, json_schema)
  Grammar mode: structural_tag
  Tools: add_entry, update_entry, list_entries, summarize_state, format_summary, submit_result
  System prompt: "You are a workspace management assistant..."

--- Section 2: Single-Turn with Observer ---
  Query: "Add a task 'Review Q3 metrics' with high priority"
  [KERNEL] Starting: 6 tools, max 5 turns
  [MODEL REQUEST] Turn 1: 2 messages, 6 tools
  [MODEL RESPONSE] Turn 1: 234ms, 1 tool calls | tokens: 412p/89c
  [TOOL CALL] Turn 1: add_entry({"name": "Review Q3 metrics", "priority": "high"})
  [TOOL RESULT] Turn 1: add_entry [OK] 45ms
  [TURN 1 COMPLETE] 1 calls, 0 errors
  [MODEL REQUEST] Turn 2: 4 messages, 6 tools
  [MODEL RESPONSE] Turn 2: 178ms, 0 tool calls | tokens: 523p/42c
  [KERNEL] Ended: 2 turns, reason=no_tool_calls, 457ms

--- Section 3: Multi-Turn Agent Loop ---
  Query: "Add 'Design review' task, then list all tasks and give me a summary"
  [KERNEL] Starting: 6 tools, max 5 turns
  [MODEL REQUEST] Turn 1: ...
  [TOOL CALL] Turn 1: add_entry(...)
  [TURN 1 COMPLETE] ...
  [TOOL CALL] Turn 2: list_entries(...)
  [TURN 2 COMPLETE] ...
  [TOOL CALL] Turn 3: summarize_state(...)
  [TURN 3 COMPLETE] ...
  [KERNEL] Ended: 4 turns, reason=no_tool_calls, 1234ms
  RunResult: 4 turns, 8 history messages, 1847 total tokens

--- Section 4: Grammar Modes ---
  [ebnf] Tool calls: [("add_entry", {"name": "Test", "priority": "low"})]
  [structural_tag] Tool calls: [("add_entry", {"name": "Test", "priority": "low"})]
  [json_schema] Tool calls: [("add_entry", {"name": "Test", "priority": "low"})]

--- Section 5: Concurrent Tool Execution ---
  Query: "Add three tasks: 'A' (high), 'B' (low), 'C' (medium)"
  [TOOL CALL] Turn 1: add_entry (concurrent)
  [TOOL CALL] Turn 1: add_entry (concurrent)
  [TOOL CALL] Turn 1: add_entry (concurrent)
  [TOOL RESULT] add_entry [OK] 48ms
  [TOOL RESULT] add_entry [OK] 52ms
  [TOOL RESULT] add_entry [OK] 47ms

--- Section 6: Batched Async Inference ---
  Concurrent (4 queries): 0.89s
  Sequential (4 queries): 2.34s
  Speedup: 2.6x

--- Section 7: Error Handling ---
  Query: "Update task 'nonexistent' to completed"
  [TOOL RESULT] update_entry [ERROR] Entry not found
  Model response: "The task 'nonexistent' was not found..."

--- Section 8: Summary ---
  Plugin: qwen
  Model durations avg: 201ms
  Tool durations avg: 48ms
  Total tokens used: 4,521

=== Demo Complete ===
```

---

## Appendix A: Grail `.pym` Script Best Practices for This Demo

1. **Always return dicts** — not bare strings or lists.
2. **Wrap main logic in try/except** — return `{"error": str(exc)}` on failure.
3. **Use `Input()` with descriptions** — enables richer auto-generated schemas.
4. **Keep scripts focused** — one responsibility per script.
5. **Use `@external` for all I/O** — file operations, network calls, etc.
6. **Avoid `nested_tool_call` patterns** — let the kernel's multi-turn loop handle tool chaining naturally. The model should decide what to call next, not the tool script.
7. **Include default values for optional inputs** — makes scripts testable standalone.
8. **Run `grail check`** after editing — regenerates `inputs.json` for registry auto-discovery.

## Appendix B: `structured-agents` Best Practices Summary

1. **Use `AgentKernel`** — never call `client.chat_completion()` directly in production agent code.
2. **Use bundles** — `bundle.yaml` is the recommended way to package agents.
3. **Use `ToolSource`** — compose `RegistryBackendToolSource` from a registry + backend.
4. **Attach observers** — at minimum for logging/debugging; use `CompositeObserver` for multiple concerns.
5. **Use `GrammarConfig`** — always send grammar constraints to ensure structured output.
6. **Use `context_provider`** — inject per-turn context via the kernel's `run()` parameter.
7. **Inspect `RunResult`** — check `turn_count`, `termination_reason`, `total_usage` for operational visibility.
8. **Use termination tools** — define a `submit_result` tool for clean agent loop termination.
9. **Configure `ToolExecutionStrategy`** — use concurrent mode when tools are independent.
10. **Use `HistoryStrategy`** — `SlidingWindowHistory` prevents context overflow in long conversations.
