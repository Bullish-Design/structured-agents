# structured-agents Source Analysis

**Generated:** 2026-02-26
**Version:** 0.3.0
**Total source files:** 21
**Total lines of code:** ~892

---

## 1. Complete File Listing with Line Counts

| File | Lines | Purpose |
|------|-------|---------|
| `src/structured_agents/__init__.py` | 71 | Package root; re-exports public API |
| `src/structured_agents/kernel.py` | 205 | Core agent loop orchestrator |
| `src/structured_agents/agent.py` | 112 | High-level user-facing Agent API |
| `src/structured_agents/types.py` | 186 | Core data types (Message, ToolCall, etc.) |
| `src/structured_agents/exceptions.py` | 47 | Exception hierarchy |
| `src/structured_agents/grammar/__init__.py` | 10 | Grammar subpackage re-exports |
| `src/structured_agents/grammar/config.py` | 34 | Decoding constraint configuration |
| `src/structured_agents/grammar/pipeline.py` | 30 | Constraint pipeline for grammar generation |
| `src/structured_agents/client/__init__.py` | 7 | Client subpackage re-exports |
| `src/structured_agents/client/factory.py` | 18 | Client factory helper |
| `src/structured_agents/client/openai.py` | 97 | OpenAI-compatible LLM client |
| `src/structured_agents/client/protocol.py` | 54 | LLMClient protocol definition |
| `src/structured_agents/tools/__init__.py` | 7 | Tools subpackage re-exports |
| `src/structured_agents/tools/grail.py` | 48 | Grail (.pym script) tool implementation |
| `src/structured_agents/tools/protocol.py` | 15 | Tool protocol definition |
| `src/structured_agents/models/__init__.py` | 16 | Models subpackage re-exports |
| `src/structured_agents/models/adapter.py` | 43 | Model adapter for model-specific behavior |
| `src/structured_agents/models/parsers.py` | 71 | Response parser implementations |
| `src/structured_agents/events/__init__.py` | 27 | Events subpackage re-exports |
| `src/structured_agents/events/observer.py` | 19 | Observer protocol and NullObserver |
| `src/structured_agents/events/types.py` | 75 | Event type dataclasses |

---

## 2. Per-File Detailed Analysis

### `src/structured_agents/__init__.py` (71 lines)

**Purpose:** Package root. Imports and re-exports the entire public API surface.

**Key exports:** Message, ToolCall, ToolResult, ToolSchema, TokenUsage, StepResult, RunResult, Tool, GrailTool, ModelAdapter, QwenResponseParser, DecodingConstraint, ConstraintPipeline, Observer, NullObserver, Event (and all event subtypes), AgentKernel, Agent, AgentManifest, LLMClient, OpenAICompatibleClient, build_client.

**Issues:**
- `KernelConfig` is defined in `types.py` but NOT exported from `__init__.py`. It is used nowhere externally but is referenced by AgentKernel's fields (which duplicate its values).
- `FunctionGemmaResponseParser` is exported from `models/__init__.py` but NOT re-exported from the top-level `__init__.py`.
- `ResponseParser` protocol is exported from `models/__init__.py` but NOT re-exported from the top-level `__init__.py`.
- `CompletionResponse` is exported from `client/__init__.py` but NOT re-exported from the top-level `__init__.py`.
- `discover_tools` is exported from `tools/__init__.py` but NOT re-exported from the top-level `__init__.py`.

---

### `src/structured_agents/kernel.py` (205 lines)

**Purpose:** The core agent loop. `AgentKernel` orchestrates model calls and tool execution in a loop.

**Key classes/functions:**

```python
@dataclass
class AgentKernel:
    client: LLMClient
    adapter: ModelAdapter
    tools: list[Tool] = field(default_factory=list)
    observer: Observer = field(default_factory=NullObserver)
    max_history_messages: int = 50
    max_concurrency: int = 1
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_choice: str = "auto"

    def _tool_map(self) -> dict[str, Tool]: ...

    async def step(
        self,
        messages: list[Message],
        tools: Sequence[ToolSchema] | Sequence[str],
    ) -> StepResult: ...

    async def run(
        self,
        initial_messages: list[Message],
        tools: Sequence[ToolSchema] | Sequence[str],
        max_turns: int = 20,
    ) -> RunResult: ...

    async def close(self) -> None: ...
```

**Issues:**
1. `max_history_messages` field is declared (line 42) but **never used** anywhere in the class. Dead configuration.
2. `observer` field is declared but only used for `KernelStartEvent` emission. `KernelEndEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `ToolCallEvent`, `ToolResultEvent`, and `TurnCompleteEvent` are **never emitted** despite being imported. The observer integration is incomplete.
3. `_tool_map()` is called twice per `step()` invocation (line 49 for resolution, line 106 for execution). Should be cached or called once.
4. The `step()` method passes `formatter(messages, [])` with an empty list (line 69), ignoring the tools list in message formatting.
5. `grammar_builder` is called with `(resolved_tools, None)` (line 79) — the second argument (config/constraint) is always `None`, making grammar configuration inoperative.
6. `tool.execute(tc.arguments, None)` passes `None` as context (line 117), which will cause `GrailTool.execute()` to use `"unknown"` as `call_id` since `context` is None. The `ToolCall.id` is never passed through.
7. The `run()` loop does not emit `KernelEndEvent` at the end (only emits `KernelStartEvent`).
8. `KernelConfig` is imported via types but duplicated as individual fields on `AgentKernel`.

---

### `src/structured_agents/agent.py` (112 lines)

**Purpose:** High-level `Agent` class and `AgentManifest` for loading bundles from YAML.

**Key classes/functions:**

```python
@dataclass
class AgentManifest:
    name: str
    system_prompt: str
    agents_dir: Path
    limits: Any = None
    model: str = "qwen"
    grammar_config: DecodingConstraint | None = None
    max_turns: int = 20

def load_manifest(bundle_path: str | Path) -> AgentManifest: ...

class Agent:
    def __init__(
        self,
        kernel: AgentKernel,
        manifest: AgentManifest,
        observer: Observer | None = None,
    ): ...

    @classmethod
    async def from_bundle(cls, path: str | Path, **overrides) -> "Agent": ...

    async def run(self, user_input: str, **kwargs) -> RunResult: ...

    async def close(self) -> None: ...
```

**Issues:**
1. `AgentManifest.grammar_config` is defined but **always set to `None`** in `load_manifest()` (line 48). It is never read from YAML or used anywhere.
2. `AgentManifest.limits` is loaded as `data.get("limits")` but typed as `Any` — no structured type.
3. `Agent.from_bundle()` hardcodes `grammar_builder=lambda t, c: None` (line 75), making grammar constraints permanently disabled when using the bundle API.
4. `Agent.from_bundle()` hardcodes `base_url="http://localhost:8000/v1"` and `api_key="EMPTY"` (lines 82-83). No way to override these via `**overrides` (which is accepted but **never used**).
5. `Agent.__init__` accepts `observer` but does not pass it to the kernel. The `self.observer` is stored but unused.
6. `load_manifest` has a subtle bug: `Path(bundle_path).parent` (line 45) — if `bundle_path` is a directory, `.parent` goes one level up instead of using the directory itself. However, when `path.is_dir()` is True, it sets `path = path / "bundle.yaml"` but still uses the original `bundle_path` for `agents_dir` computation.

---

### `src/structured_agents/types.py` (186 lines)

**Purpose:** Core domain types used throughout the codebase.

**Key classes:**

```python
class KernelConfig:
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_choice: str = "auto"
    max_concurrency: int = 1

@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_openai_format(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    @property
    def arguments_json(self) -> str: ...

    @classmethod
    def create(cls, name: str, arguments: dict[str, Any]) -> "ToolCall": ...

@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    name: str
    output: str
    is_error: bool = False

    @property
    def output_str(self) -> str: ...

    def to_message(self) -> Message: ...

@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]
    backend: str = "python"
    script_path: Path | None = None
    context_providers: tuple[Path, ...] = ()

    def to_openai_format(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass(frozen=True, slots=True)
class StepResult:
    response_message: Message
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    usage: TokenUsage | None = None

@dataclass(frozen=True)
class RunResult:
    final_message: Message
    history: list[Message]
    turn_count: int
    termination_reason: str
    final_tool_result: ToolResult | None = None
    total_usage: TokenUsage | None = None
```

**Issues:**
1. `KernelConfig` is a plain class (not a dataclass), lacks `@dataclass` decorator. Its attributes are class-level defaults, not instance attributes. Creating instances via `KernelConfig()` won't actually set instance attributes — they'll only exist as class attributes. This is likely a bug.
2. `KernelConfig` is **unused** — `AgentKernel` duplicates its fields directly.
3. `ToolResult.output_str` is a trivial property that just returns `self.output`. Appears to be dead code / unnecessary indirection.
4. `RunResult.final_tool_result` and `RunResult.total_usage` are defined but **never populated** by `AgentKernel.run()`. The kernel always returns `RunResult` without setting these optional fields.
5. `RunResult` uses `@dataclass(frozen=True)` without `slots=True`, inconsistent with other types.
6. `ToolSchema.backend`, `ToolSchema.script_path`, `ToolSchema.context_providers` are Grail-specific fields on a generic schema type. These are never used by the core kernel.
7. `Message` uses `frozen=True, slots=True` which means `tool_calls` (a list) cannot be mutated after creation — this is correct for immutability but requires care.

---

### `src/structured_agents/exceptions.py` (47 lines)

**Purpose:** Exception hierarchy for the package.

**Key classes:**

```python
class StructuredAgentsError(Exception): ...

class KernelError(StructuredAgentsError):
    def __init__(self, message: str, turn: int | None = None, phase: str | None = None) -> None: ...

class ToolExecutionError(StructuredAgentsError):
    def __init__(self, message: str, tool_name: str, call_id: str, code: str | None = None) -> None: ...

class PluginError(StructuredAgentsError): ...

class BundleError(StructuredAgentsError): ...

class BackendError(StructuredAgentsError): ...
```

**Issues:**
1. **None of these exceptions are used anywhere in the codebase.** No module imports or raises any of them. The entire exception hierarchy is dead code.
2. Not exported from `__init__.py`.

---

### `src/structured_agents/grammar/config.py` (34 lines)

**Purpose:** Configuration dataclasses for grammar-constrained decoding.

**Key classes:**

```python
@dataclass(frozen=True, slots=True)
class DecodingConstraint:
    strategy: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = False
    send_tools_to_api: bool = False

@dataclass(frozen=True, slots=True)
class GrammarConfig:
    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = True
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"
    send_tools_to_api: bool = True
```

**Issues:**
1. `GrammarConfig` and `DecodingConstraint` overlap significantly. Both have `strategy`/`mode`, `allow_parallel_calls`, and `send_tools_to_api` fields. `GrammarConfig` adds `args_format`.
2. `GrammarConfig` is **never imported or used** anywhere. Dead code.
3. `DecodingConstraint` is exported but only stored in `AgentManifest.grammar_config` which is always `None`.
4. The defaults differ between the two: `DecodingConstraint` defaults to `allow_parallel_calls=False, send_tools_to_api=False` while `GrammarConfig` defaults to `True, True`. This is inconsistent.

---

### `src/structured_agents/grammar/pipeline.py` (30 lines)

**Purpose:** Wraps a grammar builder callable with a fixed constraint config.

**Key classes:**

```python
class ConstraintPipeline:
    def __init__(
        self,
        builder: Callable[[list[ToolSchema], DecodingConstraint], dict[str, Any] | None],
        config: DecodingConstraint,
    ): ...

    def constrain(self, tools: list[ToolSchema]) -> dict[str, Any] | None: ...
```

**Issues:**
1. `ConstraintPipeline` is exported but **never instantiated** anywhere in the codebase. Dead code.
2. The kernel does not use `ConstraintPipeline` — it calls `adapter.grammar_builder` directly.

---

### `src/structured_agents/client/protocol.py` (54 lines)

**Purpose:** Defines the `LLMClient` protocol and `CompletionResponse` dataclass.

**Key classes:**

```python
@dataclass
class CompletionResponse:
    content: str | None
    tool_calls: list[dict[str, Any]] | None
    usage: TokenUsage | None
    finish_reason: str | None
    raw_response: dict[str, Any]

class LLMClient(Protocol):
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        extra_body: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> CompletionResponse: ...

    async def close(self) -> None: ...
```

**Issues:**
- `CompletionResponse` is not exported from top-level `__init__.py` (only from `client/__init__.py`).
- `CompletionResponse.raw_response` stores the full API response which could be large. No truncation or lazy access.

---

### `src/structured_agents/client/openai.py` (97 lines)

**Purpose:** Concrete `OpenAICompatibleClient` implementation using `openai.AsyncOpenAI`.

**Key classes/functions:**

```python
class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "EMPTY",
        model: str = "default",
        timeout: float = 120.0,
    ): ...

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        extra_body: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> CompletionResponse: ...

    async def close(self) -> None: ...

def build_client(config: dict[str, Any]) -> LLMClient: ...
```

**Issues:**
1. **Duplicate `build_client` function**: defined in both `client/openai.py` (line 89) and `client/factory.py` (line 10). The factory version returns `OpenAICompatibleClient` (concrete type), the openai.py version returns `LLMClient` (protocol type). They are functionally identical.
2. The top-level `__init__.py` imports `build_client` from `client/__init__.py`, which imports it from `client/openai.py`. The version in `client/factory.py` is **shadowed** and only used by `agent.py` which imports it directly from `client.factory`.
3. `response.to_dict()` (line 82) may not exist on all OpenAI SDK versions — the method name varies between `model_dump()` and `to_dict()`.
4. No error handling for API failures, timeouts, or rate limits.

---

### `src/structured_agents/client/factory.py` (18 lines)

**Purpose:** Factory helper to build clients from config dicts.

**Key functions:**

```python
def build_client(config: dict[str, Any]) -> OpenAICompatibleClient: ...
```

**Issues:**
1. Duplicate of `build_client` in `client/openai.py`. See above.
2. Returns concrete `OpenAICompatibleClient` instead of `LLMClient` protocol type.
3. `agent.py` imports from `client.factory` while `__init__.py` imports from `client.openai`. Inconsistent.

---

### `src/structured_agents/tools/protocol.py` (15 lines)

**Purpose:** Protocol definition for tools.

**Key classes:**

```python
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...

    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult: ...
```

**Issues:**
- `context: Any` is vaguely typed. Since the kernel always passes `None`, this parameter's purpose is unclear.

---

### `src/structured_agents/tools/grail.py` (48 lines)

**Purpose:** Grail tool implementation for `.pym` scripts.

**Key classes/functions:**

```python
class GrailTool:
    def __init__(self, script: Any, limits: Any = None): ...

    @property
    def schema(self) -> ToolSchema: ...

    async def execute(self, arguments: dict[str, Any], context: Any) -> ToolResult: ...

def discover_tools(agents_dir: str): ...
```

**Issues:**
1. `discover_tools()` is a stub — always returns `[]` (line 47). TODO comment says "implement with grail.load()".
2. `GrailTool.__init__` takes `script: Any` — no type safety.
3. `GrailTool.execute` uses `context.call_id` when `context` is not None, but the kernel always passes `None`, so `call_id` is always `"unknown"`.
4. `GrailTool._schema` hardcodes `parameters={"type": "object", "properties": {}}` — no actual parameter introspection from the script.

---

### `src/structured_agents/models/adapter.py` (43 lines)

**Purpose:** Model adapter that bridges the kernel to model-specific formatting/parsing.

**Key classes:**

```python
@dataclass(frozen=True)
class ModelAdapter:
    name: str
    grammar_builder: Callable[[list[ToolSchema], Any], dict[str, Any] | None]
    response_parser: Any  # ResponseParser
    format_messages: Callable[[list[Message], list[dict]], list[dict]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict]] | None = None
```

**Issues:**
1. `response_parser` is typed as `Any` instead of `ResponseParser`. This is explicitly noted in a comment but still loses type safety.
2. Uses `object.__setattr__` in `__post_init__` to work around `frozen=True`. This is a known pattern but fragile.
3. `_default_format_messages` appends tool descriptions as a system message (`"Available tools: " + str(tools)`) which produces unparseable string representations of dicts. The `tools` parameter is always `[]` from the kernel anyway.

---

### `src/structured_agents/models/parsers.py` (71 lines)

**Purpose:** Response parser implementations for different model families.

**Key classes:**

```python
class ResponseParser(Protocol):
    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]: ...

class QwenResponseParser:
    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]: ...

    def _parse_xml_tool_calls(self, content: str) -> list[ToolCall]: ...

class FunctionGemmaResponseParser:
    def parse(
        self, content: str | None, tool_calls: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]: ...
```

**Issues:**
1. `FunctionGemmaResponseParser.parse()` just delegates to `QwenResponseParser().parse()` (line 70). It instantiates a new `QwenResponseParser` on every call. This is a placeholder — no actual FunctionGemma-specific parsing logic.
2. `QwenResponseParser._parse_xml_tool_calls` uses a non-greedy regex `<tool_call>(.*?)</tool_call>` with `re.DOTALL`. This works for well-formed output but doesn't handle nested tags or malformed XML gracefully.
3. When `tool_calls` is provided (from the API), content is discarded (returns `None`). This may lose reasoning/chain-of-thought text the model produced alongside tool calls.

---

### `src/structured_agents/events/types.py` (75 lines)

**Purpose:** Event dataclasses for the observer pattern.

**Key types:**

```python
@dataclass(frozen=True)
class KernelStartEvent:
    max_turns: int
    tools_count: int
    initial_messages_count: int

@dataclass(frozen=True)
class KernelEndEvent:
    turn_count: int
    termination_reason: str
    total_duration_ms: int

@dataclass(frozen=True)
class ModelRequestEvent:
    turn: int
    messages_count: int
    tools_count: int
    model: str

@dataclass(frozen=True)
class ModelResponseEvent:
    turn: int
    duration_ms: int
    content: str | None
    tool_calls_count: int
    usage: TokenUsage | None

@dataclass(frozen=True)
class ToolCallEvent:
    turn: int
    tool_name: str
    call_id: str
    arguments: dict[str, Any]

@dataclass(frozen=True)
class ToolResultEvent:
    turn: int
    tool_name: str
    call_id: str
    is_error: bool
    duration_ms: int
    output_preview: str

@dataclass(frozen=True)
class TurnCompleteEvent:
    turn: int
    tool_calls_count: int
    tool_results_count: int
    errors_count: int

Event = Union[
    KernelStartEvent, KernelEndEvent, ModelRequestEvent, ModelResponseEvent,
    ToolCallEvent, ToolResultEvent, TurnCompleteEvent,
]
```

**Issues:**
1. `Event` is a `Union` type alias, not a base class. This means you can't use `isinstance(e, Event)` checks.
2. Only `KernelStartEvent` is actually emitted by the kernel. All other event types are **unused dead code**.

---

### `src/structured_agents/events/observer.py` (19 lines)

**Purpose:** Observer protocol and null implementation.

**Key classes:**

```python
class Observer(Protocol):
    async def emit(self, event: Event) -> None: ...

class NullObserver:
    async def emit(self, event: Event) -> None:
        pass
```

**Issues:**
- None specific to this file. Clean implementation. The issue is that observer integration in the kernel is incomplete.

---

## 3. Complete Import Graph

```
structured_agents.__init__
├── structured_agents.types
│   └── (stdlib only: uuid, dataclasses, pathlib, typing)
├── structured_agents.tools
│   ├── structured_agents.tools.protocol
│   │   └── structured_agents.types
│   └── structured_agents.tools.grail
│       └── structured_agents.types
├── structured_agents.models
│   ├── structured_agents.models.adapter
│   │   └── structured_agents.types
│   └── structured_agents.models.parsers
│       └── structured_agents.types
├── structured_agents.grammar
│   ├── structured_agents.grammar.config
│   │   └── (stdlib only)
│   └── structured_agents.grammar.pipeline
│       ├── structured_agents.grammar.config
│       └── structured_agents.types
├── structured_agents.events
│   ├── structured_agents.events.types
│   │   └── structured_agents.types
│   └── structured_agents.events.observer
│       └── structured_agents.events.types
├── structured_agents.kernel
│   ├── structured_agents.client.protocol
│   ├── structured_agents.events.observer
│   ├── structured_agents.events.types
│   ├── structured_agents.models.adapter
│   ├── structured_agents.tools.protocol
│   └── structured_agents.types
├── structured_agents.agent
│   ├── structured_agents.client.protocol
│   ├── structured_agents.client.factory
│   ├── structured_agents.events.observer
│   ├── structured_agents.grammar.config
│   ├── structured_agents.kernel
│   ├── structured_agents.models.adapter
│   ├── structured_agents.models.parsers
│   ├── structured_agents.tools.grail
│   └── structured_agents.types
└── structured_agents.client
    ├── structured_agents.client.protocol
    │   └── structured_agents.types
    ├── structured_agents.client.openai
    │   ├── openai (external: AsyncOpenAI)
    │   ├── structured_agents.client.protocol
    │   └── structured_agents.types
    └── structured_agents.client.factory
        └── structured_agents.client.openai
```

**External dependencies:** `openai` (AsyncOpenAI), `yaml` (PyYAML)

**Dependency flow:** `types.py` is the leaf — everything depends on it, it depends on nothing internal. Clean DAG with no circular imports.

---

## 4. Current API Surface (`__init__.py` exports)

### Exported (in `__all__`):

| Symbol | Source Module | Type |
|--------|-------------|------|
| `Message` | `types` | frozen dataclass |
| `ToolCall` | `types` | frozen dataclass |
| `ToolResult` | `types` | frozen dataclass |
| `ToolSchema` | `types` | frozen dataclass |
| `TokenUsage` | `types` | frozen dataclass |
| `StepResult` | `types` | frozen dataclass |
| `RunResult` | `types` | frozen dataclass |
| `Tool` | `tools.protocol` | Protocol |
| `GrailTool` | `tools.grail` | class |
| `ModelAdapter` | `models.adapter` | frozen dataclass |
| `QwenResponseParser` | `models.parsers` | class |
| `DecodingConstraint` | `grammar.config` | frozen dataclass |
| `ConstraintPipeline` | `grammar.pipeline` | class |
| `Observer` | `events.observer` | Protocol |
| `NullObserver` | `events.observer` | class |
| `Event` | `events.types` | Union type alias |
| `KernelStartEvent` | `events.types` | frozen dataclass |
| `KernelEndEvent` | `events.types` | frozen dataclass |
| `ModelRequestEvent` | `events.types` | frozen dataclass |
| `ModelResponseEvent` | `events.types` | frozen dataclass |
| `ToolCallEvent` | `events.types` | frozen dataclass |
| `ToolResultEvent` | `events.types` | frozen dataclass |
| `TurnCompleteEvent` | `events.types` | frozen dataclass |
| `AgentKernel` | `kernel` | dataclass |
| `Agent` | `agent` | class |
| `AgentManifest` | `agent` | dataclass |
| `LLMClient` | `client.protocol` | Protocol |
| `OpenAICompatibleClient` | `client.openai` | class |
| `build_client` | `client.openai` | function |

### NOT exported from top-level (but exist in subpackage `__all__`):

| Symbol | Defined In | Status |
|--------|-----------|--------|
| `CompletionResponse` | `client.protocol` | Exported from `client/__init__.py` only |
| `ResponseParser` | `models.parsers` | Exported from `models/__init__.py` only |
| `FunctionGemmaResponseParser` | `models.parsers` | Exported from `models/__init__.py` only |
| `discover_tools` | `tools.grail` | Exported from `tools/__init__.py` only |
| `KernelConfig` | `types` | Not exported anywhere |
| `GrammarConfig` | `grammar.config` | Not exported anywhere |

---

## 5. Dead Code, Unused Imports, and Inconsistencies

### Dead Code

| Item | Location | Reason |
|------|----------|--------|
| `KernelConfig` class | `types.py:14-18` | Never used. AgentKernel duplicates its fields. |
| `GrammarConfig` class | `grammar/config.py:16-33` | Never imported or used anywhere. |
| `ConstraintPipeline` class | `grammar/pipeline.py:9-29` | Exported but never instantiated. |
| `ToolResult.output_str` property | `types.py:104-106` | Trivially returns `self.output`. Never called. |
| `RunResult.final_tool_result` field | `types.py:184` | Never populated by kernel. |
| `RunResult.total_usage` field | `types.py:185` | Never populated by kernel. |
| `FunctionGemmaResponseParser` | `models/parsers.py:63-70` | Delegates to QwenResponseParser. Placeholder. |
| `discover_tools()` | `tools/grail.py:44-47` | Stub, always returns `[]`. |
| All exceptions | `exceptions.py` | None raised or caught anywhere. |
| 6 of 7 event types | `events/types.py` | Only `KernelStartEvent` is emitted. |
| `AgentKernel.max_history_messages` | `kernel.py:42` | Declared but never read. |
| `build_client` in `client/factory.py` | `client/factory.py:10-17` | Shadowed by identical function in `client/openai.py`. |

### Unused Imports

| File | Import | Status |
|------|--------|--------|
| `kernel.py:7` | `from typing import Any` | `Any` is not used in kernel.py |
| `kernel.py:5` | `import time` | Never used |
| `events/types.py:5` | `from typing import Any, Union` | `Union` used but could use `|` syntax for consistency |

### Inconsistencies

1. **Duplicate `build_client`**: Exists in both `client/openai.py:89` and `client/factory.py:10`. Different return types (`LLMClient` vs `OpenAICompatibleClient`). `agent.py` imports from `factory`, `__init__.py` imports from `openai`.

2. **`frozen` + `slots` inconsistency**: Most types use `@dataclass(frozen=True, slots=True)` but `RunResult` uses `@dataclass(frozen=True)` without `slots=True`, and `ModelAdapter` uses `@dataclass(frozen=True)` without `slots=True`.

3. **`response_parser` typing**: `ModelAdapter.response_parser` is typed as `Any` with a comment `# ResponseParser`, but `ResponseParser` is defined and importable from `models.parsers`.

4. **Grammar integration broken**: The kernel calls `adapter.grammar_builder(resolved_tools, None)` but the builder signature expects `(list[ToolSchema], Any)`. The `ConstraintPipeline` exists to wrap this but is never used. `Agent.from_bundle()` sets `grammar_builder=lambda t, c: None`.

5. **Observer partially integrated**: Kernel imports all 7 event types but only emits `KernelStartEvent`. No timing, no per-turn events, no end event.

6. **Context passing broken**: `Tool.execute(arguments, context)` expects context, kernel passes `None`, `GrailTool` falls back to `"unknown"` call_id. The tool call's actual ID is available but never forwarded.

---

## 6. Architecture Summary

The codebase implements a straightforward LLM agent loop:

```
Agent (high-level API)
  └── AgentKernel (core loop)
        ├── LLMClient (OpenAI-compatible API calls)
        ├── ModelAdapter (formatting + parsing)
        │     └── ResponseParser (extract tool calls from output)
        ├── Tool[] (executable tools)
        │     └── GrailTool (.pym scripts, stub)
        └── Observer (event system, partially wired)
```

The architecture is clean and well-layered. The main concern is that many features are declared but not connected: grammar constraints, the event system, the exception hierarchy, and several configuration fields exist as scaffolding but are not yet functional. The core `step → parse → execute → loop` path works, but ancillary systems are stubs.
