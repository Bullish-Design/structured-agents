# V0.3.1 Refactoring Guide - Detailed Implementation Instructions

**Date:** 2026-02-26  
**Purpose:** Step-by-step instructions for a junior developer to implement all fixes

---

# Phase 1: P0 - Release Blockers (MUST FIX FIRST)

These bugs will crash the library or cause it to produce incorrect results in production.

---

## Step 1.1: Fix BUG-1 - `response.to_dict()` crashes every completion

**File:** `src/structured_agents/client/openai.py`  
**Line:** 82  
**Severity:** CRITICAL - Causes runtime crash on every LLM call

### Current Broken Code:
```python
# Line 82
raw_response=response.to_dict(),
```

### Fix:
Change `to_dict()` to `model_dump()`:

```python
raw_response=response.model_dump(),
```

### Why: The OpenAI SDK's Pydantic v2 response objects use `.model_dump()`, not `.to_dict()`. This will raise `AttributeError` on every LLM call.

---

## Step 1.2: Fix BUG-2 - Parser drops tool call IDs, breaking correlation

**File:** `src/structured_agents/models/parsers.py`  
**Line:** 30  
**Severity:** CRITICAL - Breaks tool call to tool result correlation

### Current Broken Code:
```python
# Line 26-30
for tc in tool_calls:
    if isinstance(tc, dict) and "function" in tc:
        func = tc["function"]
        args = json.loads(func.get("arguments", "{}"))
        parsed.append(ToolCall.create(func["name"], args))  # BUG: generates new ID!
```

### Fix:
Preserve the original ID from the API response:

```python
# Line 26-31
for tc in tool_calls:
    if isinstance(tc, dict) and "function" in tc:
        func = tc["function"]
        args = json.loads(func.get("arguments", "{}"))
        # Preserve the original ID from the API response
        parsed.append(ToolCall(
            id=tc["id"],
            name=func["name"],
            arguments=args
        ))
```

### Why: `ToolCall.create()` generates a **new** UUID, discarding the API-provided `tc["id"]`. The model's response references one ID; the tool result will carry a different one. This breaks the tool-call-to-tool-result correlation chain that OpenAI-compatible APIs rely on.

### Also fix the XML parser path at line 56:
```python
# Line 52-56
if name:
    tool_calls.append(ToolCall(
        id=f"call_{uuid.uuid4().hex[:12]}",  # Use longer ID here too
        name=name,
        arguments=args
    ))
```

---

## Step 1.3: Fix BUG-3 - Tool context always `None`, call_id always "unknown"

**File:** `src/structured_agents/kernel.py`  
**Line:** 117  
**Severity:** CRITICAL - All tool results get "unknown" call_id

### Current Broken Code:
```python
# Line 117
return await tool.execute(tc.arguments, None)  # tc has .id but it's not passed
```

### Fix:
Pass `tc` (the ToolCall object) as context:

```python
# Line 117
return await tool.execute(tc.arguments, tc)
```

### Why: The `ToolCall` object (which has the `.id`) should be passed as context. `GrailTool.execute` then reads `context.call_id if context else "unknown"` - so now it will correctly use the tool call's ID.

---

## Step 1.4: Implement FEAT-1 - Grail integration (discover_tools)

**File:** `src/structured_agents/tools/grail.py`  
**Lines:** 44-47  
**Severity:** CRITICAL - Core feature is non-functional

### Current Broken Code:
```python
# Lines 44-47
def discover_tools(agents_dir: str):
    """Discover .pym tools in a directory."""
    # TODO: implement with grail.load()
    return []
```

### Fix:
Implement the function using grail.load():

```python
# Lines 44-47
def discover_tools(agents_dir: str) -> list[GrailTool]:
    """Discover .pym tools in a directory."""
    import grail
    from pathlib import Path
    
    tools = []
    agents_path = Path(agents_dir)
    
    if not agents_path.exists():
        return tools
    
    for pym_file in agents_path.glob("*.pym"):
        try:
            script = grail.load(str(pym_file))
            tools.append(GrailTool(script))
        except Exception:
            # Skip invalid .pym files
            continue
    
    return tools
```

### Also fix GrailTool schema generation:
The `GrailTool.__init__` hardcodes empty parameters. Update lines 15-19:

```python
# Lines 15-19 - Update GrailTool.__init__
def __init__(self, script: Any, limits: Any = None):
    self._script = script
    self._limits = limits
    
    # Build schema from script's inputs/externals
    parameters = {"type": "object", "properties": {}}
    description = f"Tool: {script.name}"
    
    # Try to introspect script inputs if available
    if hasattr(script, 'inputs'):
        inputs = script.inputs
        if isinstance(inputs, dict):
            parameters["properties"] = inputs
            required = [k for k, v in inputs.get("required", [])] if isinstance(inputs.get("required"), list) else []
            if required:
                parameters["required"] = required
    
    if hasattr(script, 'description'):
        description = script.description
    
    self._schema = ToolSchema(
        name=script.name,
        description=description,
        parameters=parameters,
    )
```

### Type the parameters properly at line 12:
```python
# Line 12 - Add proper typing
def __init__(self, script: grail.GrailScript, limits: grail.Limits | None = None):
```

### Why: The library's stated purpose is structured tool orchestration via Grail `.pym` scripts. Currently `Agent.from_bundle()` will always produce an agent with zero tools.

---

## Step 1.5: Implement FEAT-2 - Grammar-constrained decoding pipeline

**File:** `src/structured_agents/agent.py`  
**Line:** 75  
**Severity:** CRITICAL - Core differentiator is non-functional

### Current Broken Code:
```python
# Line 75
grammar_builder=lambda t, c: None,  # This is a no-op!
```

### Fix:
Wire the ConstraintPipeline in Agent.from_bundle():

```python
# Lines 71-77
tools = discover_tools(str(manifest.agents_dir))

# Wire up grammar constraint pipeline
from structured_agents.grammar.pipeline import ConstraintPipeline
from structured_agents.grammar.config import DecodingConstraint

constraint = manifest.grammar_config or DecodingConstraint()
grammar_pipeline = ConstraintPipeline(
    builder=lambda tools, config: None,  # TODO: wire to xgrammar
    config=constraint
)

adapter = ModelAdapter(
    name=manifest.model,
    grammar_builder=grammar_pipeline.constrain,
    response_parser=QwenResponseParser(),
)
```

### Also fix in kernel.py - pass constraint to grammar_builder:
```python
# Line 78-79 in kernel.py
grammar_constraint = None
if self.adapter.grammar_builder:
    grammar_constraint = self.adapter.grammar_builder(resolved_tools, self.adapter.grammar_config)
```

### Add grammar_config to ModelAdapter:
```python
# In models/adapter.py - add to __init__ and store
grammar_config: DecodingConstraint | None = None
```

### Why: The grammar-constrained decoding is a core differentiator but is currently inert - it does nothing.

---

## Step 1.6: Implement FEAT-3 - Observer/event system

**File:** `src/structured_agents/kernel.py`  
**Lines:** 10-18, 149-155  
**Severity:** CRITICAL - 6 of 7 event types never emitted

### Current State:
Only `KernelStartEvent` is emitted (line 149-155). These are never emitted:
- `ModelRequestEvent` (before API call)
- `ModelResponseEvent` (after API call)
- `ToolCallEvent` (before tool execution)
- `ToolResultEvent` (after tool execution)
- `TurnCompleteEvent` (after each turn)
- `KernelEndEvent` (after loop ends)

### Fix - Add event emissions in kernel.py:

After the API call (around line 91), add:
```python
# After response is received (around line 91)
await self.observer.emit(ModelResponseEvent(
    turn=turn_count,
    duration_ms=int((time.time() - request_start) * 1000),
    content=response.content,
    tool_calls_count=len(tool_calls) if tool_calls else 0,
    usage=response.usage,
))
```

In the step() method, before tool execution (around line 104):
```python
# Before executing tools
for tc in tool_calls:
    await self.observer.emit(ToolCallEvent(
        turn=turn_count,
        tool_name=tc.name,
        call_id=tc.id,
        arguments=tc.arguments,
    ))
```

After tool execution (around line 130):
```python
# After tool results are collected
for result in tool_results:
    await self.observer.emit(ToolResultEvent(
        turn=turn_count,
        tool_name=result.name,
        call_id=result.call_id,
        is_error=result.is_error,
        duration_ms=0,  # TODO: track actual duration
        output_preview=result.output[:100],
    ))
```

Add at the start of the run() loop (before line 160):
```python
# Before each step in the loop
await self.observer.emit(ModelRequestEvent(
    turn=turn_count,
    messages_count=len(messages),
    tools_count=len(resolved_tools),
    model=self.client.model,
))
```

At the end of the run() method (after line 195):
```python
# Before returning RunResult
await self.observer.emit(KernelEndEvent(
    turn_count=turn_count,
    termination_reason=termination_reason,
    total_duration_ms=int((time.time() - start_time) * 1000),
))

await self.observer.emit(TurnCompleteEvent(
    turn=turn_count,
    tool_calls_count=len(step_result.tool_calls),
    tool_results_count=len(step_result.tool_results),
    errors_count=sum(1 for r in step_result.tool_results if r.is_error),
))
```

Note: You'll need to track `start_time` at the beginning of `run()`:
```python
start_time = time.time()
```

### Also add ModelRequestEvent to imports:
```python
# Already imported at lines 10-18, but verify they're all used
```

### Why: The observer/event system only emits 1 of 7 event types. This is dead code for most users.

---

## Step 1.7: Fix DEP-1 - Remove vllm from hard dependencies

**File:** `pyproject.toml`  
**Section:** dependencies

### Current Broken Code:
```toml
dependencies = [
    ...
    "vllm>=0.15.1",
    ...
]
```

### Fix:
Remove vllm from dependencies, or move to an optional extra:

```toml
[project.optional-dependencies]
vllm = ["vllm>=0.15.1"]

[project]
dependencies = [
    ...
    # vllm removed - use `pip install structured-agents[vllm]` if needed
    ...
]
```

### Why: The library communicates with vLLM over HTTP via the OpenAI-compatible API. It never imports vllm. Installing vllm pulls ~10GB of CUDA wheels.

---

# Phase 2: P1 - Production Readiness

---

## Step 2.1: Fix ARCH-1 - Duplicate build_client

**Files:** 
- `src/structured_agents/client/factory.py` 
- `src/structured_agents/client/openai.py:89-96`

### Current State:
Two identical `build_client` functions exist:
- `client/factory.py:10-17` 
- `client/openai.py:89-96`

### Fix:
Delete `src/structured_agents/client/factory.py` entirely (or make it import from openai.py):

```python
# In client/factory.py - replace content with:
from structured_agents.client.openai import build_client

__all__ = ["build_client"]
```

### Verify agent.py imports from the right place:
```python
# agent.py line 10 - ensure it imports from openai.py
from structured_agents.client.openai import build_client
```

---

## Step 2.2: Fix ARCH-2 - ModelAdapter.__post_init__ mutates frozen dataclass

**File:** `src/structured_agents/models/adapter.py`  
**Lines:** 21-24

### Current Broken Code:
```python
@dataclass(frozen=True)
class ModelAdapter:
    name: str
    response_parser: Any
    grammar_builder: Callable[..., Any] = None
    format_messages: Callable[..., Any] = None
    format_tools: Callable[..., Any] = None
    
    def __post_init__(self):
        object.__setattr__(self, 'format_messages', self._default_format_messages)
        object.__setattr__(self, 'format_tools', self._default_format_tools)
```

### Fix:
Use field factories instead:

```python
@dataclass
class ModelAdapter:
    name: str
    response_parser: Any
    grammar_builder: Callable[..., Any] = None
    grammar_config: DecodingConstraint | None = None
    format_messages: Callable[..., list[dict[str, Any]]] = field(default_factory=_default_format_messages)
    format_tools: Callable[..., list[dict[str, Any]]] = field(default_factory=_default_format_tools)

def _default_format_messages(messages: list[Message], tools: list[ToolSchema]) -> list[dict[str, Any]]:
    # ... implementation
    pass

def _default_format_tools(tools: list[ToolSchema]) -> list[dict[str, Any]]:
    # ... implementation
    pass
```

---

## Step 2.3: Fix ARCH-3 - Default message formatter uses str()

**File:** `src/structured_agents/models/adapter.py`  
**Lines:** 34-37

### Current Broken Code:
```python
def _default_format_messages(self, messages: list[Message], tools: list[ToolSchema]):
    result = [m.to_openai_format() for m in messages]
    if tools:
        tool_descriptions = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        result.append({
            "role": "system",
            "content": f"Available tools: {str(tools)}"  # BUG: uses str()
        })
    return result
```

### Fix:
Use JSON serialization:

```python
def _default_format_messages(self, messages: list[Message], tools: list[ToolSchema]):
    import json
    result = [m.to_openai_format() for m in messages]
    if tools:
        tool_list = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]
        result.append({
            "role": "system", 
            "content": f"Available tools:\n{json.dumps(tool_list, indent=2)}"
        })
    return result
```

---

## Step 2.4: Fix ARCH-5 - Cache _tool_map()

**File:** `src/structured_agents/kernel.py`  
**Lines:** 48-49, 63, 106

### Current Broken Code:
```python
# Line 48-49 - called multiple times per step
def _tool_map(self) -> dict[str, Tool]:
    return {t.schema.name: t for t in self.tools}
```

### Fix:
Cache as an instance attribute:

```python
# Add to AgentKernel __init__:
tool_map: dict[str, Tool] = field(default_factory=dict, init=False)

def _rebuild_tool_map(self) -> None:
    self.tool_map = {t.schema.name: t for t in self.tools}

# Call _rebuild_tool_map() in __post_init__ or when tools change
# Then replace self._tool_map() with self.tool_map throughout
```

Or simpler - compute once per step:

```python
# In step() method, compute once:
tool_map = {t.schema.name: t for t in self.tools}
# Then use 'tool_map' variable instead of self._tool_map() calls
```

---

## Step 2.5: Fix TYPE-1 through TYPE-8 - Type Safety

### TYPE-1: script: Any, limits: Any
**File:** `src/structured_agents/tools/grail.py:12`

```python
# Change from:
def __init__(self, script: Any, limits: Any = None):

# To (after confirming grail types):
def __init__(self, script: grail.GrailScript, limits: grail.Limits | None = None):
```

### TYPE-2: context: Any in Tool.execute
**File:** `src/structured_agents/tools/protocol.py:14`

Create a ToolCallContext dataclass:
```python
# In tools/protocol.py or types.py:
@dataclass(frozen=True)
class ToolCallContext:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]

# Update Tool protocol:
def execute(self, arguments: dict[str, Any], context: ToolCallContext | None) -> ToolResult: ...
```

### TYPE-3: response_parser: Any
**File:** `src/structured_agents/models/adapter.py:15`

```python
# Change from:
response_parser: Any

# To:
response_parser: ResponseParser
```

### TYPE-4: grammar_builder 2nd arg Any
**File:** `src/structured_agents/models/adapter.py:14`

```python
# Change from:
grammar_builder: Callable[[list[ToolSchema], Any], dict[str, Any] | None] = None

# To:
grammar_builder: Callable[[list[ToolSchema], DecodingConstraint | None], dict[str, Any] | None] = None
```

### TYPE-5: tools: list[Tool] invariant
**File:** `src/structured_agents/kernel.py:40`

```python
# Change from:
tools: list[Tool] = field(default_factory=list)

# To:
tools: Sequence[Tool] = field(default_factory=list)
```

### TYPE-6: OpenAI SDK type mismatches
**File:** `src/structured_agents/client/openai.py:43-45`

Use proper types from openai SDK:
```python
from openai.types.responses import ResponseFunctionToolCall
from openai.types import ChatCompletionMessageParam, ChatCompletionToolParam

# Change message typing:
messages: list[ChatCompletionMessageParam]
tools: list[ChatCompletionToolParam] | None

# For tool_choice, use:
from openai.types import ChatCompletionToolChoiceOption

tool_choice: ChatCompletionToolChoiceOption = "auto"
```

### TYPE-7: RunResult missing slots=True
**File:** `src/structured_agents/types.py:176`

```python
# Change from:
@dataclass(frozen=True)
class RunResult:

# To:
@dataclass(frozen=True, slots=True)
class RunResult:
```

### TYPE-8: Variable shadowing in parser
**File:** `src/structured_agents/models/parsers.py:35`

Fix by using a different variable name:
```python
# Change from:
if content:
    tool_calls = self._parse_xml_tool_calls(content)  # shadows parameter!
    if tool_calls:
        return None, tool_calls

# To:
if content:
    parsed_xml_calls = self._parse_xml_tool_calls(content)
    if parsed_xml_calls:
        return None, parsed_xml_calls
```

---

## Step 2.6: Dead Code Removal

### DEAD-1: KernelConfig (types.py:14-18)
Remove the unused KernelConfig class:
```python
# Delete lines 14-18 in types.py
class KernelConfig:
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_choice: str = "auto"
    max_concurrency: int = 1
```

### DEAD-2: GrammarConfig (grammar/config.py:16-33)
Either remove GrammarConfig or remove DecodingConstraint and keep one. Recommend removing GrammarConfig:
```python
# Delete lines 16-33 in grammar/config.py
@dataclass(frozen=True, slots=True)
class GrammarConfig:
    ...
```

### DEAD-3: ToolResult.output_str (types.py:104-106)
Remove the identity property:
```python
# Delete lines 104-106
@property
def output_str(self) -> str:
    """Output as string."""
    return self.output
```

### DEAD-4: FunctionGemmaResponseParser (parsers.py:63-70)
Either remove or implement distinct behavior. If keeping, fix the wasteful instantiation:
```python
# Change to use a class attribute
class FunctionGemmaResponseParser:
    _parser = QwenResponseParser()
    
    def parse(self, content, tool_calls):
        return self._parser.parse(content, tool_calls)
```

### DEAD-5: Exception hierarchy (exceptions.py)
Either implement usage or remove. Recommend removing unused exceptions:
```python
# Keep only:
class StructuredAgentsError(Exception):
    """Base exception for structured-agents."""
    pass

# Remove or implement: KernelError, ToolExecutionError, PluginError, BackendError
```

### DEAD-6: max_history_messages unused (kernel.py:43)
Either implement or remove. To implement:
```python
# In run() method, before appending new messages:
if len(messages) > self.max_history_messages:
    # Trim oldest messages (keep system prompt)
    messages = [messages[0]] + messages[-(self.max_history_messages-1):]
```

### DEAD-7: **overrides parameter (agent.py:67)
Either implement or remove. To implement:
```python
# In from_bundle(), apply overrides to manifest or config
for key, value in overrides.items():
    if hasattr(manifest, key):
        object.__setattr__(manifest, key, value)
```

---

# Phase 3: P2 - Quality Improvements

---

## Step 3.1: Test Suite Improvements

### TEST-1: Add conftest.py
Create `tests/conftest.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from structured_agents.types import Message, ToolCall, ToolResult
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import QwenResponseParser
from structured_agents.tools.grail import GrailTool

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.chat_completion = AsyncMock()
    return client

@pytest.fixture
def mock_adapter():
    return ModelAdapter(
        name="test",
        response_parser=QwenResponseParser(),
        grammar_builder=None,
    )

@pytest.fixture
def sample_messages():
    return [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="Hello"),
    ]

@pytest.fixture
def grail_tool_fixture():
    # Use tests/fixtures/grail_tools/ if available
    pass
```

### TEST-2: Add parser unit tests
Create `tests/test_models/test_parsers.py`:

```python
import pytest
from structured_agents.models.parsers import QwenResponseParser

class TestQwenResponseParser:
    def test_parse_xml_tool_calls_single(self):
        parser = QwenResponseParser()
        content = '<tool_call>{"name": "add", "arguments": {"x": 1, "y": 2}}</tool_call>'
        result, tool_calls = parser.parse(content, None)
        assert result is None
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "add"
        assert tool_calls[0].arguments == {"x": 1, "y": 2}

    def test_parse_xml_tool_calls_multiple(self):
        # Test multiple tool calls
        pass

    def test_parse_malformed_json(self):
        # Test error handling
        pass
```

### TEST-3: Fix load_manifest bug
**File:** `src/structured_agents/agent.py:44`

```python
# Current (buggy):
system_prompt=data.get("system_prompt", ""),

# Fix - read from correct path:
system_prompt=data.get("initial_context", {}).get("system_prompt", ""),
```

---

## Step 3.2: Documentation Updates

### DOC-1: Rewrite README.md examples

Replace all pre-v0.3.0 API examples with v0.3.0 API:

```python
# OLD (broken):
from structured_agents import KernelConfig, AgentKernel, FunctionGemmaPlugin
kernel = AgentKernel(config=KernelConfig(...), plugin=plugin, tool_source=...)

# NEW (correct):
from structured_agents import Agent, build_client, QwenResponseParser, ModelAdapter
client = build_client({"base_url": "http://localhost:8000/v1", "model": "qwen"})
adapter = ModelAdapter(name="qwen", response_parser=QwenResponseParser())
agent = Agent(kernel, manifest)
result = await agent.run("Your message here")
```

### DOC-2: Update ARCHITECTURE.md

Either update to reflect actual v0.3.0 architecture or remove the document entirely if it causes confusion.

---

## Step 3.3: Packaging

### PKG-1: Add py.typed marker

Create `src/structured_agents/py.typed`:
```
# Marker file for PEP 561 - indicates this is a typed package
```

### PKG-2: Export KernelConfig

Add to `src/structured_agents/__init__.py`:
```python
from structured_agents.types import KernelConfig
```

### PKG-3: Export exceptions

Add to `src/structured_agents/__init__.py`:
```python
from structured_agents.exceptions import StructuredAgentsError
```

### PKG-4: Pass observer to kernel in from_bundle

**File:** `src/structured_agents/agent.py:87-93`

```python
# Change from:
kernel = AgentKernel(
    client=client,
    adapter=adapter,
    tools=tools,
)

# To:
kernel = AgentKernel(
    client=client,
    adapter=adapter,
    tools=tools,
    observer=self.observer,  # Pass the agent's observer
)
```

---

# Phase 4: Additional Fixes

---

## Step 4.1: Module-Level Issues

### MOD-3: json.loads without error handling
**File:** `src/structured_agents/models/parsers.py:29`

```python
# Current:
args = json.loads(func.get("arguments", "{}"))

# Fix:
try:
    args = json.loads(func.get("arguments", "{}"))
except json.JSONDecodeError:
    args = {}
```

### MOD-4: tool_choice="none" with no tools
**File:** `src/structured_agents/kernel.py:87`

```python
# Current:
tool_choice=self.tool_choice if resolved_tools else "none",

# Fix - omit the parameter when no tools:
tool_choice = self.tool_choice if resolved_tools else None,
# Then pass only if not None:
tool_choice=tool_choice if tool_choice else None,
```

### MOD-8: Short tool call IDs
**File:** `src/structured_agents/types.py:89`

```python
# Current:
id=f"call_{uuid.uuid4().hex[:8]}",

# Fix:
id=f"call_{uuid.uuid4().hex[:12]}",
```

### MOD-9: No ErrorEvent
**File:** `src/structured_agents/events/types.py`

Add new event type:
```python
@dataclass(frozen=True)
class ErrorEvent:
    phase: str  # "model_request", "tool_execution", "parsing", etc.
    error_type: str
    error_message: str
    turn: int | None = None
```

---

## Step 4.2: Clean stale demo files

Remove broken demo files:
- `demo/workspace_agent_demo.py`
- `demo/demo_steps/` directory
- `demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md`
- `demo/WORKSPACE_AGENT_CONVO.md`
- `demo/DEMO_IMPLEMENTATION_PLAN.md`
- `demo/DEMO_CONCEPT.md`
- `demo/__pycache__/`

---

# Verification Commands

After implementing fixes, run these commands to verify:

```bash
# Type checking
cd /home/andrew/Documents/Projects/structured-agents
python -m pyright src/structured_agents/

# Run tests
pytest tests/ -v

# Verify imports work
python -c "from structured_agents import Agent, AgentKernel, ModelAdapter"
```

---

# Summary of Files to Modify

| File | Changes |
|------|---------|
| `src/structured_agents/client/openai.py` | BUG-1 fix, ARCH-1 (keep one build_client), TYPE-6 |
| `src/structured_agents/models/parsers.py` | BUG-2 fix, DEAD-4, MOD-3, TYPE-8 |
| `src/structured_agents/kernel.py` | BUG-3 fix, FEAT-3 implementation, ARCH-5, MOD-4, MOD-5 |
| `src/structured_agents/tools/grail.py` | FEAT-1 implementation, TYPE-1 |
| `src/structured_agents/agent.py` | FEAT-2, TEST-3, PKG-4, ARCH-4, ARCH-6, MOD-6 |
| `src/structured_agents/types.py` | DEAD-1, DEAD-3, MOD-8, TYPE-7 |
| `src/structured_agents/grammar/config.py` | DEAD-2 |
| `src/structured_agents/models/adapter.py` | ARCH-2, ARCH-3, TYPE-3, TYPE-4 |
| `src/structured_agents/events/types.py` | MOD-9 |
| `pyproject.toml` | DEP-1, DEP-2, DEP-3 |
| `tests/conftest.py` | TEST-3 (new file) |
| `README.md` | DOC-1 |
| `src/structured_agents/py.typed` | PKG-1 (new file) |
