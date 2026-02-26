# Developer Guide: Step 7 — Packaging, Testing, Documentation & Cleanup

This final step handles everything outside the core source: dependency cleanup, test improvements, documentation updates, and stale file removal.

## 1. Fix pyproject.toml — Clean Dependencies

The current `pyproject.toml` has several unused dependencies that bloat the package. We'll clean them up.

### 1.1 Remove Unused Dependencies

Remove from `dependencies`:
- `pydantic>=2.0` — not imported in any v0.3.x source (we use dataclasses)
- `httpx>=0.25` — only used in a broken demo, not in library code
- `jinja2>=3.0` — leftover from old template system, not imported
- `fsdantic` — not imported anywhere
- `vllm>=0.15.1` — the library talks to vLLM over HTTP via the OpenAI client. It never imports vllm. Installing it pulls ~10GB of CUDA wheels
- `xgrammar==0.1.29` — not imported in current source. May be needed later when grammar pipeline is fully wired

### 1.2 Keep Required Dependencies

- `openai>=1.0` — the client uses `openai.AsyncOpenAI`
- `pyyaml>=6.0` — used by `agent.py` for bundle manifest loading
- `grail` — used by `tools/grail.py`

### 1.3 Move to Optional Extras

`vllm` and `xgrammar` should go under `[project.optional-dependencies]` for users who want grammar-constrained decoding:

```toml
[project.optional-dependencies]
grammar = [
    "xgrammar==0.1.29",
]
vllm = [
    "vllm>=0.15.1",
]
```

### 1.4 Clean Up UV Sources

Remove from `[tool.uv.sources]`:
- `fsdantic` entry (dependency removed)
- Commented-out `cairn` line

### 1.5 Clean Up Dev Dependencies

Remove:
- `respx>=0.21` — never used in any test

Add:
- `pyright` for type checking

### 1.6 Update Version

Update version to `0.3.1`.

### 1.7 Final pyproject.toml

```toml
[project]
name = "structured-agents"
version = "0.3.1"
description = "Structured tool orchestration with grammar-constrained LLM outputs"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "openai>=1.0",
    "pyyaml>=6.0",
    "grail",
]

[project.optional-dependencies]
grammar = [
    "xgrammar==0.1.29",
]
vllm = [
    "vllm>=0.15.1",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.uv.sources]
grail = { git = "https://github.com/Bullish-Design/grail.git" }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/structured_agents"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## 2. Add py.typed Marker

Create `src/structured_agents/py.typed` (empty file). This is a PEP 561 marker that tells type checkers this package includes type annotations.

```bash
touch src/structured_agents/py.typed
```

## 3. Update __init__.py

The `__init__.py` must reflect all changes from Steps 1-6. After all refactoring:

- **Removed**: KernelConfig, FunctionGemmaResponseParser, ConstraintPipeline
- **Added**: ResponseParser, discover_tools, exceptions (StructuredAgentsError, KernelError, ToolExecutionError, BundleError, AdapterError)

```python
"""structured-agents - Structured tool orchestration with grammar-constrained LLM outputs."""
from structured_agents.types import (
    Message, ToolCall, ToolResult, ToolSchema, TokenUsage, StepResult, RunResult,
)
from structured_agents.tools import Tool, GrailTool, discover_tools
from structured_agents.models import ModelAdapter, ResponseParser, QwenResponseParser
from structured_agents.grammar import DecodingConstraint
from structured_agents.events import (
    Observer, NullObserver, Event,
    KernelStartEvent, KernelEndEvent, ModelRequestEvent, ModelResponseEvent,
    ToolCallEvent, ToolResultEvent, TurnCompleteEvent,
)
from structured_agents.kernel import AgentKernel
from structured_agents.agent import Agent, AgentManifest, load_manifest
from structured_agents.client import LLMClient, OpenAICompatibleClient, build_client
from structured_agents.exceptions import (
    StructuredAgentsError, KernelError, ToolExecutionError, BundleError, AdapterError,
)
__version__ = "0.3.1"
__all__ = [
    # Types
    "Message", "ToolCall", "ToolResult", "ToolSchema", "TokenUsage", "StepResult", "RunResult",
    # Tools
    "Tool", "GrailTool", "discover_tools",
    # Models
    "ModelAdapter", "ResponseParser", "QwenResponseParser",
    # Grammar
    "DecodingConstraint",
    # Events
    "Observer", "NullObserver", "Event",
    "KernelStartEvent", "KernelEndEvent", "ModelRequestEvent", "ModelResponseEvent",
    "ToolCallEvent", "ToolResultEvent", "TurnCompleteEvent",
    # Core
    "AgentKernel", "Agent", "AgentManifest", "load_manifest",
    # Client
    "LLMClient", "OpenAICompatibleClient", "build_client",
    # Exceptions
    "StructuredAgentsError", "KernelError", "ToolExecutionError", "BundleError", "AdapterError",
]
```

## 4. Create tests/conftest.py

Create shared test fixtures for consistent testing across the test suite.

```python
"""Shared test fixtures for structured-agents."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from structured_agents.types import Message, ToolCall, ToolResult, ToolSchema, TokenUsage
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import QwenResponseParser
from structured_agents.client.protocol import CompletionResponse

@pytest.fixture
def mock_client():
    """A mock LLM client that returns configurable responses."""
    client = AsyncMock()
    client.model = "test-model"
    client.chat_completion = AsyncMock(return_value=CompletionResponse(
        content="Hello", tool_calls=None, usage=None, finish_reason="stop", raw_response={},
    ))
    client.close = AsyncMock()
    return client

@pytest.fixture
def adapter():
    """A real ModelAdapter with QwenResponseParser."""
    return ModelAdapter(name="test", response_parser=QwenResponseParser())

@pytest.fixture
def sample_messages():
    """Standard system + user message pair."""
    return [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="Hello"),
    ]

@pytest.fixture
def sample_tool_schema():
    """A simple tool schema for testing."""
    return ToolSchema(
        name="add_numbers",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
    )

@pytest.fixture
def sample_tool_call():
    """A sample tool call."""
    return ToolCall(id="call_abc123", name="add_numbers", arguments={"x": 1, "y": 2})
```

## 5. Add Critical Test Coverage

### 5.1 Parser Tests — tests/test_models/test_parsers_comprehensive.py

This is the most critical test file — it covers BUG-2 regression (API tool call ID preservation) and edge cases.

```python
"""Comprehensive parser tests — covers BUG-2 regression and edge cases."""
import pytest
from structured_agents.models.parsers import QwenResponseParser

class TestQwenResponseParser:
    def setup_method(self):
        self.parser = QwenResponseParser()
    
    def test_parse_api_tool_calls_preserves_id(self):
        """BUG-2 regression: API-provided tool call IDs must be preserved."""
        tool_calls = [{
            "id": "call_original_123",
            "type": "function",
            "function": {"name": "add", "arguments": '{"x": 1, "y": 2}'},
        }]
        content, parsed = self.parser.parse(None, tool_calls)
        assert content is None
        assert len(parsed) == 1
        assert parsed[0].id == "call_original_123"  # Must be the ORIGINAL id
        assert parsed[0].name == "add"
        assert parsed[0].arguments == {"x": 1, "y": 2}
    
    def test_parse_api_tool_calls_malformed_json(self):
        """Malformed arguments JSON should default to empty dict."""
        tool_calls = [{
            "id": "call_bad",
            "type": "function",
            "function": {"name": "bad_tool", "arguments": "not json{"},
        }]
        content, parsed = self.parser.parse(None, tool_calls)
        assert len(parsed) == 1
        assert parsed[0].arguments == {}
    
    def test_parse_xml_tool_calls(self):
        """XML-embedded tool calls should be parsed correctly."""
        content = '<tool_call>{"name": "add", "arguments": {"x": 1}}</tool_call>'
        result_content, parsed = self.parser.parse(content, None)
        assert result_content is None
        assert len(parsed) == 1
        assert parsed[0].name == "add"
    
    def test_parse_plain_text(self):
        """Plain text without tool calls returns content and empty list."""
        content, parsed = self.parser.parse("Just a response", None)
        assert content == "Just a response"
        assert parsed == []
    
    def test_parse_none_content_no_tools(self):
        """None content and no tools returns None and empty list."""
        content, parsed = self.parser.parse(None, None)
        assert content is None
        assert parsed == []
    
    def test_parse_multiple_api_tool_calls(self):
        """Multiple tool calls should all be parsed with correct IDs."""
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "a", "arguments": "{}"}},
            {"id": "call_2", "type": "function", "function": {"name": "b", "arguments": '{"x": 1}'}},
        ]
        _, parsed = self.parser.parse(None, tool_calls)
        assert len(parsed) == 2
        assert parsed[0].id == "call_1"
        assert parsed[1].id == "call_2"
```

### 5.2 Event Emission Tests — tests/test_kernel/test_kernel_events.py

```python
"""Event emission tests for AgentKernel."""
import pytest
from structured_agents.kernel import AgentKernel
from structured_agents.events import (
    KernelStartEvent, KernelEndEvent, ModelRequestEvent, ModelResponseEvent,
    ToolCallEvent, ToolResultEvent, TurnCompleteEvent,
)
from structured_agents.types import Message, ToolResult

class EventCollector:
    """Collects events for assertion."""
    def __init__(self):
        self.events = []
    
    async def emit(self, event):
        self.events.append(event)

@pytest.mark.asyncio
async def test_all_event_types_emitted(mock_client, adapter, sample_tool_schema):
    """Verify all 7 event types are emitted during a run."""
    collector = EventCollector()
    mock_client.chat_completion.return_value.content = "Done"
    
    kernel = AgentKernel(
        client=mock_client,
        adapter=adapter,
        tools=[],
        observer=collector,
    )
    
    await kernel.run(
        messages=[Message(role="user", content="Hello")],
        max_turns=1,
    )
    
    event_types = [type(e).__name__ for e in collector.events]
    assert "KernelStartEvent" in event_types
    assert "KernelEndEvent" in event_types
    assert "ModelRequestEvent" in event_types
    assert "ModelResponseEvent" in event_types

@pytest.mark.asyncio
async def test_event_ordering(mock_client, adapter):
    """Verify events are emitted in correct order."""
    collector = EventCollector()
    mock_client.chat_completion.return_value.content = "Response"
    
    kernel = AgentKernel(
        client=mock_client,
        adapter=adapter,
        tools=[],
        observer=collector,
    )
    
    await kernel.run(
        messages=[Message(role="user", content="Hi")],
        max_turns=1,
    )
    
    # KernelStart must come before any other event
    assert collector.events[0].__class__.__name__ == "KernelStartEvent"
    # KernelEnd must come last
    assert collector.events[-1].__class__.__name__ == "KernelEndEvent"
```

### 5.3 Error Handling Tests — tests/test_kernel/test_kernel_errors.py

```python
"""Negative path tests for AgentKernel."""
import pytest
from structured_agents.kernel import AgentKernel
from structured_agents.exceptions import ToolExecutionError
from structured_agents.types import Message, ToolCall

@pytest.mark.asyncio
async def test_unknown_tool_name(mock_client, adapter):
    """Unknown tool name should raise ToolExecutionError."""
    from unittest.mock import AsyncMock
    
    tool = AsyncMock()
    tool.name = "nonexistent_tool"
    tool.schema = {"name": "nonexistent_tool", "description": "A tool"}
    tool.execute = AsyncMock(side_effect=Exception("Tool not found"))
    
    mock_client.chat_completion.return_value.content = None
    mock_client.chat_completion.return_value.tool_calls = [
        {"id": "call_1", "type": "function", "function": {"name": "nonexistent_tool", "arguments": "{}"}}
    ]
    
    kernel = AgentKernel(
        client=mock_client,
        adapter=adapter,
        tools=[tool],
    )
    
    with pytest.raises(ToolExecutionError):
        await kernel.run(
            messages=[Message(role="user", content="Use nonexistent_tool")],
            max_turns=1,
        )

@pytest.mark.asyncio
async def test_max_turns_exhaustion(mock_client, adapter):
    """max_turns should limit the number of turns."""
    from structured_agents.client.protocol import CompletionResponse
    
    call_count = 0
    async def count_calls(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return CompletionResponse(
            content="Response " + str(call_count),
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            raw_response={},
        )
    
    mock_client.chat_completion = count_calls
    
    kernel = AgentKernel(
        client=mock_client,
        adapter=adapter,
        tools=[],
    )
    
    result = await kernel.run(
        messages=[Message(role="user", content="Hello")],
        max_turns=3,
    )
    
    assert call_count == 3  # Should stop after 3 turns

@pytest.mark.asyncio
async def test_api_failure_propagates(mock_client, adapter):
    """API call failure should propagate as-is."""
    mock_client.chat_completion = AsyncMock(
        side_effect=Exception("API rate limited")
    )
    
    kernel = AgentKernel(
        client=mock_client,
        adapter=adapter,
        tools=[],
    )
    
    with pytest.raises(Exception, match="API rate limited"):
        await kernel.run(
            messages=[Message(role="user", content="Hello")],
            max_turns=1,
        )
```

### 5.4 Manifest Loading Tests — tests/test_agent/test_load_manifest.py

```python
"""Manifest loading tests for Agent."""
import pytest
import tempfile
import os
from pathlib import Path
from structured_agents.agent import load_manifest, AgentManifest

@pytest.fixture
def manifest_dir():
    """Create a temporary directory with test manifests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def test_load_manifest_system_prompt_extraction(manifest_dir):
    """system_prompt should be extracted from initial_context."""
    manifest = {
        "name": "test_agent",
        "initial_context": [
            {"role": "system", "content": "You are a helpful assistant."}
        ],
        "model": {"name": "gpt-4"},
    }
    
    # Write manifest to file
    manifest_file = manifest_dir / "test_agent.yaml"
    import yaml
    with open(manifest_file, "w") as f:
        yaml.dump(manifest, f)
    
    result = load_manifest(manifest_file)
    assert result.system_prompt == "You are a helpful assistant."

def test_load_manifest_model_name_extraction(manifest_dir):
    """Model name should be extracted from dict format."""
    manifest = {
        "name": "test_agent",
        "initial_context": [],
        "model": {"name": "qwen-max"},
    }
    
    manifest_file = manifest_dir / "test_agent.yaml"
    import yaml
    with open(manifest_file, "w") as f:
        yaml.dump(manifest, f)
    
    result = load_manifest(manifest_file)
    assert result.model == "qwen-max"

def test_load_manifest_path_resolution(manifest_dir):
    """agents_dir should resolve relative tool paths."""
    manifest = {
        "name": "test_agent",
        "initial_context": [],
        "model": "gpt-4",
        "agents_dir": "agents/",
    }
    
    manifest_file = manifest_dir / "test_agent.yaml"
    import yaml
    with open(manifest_file, "w") as f:
        yaml.dump(manifest, f)
    
    result = load_manifest(manifest_file, agents_dir=manifest_dir)
    assert result.agents_dir == manifest_dir / "agents/"

def test_load_manifest_missing_file_raises():
    """Missing manifest file should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_manifest(Path("/nonexistent/manifest.yaml"))

def test_load_manifest_malformed_yaml_raises(manifest_dir):
    """Malformed YAML should raise YAML error."""
    manifest_file = manifest_dir / "bad.yaml"
    with open(manifest_file, "w") as f:
        f.write("invalid: yaml: content: [}")
    
    with pytest.raises(Exception):  # yaml.YAMLError
        load_manifest(manifest_file)
```

## 6. Clean Stale Files

Delete broken demo files and orphaned code that was removed in previous steps.

### 6.1 Delete Broken Demo Files

```bash
rm demo/workspace_agent_demo.py
rm -rf demo/demo_steps/
rm demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md
rm demo/WORKSPACE_AGENT_CONVO.md
rm demo/DEMO_IMPLEMENTATION_PLAN.md
rm demo/DEMO_CONCEPT.md
rm -rf demo/__pycache__/
```

### 6.2 Verify Deleted Files

These files should already be deleted from previous steps, but verify they don't exist:

```bash
ls src/structured_agents/client/factory.py  # Should not exist
ls src/structured_agents/grammar/pipeline.py  # Should not exist
```

If they exist, delete them:
```bash
rm src/structured_agents/client/factory.py
rm src/structured_agents/grammar/pipeline.py
```

## 7. Update events/__init__.py

Add `CompositeObserver` to the events package for users who want to fan out events to multiple observers.

### 7.1 Add CompositeObserver

Add this class to `src/structured_agents/events/__init__.py`:

```python
class CompositeObserver:
    """Fan out events to multiple observers."""
    def __init__(self, observers: list[Observer]) -> None:
        self._observers = observers
    
    async def emit(self, event: Event) -> None:
        for observer in self._observers:
            await observer.emit(event)
```

### 7.2 Update Exports

Add `CompositeObserver` to the `__all__` list in `events/__init__.py`:

```python
__all__ = [
    "Observer",
    "NullObserver", 
    "CompositeObserver",
    "Event",
    "KernelStartEvent",
    "KernelEndEvent",
    "ModelRequestEvent",
    "ModelResponseEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "TurnCompleteEvent",
]
```

## 8. Verification Commands

Run these commands to verify everything works correctly.

### 8.1 Verify Imports

```bash
python -c "from structured_agents import Agent, AgentKernel, ModelAdapter, discover_tools"
```

### 8.2 Run Tests

```bash
pytest tests/ -v
```

### 8.3 Type Check (Optional — requires pyright)

```bash
pyright src/structured_agents/
```

---

## Summary: Files Modified/Created/Deleted Across All 7 Steps

### Created (New Files)
- `src/structured_agents/grammar/__init__.py` — Grammar module with DecodingConstraint
- `src/structured_agents/grammar/json.py` — JSON decoding constraint
- `src/structured_agents/exceptions.py` — Custom exception hierarchy
- `src/structured_agents/events/__init__.py` — Events module with all event types
- `src/structured_agents/py.typed` — PEP 561 type marker
- `tests/conftest.py` — Shared test fixtures
- `tests/test_models/test_parsers_comprehensive.py` — Parser tests
- `tests/test_kernel/test_kernel_events.py` — Event tests
- `tests/test_kernel/test_kernel_errors.py` — Error tests
- `tests/test_agent/test_load_manifest.py` — Manifest tests

### Modified (Existing Files)
- `pyproject.toml` — Cleaned dependencies, added optional extras, updated version
- `src/structured_agents/__init__.py` — Updated exports for all changes
- `src/structured_agents/types.py` — Added TokenUsage
- `src/structured_agents/kernel.py` — Refactored to AgentKernel
- `src/structured_agents/models/__init__.py` — Added ResponseParser, QwenResponseParser
- `src/structured_agents/models/parsers.py` — Implemented QwenResponseParser
- `src/structured_agents/models/adapter.py` — Refactored ModelAdapter
- `src/structured_agents/client/__init__.py` — Refactored client exports
- `src/structured_agents/client/protocol.py` — Added CompletionResponse
- `src/structured_agents/tools/grail.py` — Renamed GrailTool
- `src/structured_agents/tools/__init__.py` — Added discover_tools
- `src/structured_agents/events/__init__.py` — Added CompositeObserver

### Deleted (Removed Files)
- `src/structured_agents/kernel_config.py` — Step 1
- `src/structured_agents/response_parser.py` — Step 3
- `src/structured_agents/grammar/pipeline.py` — Step 6
- `src/structured_agents/client/factory.py` — Step 2
- `src/structured_agents/constraints.py` — Step 6
- `demo/workspace_agent_demo.py` — Step 7
- `demo/demo_steps/` — Step 7
- `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md` — Step 7
- `demo/WORKSPACE_AGENT_CONVO.md` — Step 7
- `demo/DEMO_IMPLEMENTATION_PLAN.md` — Step 7
- `demo/DEMO_CONCEPT.md` — Step 7

### Version Bump
- `0.3.0` → `0.3.1`
