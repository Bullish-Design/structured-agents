# Remora Integration Guide: structured-agents v0.4 Migration

This guide details how to integrate the newly refactored `structured-agents` v0.4 API
into the Remora library. The refactor eliminates intermediate abstractions (`ModelAdapter`,
`agent.py`) in favor of a cleaner, more direct kernel API.

---

## Executive Summary

### Breaking Changes in structured-agents v0.4

| Removed | Replacement | Impact |
|---------|-------------|--------|
| `structured_agents.agent` module | Direct imports from subpackages | High - multiple Remora files |
| `structured_agents.models.adapter.ModelAdapter` | Direct `response_parser` on `AgentKernel` | High - `kernel_factory.py` |
| `get_response_parser` from `agent.py` | `structured_agents.parsing.get_response_parser` | Medium |
| `load_manifest` from `agent.py` | Needs to be reimplemented or moved | High - `swarm_executor.py` |

### New v0.4 API Surface

```python
from structured_agents import (
    # Core
    AgentKernel,
    
    # Parsing (NEW location)
    ResponseParser,
    DefaultResponseParser,
    get_response_parser,
    
    # Client
    LLMClient,
    OpenAICompatibleClient,
    LiteLLMClient,
    build_client,
    CompletionResponse,
    
    # Grammar (unchanged)
    ConstraintPipeline,
    DecodingConstraint,
    
    # Events (unchanged, now Pydantic models)
    Event, KernelEvent,
    KernelStartEvent, KernelEndEvent,
    ModelRequestEvent, ModelResponseEvent,
    ToolCallEvent, ToolResultEvent, TurnCompleteEvent,
    Observer, NullObserver, CompositeObserver,
    
    # Types (unchanged)
    Message, ToolCall, ToolResult, ToolSchema,
    TokenUsage, StepResult, RunResult,
    
    # Tools (unchanged)
    Tool,
)
```

---

## Affected Files in Remora

| File | Changes Required | Priority |
|------|------------------|----------|
| `src/remora/core/kernel_factory.py` | **Major rewrite** - remove ModelAdapter, update imports | P0 |
| `src/remora/core/swarm_executor.py` | Update imports, handle `load_manifest` removal | P0 |
| `src/remora/core/events.py` | Update imports (cosmetic) | P1 |
| `src/remora/core/event_bus.py` | No changes needed | - |
| `src/remora/core/event_store.py` | No changes needed | - |
| `src/remora/core/chat.py` | No changes needed | - |
| `src/remora/lsp/runner.py` | No changes needed | - |
| `src/remora/core/tools/*.py` | No changes needed | - |
| `pyproject.toml` | Update dependency version | P0 |

---

## Step-by-Step Migration

### Step 1: Update pyproject.toml

```toml
# Before
dependencies = [
    ...
    "structured-agents>=0.3.4",
    "structured-agents[grammar,vllm]>=0.3",
    ...
]

# After
dependencies = [
    ...
    "structured-agents>=0.4.0",
    "structured-agents[grammar,vllm]>=0.4",
    ...
]
```

---

### Step 2: Rewrite `kernel_factory.py`

This is the most critical change. The `ModelAdapter` abstraction has been removed.

#### Before (v0.3)

```python
"""Shared kernel factory for LLM client/adapter/kernel creation."""

from __future__ import annotations
from typing import Any

from structured_agents.agent import get_response_parser
from structured_agents.client import build_client
from structured_agents.grammar.pipeline import ConstraintPipeline
from structured_agents.kernel import AgentKernel
from structured_agents.models.adapter import ModelAdapter


def create_kernel(
    *,
    model_name: str,
    base_url: str,
    api_key: str,
    timeout: float = 300.0,
    tools: list[Any] | None = None,
    observer: Any | None = None,
    grammar_config: Any | None = None,
    client: Any | None = None,
) -> AgentKernel:
    if client is None:
        client = build_client(
            {
                "base_url": base_url,
                "api_key": api_key or "EMPTY",
                "model": model_name,
                "timeout": timeout,
            }
        )

    parser = get_response_parser(model_name)
    pipeline = ConstraintPipeline(grammar_config) if grammar_config else None
    adapter = ModelAdapter(
        name=model_name,
        response_parser=parser,
        constraint_pipeline=pipeline,
    )

    return AgentKernel(
        client=client,
        adapter=adapter,
        tools=tools or [],
        observer=observer,
    )
```

#### After (v0.4)

```python
"""Shared kernel factory for LLM client/kernel creation.

v0.4 API: ModelAdapter removed, response_parser is now a direct kernel parameter.
"""

from __future__ import annotations
from typing import Any

from structured_agents import (
    AgentKernel,
    build_client,
    get_response_parser,
    ConstraintPipeline,
    NullObserver,
)


def create_kernel(
    *,
    model_name: str,
    base_url: str,
    api_key: str,
    timeout: float = 300.0,
    tools: list[Any] | None = None,
    observer: Any | None = None,
    grammar_config: Any | None = None,
    client: Any | None = None,
) -> AgentKernel:
    """Create an ``AgentKernel`` with the standard Remora defaults.

    Parameters
    ----------
    model_name:
        Model identifier (e.g. ``"Qwen/Qwen3-4B"`` or ``"hosted_vllm/Qwen/Qwen3-4B"``).
    base_url:
        OpenAI-compatible API base URL.
    api_key:
        API key (``"EMPTY"`` for local servers).
    timeout:
        HTTP request timeout in seconds.
    tools:
        Tool instances to attach to the kernel.
    observer:
        Event observer (``EventBus``, ``EventStore`` wrapper, etc.).
    grammar_config:
        Optional grammar config for constrained decoding.
    client:
        Pre-built LLM client to reuse. If ``None`` a new one is created.
    """
    if client is None:
        client = build_client(
            {
                "base_url": base_url,
                "api_key": api_key or "EMPTY",
                "model": model_name,
                "timeout": timeout,
            }
        )

    # v0.4: response_parser is now a direct kernel parameter
    response_parser = get_response_parser(model_name)
    
    # v0.4: constraint_pipeline is now a direct kernel parameter
    constraint_pipeline = None
    if grammar_config:
        constraint_pipeline = ConstraintPipeline(grammar_config)

    return AgentKernel(
        client=client,
        response_parser=response_parser,
        tools=tools or [],
        observer=observer or NullObserver(),
        constraint_pipeline=constraint_pipeline,
    )


__all__ = ["create_kernel"]
```

#### Key Changes

1. **Import path**: `get_response_parser` now comes from `structured_agents` (or `structured_agents.parsing`)
2. **No ModelAdapter**: The adapter layer is gone - pass `response_parser` and `constraint_pipeline` directly to `AgentKernel`
3. **Observer default**: Use `NullObserver()` if no observer provided (kernel expects Observer protocol, not `None`)

---

### Step 3: Update `swarm_executor.py`

The main issue is `load_manifest` from `structured_agents.agent` was removed.

#### Before (v0.3)

```python
from structured_agents.agent import load_manifest
from structured_agents.client import build_client
from structured_agents.types import Message
```

#### After (v0.4)

**Reimplement `load_manifest` in Remora**

The `load_manifest` function loaded YAML bundle manifests and performed critical
transformations (path resolution, grammar config parsing). This must be reimplemented
locally with the full logic:

```python
# remora/core/manifest.py (new file)

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

from structured_agents import DecodingConstraint


@dataclass
class BundleManifest:
    """Manifest for an agent bundle.
    
    This is Remora's local replacement for the removed
    structured_agents.agent.AgentManifest.
    """
    name: str = ""
    system_prompt: str = ""
    agents_dir: Path | None = None
    model: str = "qwen"
    grammar_config: DecodingConstraint | None = None
    max_turns: int = 20
    requires_context: bool = True
    limits: dict[str, Any] | None = None


def load_manifest(bundle_path: str | Path) -> BundleManifest:
    """Load a bundle manifest from path.
    
    This function replicates the logic from the removed
    structured_agents.agent.load_manifest, including:
    - Path resolution for agents_dir (relative to bundle)
    - Grammar config parsing (dict -> DecodingConstraint)
    - Model config parsing (string or dict format)
    
    Args:
        bundle_path: Path to bundle directory or bundle.yaml file
        
    Returns:
        Parsed BundleManifest with resolved paths
    """
    path = Path(bundle_path)
    if path.is_dir():
        manifest_path = path / "bundle.yaml"
    else:
        manifest_path = path
    
    bundle_dir = manifest_path.parent
    
    if not manifest_path.exists():
        return BundleManifest()
    
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    
    # Parse initial_context for system_prompt (original format)
    initial_context = data.get("initial_context", {})
    system_prompt = initial_context.get("system_prompt", "")
    # Also support flat system_prompt key
    if not system_prompt:
        system_prompt = data.get("system_prompt", "")
    
    # Parse model config (can be string or dict)
    model_config = data.get("model", "qwen")
    if isinstance(model_config, dict):
        model_name = (
            model_config.get("plugin") 
            or model_config.get("id") 
            or model_config.get("name")
            or "qwen"
        )
    else:
        model_name = str(model_config)
    
    # Parse grammar config -> DecodingConstraint
    grammar_config = None
    grammar_data = data.get("grammar", {})
    if grammar_data:
        grammar_config = DecodingConstraint(
            strategy=grammar_data.get("strategy", "structural_tag"),
            allow_parallel_calls=grammar_data.get("allow_parallel_calls", False),
            send_tools_to_api=grammar_data.get("send_tools_to_api", False),
        )
    
    # Resolve agents_dir relative to bundle directory
    agents_dir_raw = data.get("agents_dir")
    agents_dir = bundle_dir / agents_dir_raw if agents_dir_raw else None
    
    return BundleManifest(
        name=data.get("name", "unnamed"),
        system_prompt=system_prompt,
        agents_dir=agents_dir,
        model=model_name,
        grammar_config=grammar_config,
        max_turns=data.get("max_turns", 20),
        requires_context=data.get("requires_context", True),
        limits=data.get("limits"),
    )


__all__ = ["BundleManifest", "load_manifest"]
```

**Critical Implementation Details:**

1. **`agents_dir` path resolution**: The YAML contains a relative path like `"agents"`.
   This must be joined with `bundle_dir` to get the absolute path.

2. **`grammar_config` parsing**: The YAML contains a dict like `{strategy: "structural_tag"}`.
   This must be converted to a `DecodingConstraint` instance.

3. **`model` parsing**: Can be either a string `"qwen"` or a dict `{plugin: "qwen", id: "..."}`.

4. **`system_prompt` location**: Can be under `initial_context.system_prompt` (old format)
   or directly as `system_prompt` (new format).

#### Updated imports in swarm_executor.py

```python
# Before
from structured_agents.agent import load_manifest
from structured_agents.client import build_client
from structured_agents.types import Message

# After
from structured_agents import build_client, Message
from remora.core.manifest import load_manifest  # Local implementation
```

---

### Step 4: Update `events.py` Imports (Cosmetic)

The events module re-exports structured-agents events. The imports still work but
events are now Pydantic models (frozen) instead of dataclasses.

```python
# No changes required - these imports still work
from structured_agents.events import (
    KernelStartEvent,
    KernelEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    ModelRequestEvent,
    ModelResponseEvent,
    TurnCompleteEvent,
)
```

**Note**: Events are now Pydantic BaseModels with `frozen=True`. This means:
- They have `.model_dump()` and `.model_dump_json()` methods
- They are immutable (assignment raises ValidationError)
- They have stricter validation (`extra="forbid"`)

If your code relies on dataclass-specific features, update accordingly:

```python
# Before (dataclass style)
import dataclasses
event_dict = dataclasses.asdict(event)

# After (Pydantic style)
event_dict = event.model_dump()
```

---

### Step 5: Verify EventBus Compatibility

The `EventBus` implements the `Observer` protocol via `emit()`. The v0.4 Observer
protocol is unchanged:

```python
class Observer(Protocol):
    async def emit(self, event: Event) -> None: ...
```

Your `EventBus` already implements this correctly - no changes needed.

---

## AgentKernel v0.4 API Reference

### Constructor Signature

```python
@dataclass
class AgentKernel:
    client: LLMClient                           # Required: LLM client
    response_parser: ResponseParser = ...        # Parser for model output
    tools: Sequence[Tool] = ()                   # Available tools
    observer: Observer = NullObserver()          # Event observer
    constraint_pipeline: ConstraintPipeline | None = None  # Grammar constraints
    max_history_messages: int = 50               # History truncation
    max_concurrency: int = 1                     # Parallel tool execution
    max_tokens: int = 4096                       # Max completion tokens
    temperature: float = 0.1                     # Sampling temperature
    tool_choice: str = "auto"                    # Tool choice strategy
```

### Key Behavior Changes

1. **Grammar constraints are model-aware**: The kernel checks if the model supports
   grammar constraints via the `hosted_vllm/` prefix. Only `hosted_vllm/*` models
   get `extra_body` with grammar constraints.

2. **LiteLLM routing**: If the model has a provider prefix (`anthropic/`, `openai/`,
   `hosted_vllm/`, etc.), `build_client()` returns `LiteLLMClient` instead of
   `OpenAICompatibleClient`.

3. **Frozen events**: All events are now immutable Pydantic models. Don't try to
   modify event attributes after creation.

---

## Model String Formats

The new `build_client()` recognizes these model formats:

| Format | Client | Example |
|--------|--------|---------|
| `hosted_vllm/Model/Name` | LiteLLMClient (with base_url) | `hosted_vllm/Qwen/Qwen3-4B` |
| `anthropic/model-name` | LiteLLMClient | `anthropic/claude-3-sonnet` |
| `openai/model-name` | LiteLLMClient | `openai/gpt-4o` |
| `gemini/model-name` | LiteLLMClient | `gemini/gemini-pro` |
| `Plain/Model` | OpenAICompatibleClient | `Qwen/Qwen3-4B` |

**For Remora's typical vLLM usage**, you have two options:

1. **Plain model name** (existing behavior): Uses `OpenAICompatibleClient` with `base_url`
   ```python
   model_name = "Qwen/Qwen3-4B"  # Works as before
   ```

2. **Prefixed model name** (new behavior): Uses `LiteLLMClient` with `base_url`
   ```python
   model_name = "hosted_vllm/Qwen/Qwen3-4B"  # Grammar constraints enabled
   ```

**Important**: Grammar constraints (`extra_body`) are only applied when the model
starts with `hosted_vllm/`. Update your config/manifests if you want constraints.

---

## Migration Checklist

- [ ] Update `pyproject.toml` to require `structured-agents>=0.4.0`
- [ ] Rewrite `kernel_factory.py` to remove `ModelAdapter`
- [ ] Create `remora/core/manifest.py` with `load_manifest` implementation
- [ ] Update `swarm_executor.py` imports
- [ ] Verify `EventBus.emit()` still works (it should)
- [ ] Test with both plain model names and `hosted_vllm/` prefixed names
- [ ] Run full test suite
- [ ] Test grammar-constrained decoding with vLLM

---

## Testing the Migration

### Unit Test: kernel_factory

```python
import pytest
from remora.core.kernel_factory import create_kernel


def test_create_kernel_basic():
    """Verify kernel creation with v0.4 API."""
    kernel = create_kernel(
        model_name="Qwen/Qwen3-4B",
        base_url="http://localhost:8000/v1",
        api_key="EMPTY",
    )
    
    assert kernel.client is not None
    assert kernel.response_parser is not None
    assert kernel.constraint_pipeline is None


def test_create_kernel_with_grammar():
    """Verify grammar constraints are applied."""
    from structured_agents.grammar import StructuredOutputModel
    
    grammar_config = StructuredOutputModel(strategy="structural_tag")
    kernel = create_kernel(
        model_name="hosted_vllm/Qwen/Qwen3-4B",
        base_url="http://localhost:8000/v1",
        api_key="EMPTY",
        grammar_config=grammar_config,
    )
    
    assert kernel.constraint_pipeline is not None
```

### Integration Test: Full Agent Turn

```python
import pytest
from remora.core.swarm_executor import SwarmExecutor


@pytest.mark.integration
async def test_swarm_executor_v04():
    """Verify SwarmExecutor works with v0.4 structured-agents."""
    # ... setup ...
    result = await executor.run_agent(node)
    assert result  # Response received
```

---

## Rollback Plan

If migration issues are critical, pin to v0.3:

```toml
[tool.uv.sources]
structured-agents = { git = "https://github.com/Bullish-Design/structured-agents.git", rev = "v0.3.4" }
```

However, v0.4 is a cleaner API and recommended for new development.

---

## Questions & Clarifications

### Q: Does the Observer protocol change?

No. The `Observer` protocol is unchanged:
```python
class Observer(Protocol):
    async def emit(self, event: Event) -> None: ...
```

Your `EventBus` implements this and will continue to work.

### Q: Will my existing tool implementations break?

No. The `Tool` protocol is unchanged:
```python
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...
    async def execute(self, arguments: dict, context: ToolCall | None) -> ToolResult: ...
```

### Q: Do I need to update how I create Messages?

No. `Message` is unchanged (still a frozen dataclass):
```python
Message(role="user", content="Hello")
Message(role="assistant", content="Hi", tool_calls=[...])
```

### Q: What about the events in remora/core/events.py?

Your Remora-specific events (`AgentStartEvent`, `AgentMessageEvent`, etc.) are
unaffected. The structured-agents events you re-export are now Pydantic models,
which is actually more consistent with your Pydantic-based Remora events.

---

## Summary

The v0.4 migration primarily affects `kernel_factory.py`:

1. Remove `ModelAdapter` import and usage
2. Pass `response_parser` and `constraint_pipeline` directly to `AgentKernel`
3. Update import paths for `get_response_parser`
4. Implement `load_manifest` locally (or vendor from v0.3)

The rest of the Remora codebase should work without changes.
