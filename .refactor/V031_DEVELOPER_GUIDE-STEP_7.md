You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_7.md
This is Step 7 of 7: "Packaging, Testing, Documentation & Cleanup"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
This final step handles everything outside the core source: dependency cleanup, test improvements, documentation updates, and stale file removal.
## Current state of pyproject.toml:
```toml
[project]
name = "structured-agents"
version = "0.3.0"
description = "Structured tool orchestration with grammar-constrained LLM outputs"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.0",
    "httpx>=0.25",
    "openai>=1.0",
    "pyyaml>=6.0",
    "jinja2>=3.0",
    "grail",
    "fsdantic",
    "xgrammar==0.1.29",
    "vllm>=0.15.1",
]
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
]
[tool.uv.sources]
fsdantic = { git = "https://github.com/Bullish-Design/fsdantic.git" }
grail = { git = "https://github.com/Bullish-Design/grail.git" }
#cairn = { git = "https://github.com/Bullish-Design/cairn.git" }
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[tool.hatch.build.targets.wheel]
packages = ["src/structured_agents"]
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```
## Current state of __init__.py (after Steps 1-6):
After all previous steps, the __init__.py needs to be updated to match the new module structure:
- KernelConfig removed (Step 1)
- FunctionGemmaResponseParser removed (Step 3)
- ConstraintPipeline removed (Step 6)
- ResponseParser added to exports (Step 3)
- Exceptions added to exports (Step 1)
- discover_tools added to exports
## What the guide should instruct the developer to do:
### 1. Fix pyproject.toml — Clean dependencies:
**Remove** these unused dependencies:
- `pydantic>=2.0` — not imported in any v0.3.x source (we use dataclasses)
- `httpx>=0.25` — only used in a broken demo, not in library code
- `jinja2>=3.0` — leftover from old template system, not imported
- `fsdantic` — not imported anywhere
- `vllm>=0.15.1` — the library talks to vLLM over HTTP via the OpenAI client. It never imports vllm. Installing it pulls ~10GB of CUDA wheels.
- `xgrammar==0.1.29` — not imported in current source. May be needed later when grammar pipeline is fully wired.
**Keep** these:
- `openai>=1.0` — the client uses `openai.AsyncOpenAI`
- `pyyaml>=6.0` — used by `agent.py` for bundle manifest loading
- `grail` — used by `tools/grail.py`
**Move to optional extras:**
- `vllm` and `xgrammar` should go under `[project.optional-dependencies]` for users who want grammar-constrained decoding
**Remove** from `[tool.uv.sources]`:
- `fsdantic` entry (dependency removed)
- Commented-out `cairn` line
**Remove** from dev dependencies:
- `respx>=0.21` — never used in any test
**Add** to dev dependencies:
- `pyright` or `mypy` for type checking
**Update version** to `0.3.1`.
Final pyproject.toml:
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
### 2. Add py.typed marker:
Create `src/structured_agents/py.typed` (empty file). This is a PEP 561 marker that tells type checkers this package includes type annotations.
### 3. Update __init__.py:
Show the complete final __init__.py reflecting all changes from Steps 1-6:
- Remove: KernelConfig, FunctionGemmaResponseParser, ConstraintPipeline
- Add: ResponseParser, discover_tools, exceptions (StructuredAgentsError, KernelError, ToolExecutionError, BundleError, AdapterError)
- Update version to 0.3.1
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
### 4. Create tests/conftest.py:
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
### 5. Add critical test coverage:
**tests/test_models/test_parsers_comprehensive.py** — Parser tests including:
- API tool_calls parsing with ID preservation (BUG-2 regression test)
- XML tool_call parsing
- Malformed JSON handling
- Mixed content and tool calls
- Empty/None inputs
**tests/test_kernel/test_kernel_events.py** — Event emission tests:
- Verify all 7 event types are emitted during a run
- Verify event ordering
- Verify event data is correct
**tests/test_kernel/test_kernel_errors.py** — Negative path tests:
- Unknown tool name handling
- max_turns exhaustion
- Tool execution failure
- API call failure
**tests/test_agent/test_load_manifest.py** — Manifest loading tests:
- Correct system_prompt extraction from initial_context
- Model name extraction from dict format
- Path resolution for agents_dir
- Missing/malformed YAML handling
Show concrete test code for the parsers test file (most critical):
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
### 6. Clean stale files:
Delete these files/directories:
- `demo/workspace_agent_demo.py` — imports from non-existent modules
- `demo/demo_steps/` — entire directory, all broken
- `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md` — planning doc
- `demo/WORKSPACE_AGENT_CONVO.md` — conversation log
- `demo/DEMO_IMPLEMENTATION_PLAN.md` — planning doc
- `demo/DEMO_CONCEPT.md` — planning doc
- `demo/__pycache__/` — bytecode cache
- `src/structured_agents/client/factory.py` — already deleted in Step 2, confirm
- `src/structured_agents/grammar/pipeline.py` — already deleted in Step 6, confirm
### 7. Update events/__init__.py:
Add CompositeObserver to the events package for users who want multiple observers:
```python
class CompositeObserver:
    """Fan out events to multiple observers."""
    def __init__(self, observers: list[Observer]) -> None:
        self._observers = observers
    async def emit(self, event: Event) -> None:
        for observer in self._observers:
            await observer.emit(event)
```
Add to events/__init__.py exports.
### 8. Verification commands:
```bash
# Verify imports work
python -c "from structured_agents import Agent, AgentKernel, ModelAdapter, discover_tools"
# Run tests
pytest tests/ -v
# Type check (if pyright installed)
pyright src/structured_agents/
```
## IMPORTANT NOTES:
- Show COMPLETE files for pyproject.toml, __init__.py, conftest.py, and the parser test file.
- For other test files, show the structure and key tests but don't need to be as exhaustive.
- The cleanup section should list exact commands to delete stale files.
- Include a final summary section that lists all files modified/created/deleted across all 7 steps.
Return a brief (2-3 sentence) confirmation when done.