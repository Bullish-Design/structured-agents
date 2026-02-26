# Subsystems Analysis: Events, Grammar, Tools

**Repo:** structured-agents v0.3.0
**Date:** 2026-02-26
**Scope:** `src/structured_agents/events/`, `grammar/`, `tools/`, plus `kernel.py` and `agent.py` integration

---

## 1. Event System

### 1.1 Architecture

The event system follows an Observer pattern with a discriminated union of frozen dataclasses.

**Files:**
- `events/types.py` — 7 event dataclasses + `Event` union type
- `events/observer.py` — `Observer` protocol + `NullObserver` no-op
- `events/__init__.py` — re-exports all

**Observer Protocol** (`events/observer.py:8-11`):
```python
class Observer(Protocol):
    async def emit(self, event: Event) -> None: ...
```

**NullObserver** (`events/observer.py:14-18`):
```python
class NullObserver:
    async def emit(self, event: Event) -> None:
        pass
```

### 1.2 Event Types Defined

All in `events/types.py`, all `@dataclass(frozen=True)`:

| Event | Fields | Lines |
|---|---|---|
| `KernelStartEvent` | `max_turns: int`, `tools_count: int`, `initial_messages_count: int` | 9-13 |
| `KernelEndEvent` | `turn_count: int`, `termination_reason: str`, `total_duration_ms: int` | 16-20 |
| `ModelRequestEvent` | `turn: int`, `messages_count: int`, `tools_count: int`, `model: str` | 23-28 |
| `ModelResponseEvent` | `turn: int`, `duration_ms: int`, `content: str\|None`, `tool_calls_count: int`, `usage: TokenUsage\|None` | 31-37 |
| `ToolCallEvent` | `turn: int`, `tool_name: str`, `call_id: str`, `arguments: dict[str, Any]` | 40-45 |
| `ToolResultEvent` | `turn: int`, `tool_name: str`, `call_id: str`, `is_error: bool`, `duration_ms: int`, `output_preview: str` | 48-55 |
| `TurnCompleteEvent` | `turn: int`, `tool_calls_count: int`, `tool_results_count: int`, `errors_count: int` | 58-63 |

**Union type** (`events/types.py:66-74`):
```python
Event = Union[
    KernelStartEvent, KernelEndEvent,
    ModelRequestEvent, ModelResponseEvent,
    ToolCallEvent, ToolResultEvent,
    TurnCompleteEvent,
]
```

### 1.3 Events Actually Emitted

**Only 1 of 7 event types is emitted in production code.**

Grepping for `observer.emit` across the entire codebase finds exactly ONE emit call in production code:

- `kernel.py:149-155` — emits `KernelStartEvent` at the start of `run()`:
  ```python
  await self.observer.emit(
      KernelStartEvent(
          max_turns=max_turns,
          tools_count=len(self.tools),
          initial_messages_count=len(initial_messages),
      )
  )
  ```

**Never emitted in production code (6 of 7):**
- `KernelEndEvent` — not emitted at end of `run()` loop
- `ModelRequestEvent` — not emitted before `client.chat_completion()` in `step()`
- `ModelResponseEvent` — not emitted after response parsing in `step()`
- `ToolCallEvent` — not emitted before tool execution in `step()`
- `ToolResultEvent` — not emitted after tool execution in `step()`
- `TurnCompleteEvent` — not emitted at end of each turn in `run()`

**Emitted only in test/demo code:**
- `tests/test_events/test_observer.py` — creates and emits `KernelStartEvent`, `ToolCallEvent` to test observer protocol
- `demo_v03.py:373` — emits `KernelStartEvent` via `NullObserver`
- `demo_v03.py:341-363` — creates instances of all 7 event types for display, but only emits one via `NullObserver`

### 1.4 Observer Wiring

- `AgentKernel` accepts `observer: Observer` with default `NullObserver` (`kernel.py:41`)
- `Agent` accepts `observer: Observer | None` in `__init__` (`agent.py:60`), defaults to `NullObserver`
- `Agent.from_bundle()` does NOT pass observer to kernel (`agent.py:87-91`)
- `Agent.__init__` stores `self.observer` but never uses it — does not pass it to `self.kernel`
- The observer on `Agent` and the observer on `AgentKernel` are **independent and disconnected**

### 1.5 Event System Verdict

The event system is **structurally complete but functionally inert**. All types are defined, the protocol works, but only `KernelStartEvent` is ever emitted. The `run()` method has the wiring but is missing emits for the other 6 event types at their natural lifecycle points (before/after model call, before/after tool execution, turn complete, kernel end).

---

## 2. Grammar System

### 2.1 Architecture

**Files:**
- `grammar/config.py` — `DecodingConstraint` + `GrammarConfig` dataclasses
- `grammar/pipeline.py` — `ConstraintPipeline` class
- `grammar/__init__.py` — re-exports `DecodingConstraint`, `ConstraintPipeline`

### 2.2 Config Classes

**`DecodingConstraint`** (`grammar/config.py:7-13`):
```python
@dataclass(frozen=True, slots=True)
class DecodingConstraint:
    strategy: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = False
    send_tools_to_api: bool = False
```

**`GrammarConfig`** (`grammar/config.py:16-33`):
```python
@dataclass(frozen=True, slots=True)
class GrammarConfig:
    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = True
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"
    send_tools_to_api: bool = True
```

**Note:** `GrammarConfig` is defined but **never imported or used anywhere** — not in `__init__.py`, not in any other module. It is dead code. `DecodingConstraint` is the one actually exported and referenced.

### 2.3 ConstraintPipeline

**`ConstraintPipeline`** (`grammar/pipeline.py:9-29`):
```python
class ConstraintPipeline:
    def __init__(
        self,
        builder: Callable[[list[ToolSchema], DecodingConstraint], dict[str, Any] | None],
        config: DecodingConstraint,
    ):
        self._builder = builder
        self._config = config

    def constrain(self, tools: list[ToolSchema]) -> dict[str, Any] | None:
        if not tools:
            return None
        return self._builder(tools, self._config)
```

The pipeline is a thin wrapper: it takes a builder callable and a config, and delegates to the builder. The `constrain()` method short-circuits on empty tools.

### 2.4 Grammar Integration Into Kernel

**`kernel.py:76-81`** — grammar constraint in `step()`:
```python
grammar_constraint = None
if self.adapter.grammar_builder:
    grammar_constraint = self.adapter.grammar_builder(resolved_tools, None)

extra_body = grammar_constraint
```

Key observations:
- The kernel calls `adapter.grammar_builder(resolved_tools, None)` — **always passes `None` as the config argument**, not an actual `DecodingConstraint`
- The `ModelAdapter.grammar_builder` field signature is `Callable[[list[ToolSchema], Any], dict[str, Any] | None]` — the second arg is `Any`, not `DecodingConstraint`
- `ConstraintPipeline` is **never used by the kernel or agent**. The kernel calls the raw builder callable directly
- The result goes into `extra_body` which is passed to `client.chat_completion(extra_body=extra_body)`

### 2.5 Grammar Builder in Agent

**`agent.py:73-76`** — `Agent.from_bundle()` creates adapter with no-op grammar:
```python
adapter = ModelAdapter(
    name=manifest.model,
    grammar_builder=lambda t, c: None,  # Always returns None
    response_parser=QwenResponseParser(),
)
```

Same pattern in tests:
- `tests/test_kernel/test_basic.py:29` — `grammar_builder=lambda t, c: None`
- `tests/test_integration/test_full_agent.py:69` — `grammar_builder=lambda t, c: None`

### 2.6 Grammar System Verdict

The grammar system has three layers, none fully connected:

1. **`DecodingConstraint`** — defined, exported, used only in `AgentManifest.grammar_config` (which is always `None` from `load_manifest`) and in `ConstraintPipeline`
2. **`GrammarConfig`** — defined but completely dead code, never imported
3. **`ConstraintPipeline`** — defined and tested, but **never instantiated by kernel or agent**. Only used in `demo_v03.py`
4. **`ModelAdapter.grammar_builder`** — the actual integration point, but always receives `None` as config and always returns `None` in agent.py

The grammar pipeline is **architecturally sketched but not wired**. The path from `DecodingConstraint` -> `ConstraintPipeline` -> `extra_body` exists in the demo but not in the production `kernel.py` / `agent.py` path.

---

## 3. Tools System

### 3.1 Architecture

**Files:**
- `tools/protocol.py` — `Tool` protocol
- `tools/grail.py` — `GrailTool` class + `discover_tools()` function
- `tools/__init__.py` — re-exports all

### 3.2 Tool Protocol

**`Tool`** (`tools/protocol.py:8-14`):
```python
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...

    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult: ...
```

Two methods:
- `schema` — property returning `ToolSchema` (name, description, parameters, backend, script_path, context_providers)
- `execute(arguments, context)` — async, returns `ToolResult`. The `context` parameter is typed as `Any`

### 3.3 GrailTool Implementation

**`GrailTool`** (`tools/grail.py:9-41`):
```python
class GrailTool:
    def __init__(self, script: Any, limits: Any = None):
        self._script = script
        self._limits = limits
        self._schema = ToolSchema(
            name=script.name,
            description=f"Tool: {script.name}",
            parameters={"type": "object", "properties": {}},
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult:
        try:
            result = await self._script.run(inputs=arguments, limits=self._limits)
            output = json.dumps(result) if not isinstance(result, str) else result
            return ToolResult(
                call_id=context.call_id if context else "unknown",
                name=self._script.name,
                output=output,
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                call_id=context.call_id if context else "unknown",
                name=self._script.name,
                output=str(e),
                is_error=True,
            )
```

Key observations:
- `script` is typed as `Any` — expected to be a Grail script with `.name` and `.run()` method
- Schema description is always `"Tool: {script.name}"` — does not extract actual description from the script
- Schema parameters is always `{"type": "object", "properties": {}}` — **never extracts actual parameter schema from the script**
- `context` parameter in `execute()` is expected to have `.call_id` but this is unchecked; falls back to `"unknown"` if context is `None`
- Error handling: catches all exceptions, returns `ToolResult(is_error=True)` with the exception string

### 3.4 discover_tools()

**`discover_tools`** (`tools/grail.py:44-47`):
```python
def discover_tools(agents_dir: str):
    """Discover .pym tools in a directory."""
    # TODO: implement with grail.load()
    return []
```

**This is a stub.** It always returns an empty list. The actual implementation exists only in `demo_v03.py:80-100` which imports `grail` and uses `grail.load()`.

### 3.5 How Kernel Uses Tools

**Tool resolution** (`kernel.py:48-49, 57-66`):
```python
def _tool_map(self) -> dict[str, Tool]:
    return {t.schema.name: t for t in self.tools}
```

`step()` accepts tools as `Sequence[ToolSchema] | Sequence[str]`:
- If `ToolSchema` objects: used directly
- If strings: looked up in `_tool_map()` by name

**Tool execution** (`kernel.py:108-129`):
```python
async def execute_one(tc: ToolCall):
    tool = tool_map.get(tc.name)
    if not tool:
        return ToolResult(call_id=tc.id, name=tc.name, output=f"Unknown tool: {tc.name}", is_error=True)
    return await tool.execute(tc.arguments, None)  # NOTE: context is always None
```

- Context is **always passed as `None`** to `tool.execute()`
- This means `GrailTool.execute()` will always produce `call_id="unknown"`
- Concurrency: sequential if `max_concurrency <= 1`, otherwise uses `asyncio.gather` with semaphore

### 3.6 How Agent Uses Tools

**`agent.py:71`** in `from_bundle()`:
```python
tools = discover_tools(str(manifest.agents_dir))
```
Since `discover_tools()` is a stub returning `[]`, **`Agent.from_bundle()` always gets zero tools**.

**`agent.py:102`** in `run()`:
```python
tool_schemas = [t.schema for t in self.kernel.tools]
```
Passes all kernel tool schemas to `kernel.run()`.

### 3.7 Tools System Verdict

The Tool protocol is clean and functional. `GrailTool` implements it but has two gaps:
1. Does not extract real parameter schemas from grail scripts
2. Always receives `None` context from the kernel, making `call_id` always `"unknown"`

`discover_tools()` is a stub — the real implementation is only in the demo file. Any use of `Agent.from_bundle()` results in zero tools.

---

## 4. Kernel-Agent Integration

### 4.1 AgentKernel

**`kernel.py:34-46`** — full dataclass signature:
```python
@dataclass
class AgentKernel:
    client: LLMClient
    adapter: ModelAdapter
    tools: list[Tool] = field(default_factory=list)
    observer: Observer = field(default_factory=NullObserver)
    max_history_messages: int = 50        # NOTE: never used
    max_concurrency: int = 1
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_choice: str = "auto"
```

**Unused fields:**
- `max_history_messages` — declared but never referenced in any method

**`step()` signature** (`kernel.py:51-55`):
```python
async def step(
    self,
    messages: list[Message],
    tools: Sequence[ToolSchema] | Sequence[str],
) -> StepResult:
```

**`run()` signature** (`kernel.py:138-143`):
```python
async def run(
    self,
    initial_messages: list[Message],
    tools: Sequence[ToolSchema] | Sequence[str],
    max_turns: int = 20,
) -> RunResult:
```

**`run()` loop** (`kernel.py:157-190`):
1. Emits `KernelStartEvent`
2. While turn_count < max_turns:
   - Calls `self.step(messages, tools)`
   - Appends response message to messages
   - Appends tool result messages to messages
   - If no tool_calls in step result: breaks with `termination_reason = "no_tool_calls"`
3. Returns `RunResult`

**Missing from the loop:**
- No `KernelEndEvent` emit
- No `ModelRequestEvent` / `ModelResponseEvent` emits in `step()`
- No `ToolCallEvent` / `ToolResultEvent` emits in `step()`
- No `TurnCompleteEvent` emit per turn
- No timing (`time` is imported but unused)
- No history truncation despite `max_history_messages` field existing

### 4.2 Agent

**`agent.py:53-111`** — high-level API:

```python
class Agent:
    def __init__(self, kernel: AgentKernel, manifest: AgentManifest, observer: Observer | None = None):
        self.kernel = kernel
        self.manifest = manifest
        self.observer = observer or NullObserver()

    @classmethod
    async def from_bundle(cls, path: str | Path, **overrides) -> "Agent":
        manifest = load_manifest(path)
        tools = discover_tools(str(manifest.agents_dir))  # Always returns []
        adapter = ModelAdapter(
            name=manifest.model,
            grammar_builder=lambda t, c: None,  # No-op
            response_parser=QwenResponseParser(),
        )
        client = build_client({
            "model": manifest.model,
            "base_url": "http://localhost:8000/v1",
            "api_key": "EMPTY",
        })
        kernel = AgentKernel(client=client, adapter=adapter, tools=tools)
        return cls(kernel, manifest)  # NOTE: observer not passed

    async def run(self, user_input: str, **kwargs) -> RunResult:
        messages = [
            Message(role="system", content=self.manifest.system_prompt),
            Message(role="user", content=user_input),
        ]
        tool_schemas = [t.schema for t in self.kernel.tools]
        return await self.kernel.run(
            messages, tool_schemas,
            max_turns=kwargs.get("max_turns", self.manifest.max_turns),
        )
```

**Issues in `from_bundle()`:**
1. `**overrides` parameter is accepted but never used
2. Observer is not forwarded to `AgentKernel`
3. `base_url` is hardcoded to `http://localhost:8000/v1`
4. `api_key` is hardcoded to `"EMPTY"`
5. `grammar_builder` is always no-op

### 4.3 ModelAdapter Integration

**`ModelAdapter`** (`models/adapter.py:10-17`):
```python
@dataclass(frozen=True)
class ModelAdapter:
    name: str
    grammar_builder: Callable[[list[ToolSchema], Any], dict[str, Any] | None]
    response_parser: Any  # ResponseParser
    format_messages: Callable[[list[Message], list[dict]], list[dict]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict]] | None = None
```

Defaults via `__post_init__`:
- `format_messages` -> `_default_format_messages` which calls `msg.to_openai_format()` and appends tools as system message
- `format_tools` -> `_default_format_tools` which calls `ts.to_openai_format()`

**Usage in `kernel.py:68-73`:**
```python
formatter = self.adapter.format_messages
formatted_messages = formatter(messages, []) if formatter else []  # NOTE: always passes empty list for tools
if resolved_tools:
    tool_formatter = self.adapter.format_tools
    formatted_tools = tool_formatter(resolved_tools) if tool_formatter else None
```

Note: `format_messages` is called with `messages` and an empty list `[]` for tools, meaning `_default_format_messages` never appends a tools system message. The tools are handled separately via `format_tools`.

### 4.4 Response Parsing

**`QwenResponseParser`** (`models/parsers.py:18-60`):
```python
def parse(self, content: str | None, tool_calls: list[dict[str, Any]] | None) -> tuple[str | None, list[ToolCall]]:
```

Two parsing paths:
1. If `tool_calls` present (from vLLM API): parse function calls from dict format
2. If no `tool_calls` but `content` present: try XML-style `<tool_call>{json}</tool_call>` extraction

**`FunctionGemmaResponseParser`** (`models/parsers.py:63-70`):
- Exists but delegates entirely to `QwenResponseParser` — effectively dead/placeholder

**Usage in `kernel.py:94-96`:**
```python
content, tool_calls = self.adapter.response_parser.parse(
    response.content, response.tool_calls
)
```

---

## 5. Cross-Cutting Findings

### 5.1 Completeness Matrix

| Subsystem | Defined | Wired | Functional |
|---|---|---|---|
| Events: types | 7/7 | 1/7 emitted | 1/7 |
| Events: observer | complete | kernel only | works for that 1 emit |
| Grammar: DecodingConstraint | complete | stored in manifest | never reaches kernel |
| Grammar: GrammarConfig | complete | nowhere | dead code |
| Grammar: ConstraintPipeline | complete | demo only | not used in kernel/agent |
| Grammar: builder callable | complete | kernel calls it | always returns None |
| Tools: protocol | complete | kernel uses it | works |
| Tools: GrailTool | complete | structurally ok | context always None |
| Tools: discover_tools | stub | agent calls it | always returns [] |

### 5.2 Data Flow Gaps

1. **Event emission gap:** `step()` does all the work (model call, tool execution) but emits zero events. `run()` wraps `step()` but only emits `KernelStartEvent`.

2. **Grammar config gap:** `DecodingConstraint` is created in `AgentManifest` but never passed through to `grammar_builder`. The kernel always passes `None` as the config arg. `ConstraintPipeline` exists to bridge this but is never instantiated by kernel/agent.

3. **Tool context gap:** `kernel.py:117` calls `tool.execute(tc.arguments, None)`. The `ToolCall` object has the `id` field that should be the context, but it's not wrapped or passed.

4. **Tool discovery gap:** `discover_tools()` is a stub. The real implementation in `demo_v03.py` shows what it should do: use `grail.load()` to load `.pym` files.

5. **Observer forwarding gap:** `Agent.__init__` accepts an observer but never passes it to `kernel`. `Agent.from_bundle()` doesn't accept or forward an observer at all.

### 5.3 Unused Imports / Fields

- `kernel.py:5` — `import time` — never used
- `kernel.py:42` — `max_history_messages: int = 50` — never referenced
- `grammar/config.py:16-33` — `GrammarConfig` class — never imported anywhere
- `models/parsers.py:63-70` — `FunctionGemmaResponseParser` — delegates to Qwen, not independently functional

### 5.4 Key Integration Point Signatures (Exact)

```python
# kernel.py:51
async def step(self, messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str]) -> StepResult

# kernel.py:138
async def run(self, initial_messages: list[Message], tools: Sequence[ToolSchema] | Sequence[str], max_turns: int = 20) -> RunResult

# tools/protocol.py:11-14
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...
    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult: ...

# events/observer.py:8-11
class Observer(Protocol):
    async def emit(self, event: Event) -> None: ...

# grammar/pipeline.py:12-18
class ConstraintPipeline:
    def __init__(self, builder: Callable[[list[ToolSchema], DecodingConstraint], dict[str, Any] | None], config: DecodingConstraint): ...

# models/adapter.py:10-17
class ModelAdapter:
    name: str
    grammar_builder: Callable[[list[ToolSchema], Any], dict[str, Any] | None]
    response_parser: Any
    format_messages: Callable[[list[Message], list[dict]], list[dict]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict]] | None = None

# client/protocol.py:25-34
async def chat_completion(self, messages, tools=None, tool_choice="auto", max_tokens=4096, temperature=0.1, extra_body=None, model=None) -> CompletionResponse
```
