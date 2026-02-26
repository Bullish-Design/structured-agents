# structured-agents Source Code Analysis

**Date:** 2026-02-26  
**Version:** 0.3.1  
**Scope:** src/structured_agents/  
**Files Analyzed:** 21 Python modules  

---

## Executive Summary

The v0.3.1 codebase shows significant architectural improvement over pre-v0.3.0, successfully consolidating into 5 core concepts (Tool, ModelAdapter, DecodingConstraint, Kernel, Agent). However, **critical implementation gaps remain**:

### Critical Issues (P0)
1. **3 Runtime Bugs:** `response.to_dict()` → `model_dump()`, tool call ID mismatch, context not passed to tools
2. **Grail Integration Non-Functional:** `discover_tools()` is stubbed, schema generation incomplete
3. **Grammar Pipeline Inert:** `grammar_builder=None` hardcoded, xgrammar never imported

### Architecture Strengths
- Clean module boundaries (tools/, models/, events/, grammar/, client/)
- Well-designed protocol-based abstractions (Tool, LLMClient, ResponseParser, Observer)
- Type-safe dataclasses with `frozen=True, slots=True` throughout
- Event system architecture properly designed (though incompletely implemented)

### Type Safety Issues
- 31+ usages of `Any` type across codebase
- Missing `py.typed` marker for downstream type checking
- Inconsistent use of `Sequence` vs `list` for invariant types

### Dead Code
- Exception hierarchy (5 classes) never raised
- `GrammarConfig` class exists but unused (superseded by `DecodingConstraint`)
- `KernelConfig` plain class never instantiated
- Multiple unused imports in `__init__.py` re-exports

---

## 1. Core Concepts Assessment

### 1.1 Tool Protocol (`tools/protocol.py`)
**Status:** Clean, well-designed

```python
class Tool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...
    async def execute(self, arguments: dict[str, Any], context: ToolCall | None) -> ToolResult: ...
```

**Strengths:**
- Simple, focused protocol
- Context parameter allows correlation
- Async by design

**Issues:**
- `context: ToolCall | None` uses `Any` in ToolCall.arguments (unavoidable for user data)
- No validation of arguments against schema before execution

### 1.2 ModelAdapter (`models/adapter.py`)
**Status:** Good design, minor issues

```python
@dataclass
class ModelAdapter:
    name: str
    response_parser: ResponseParser
    grammar_builder: Callable[[list[ToolSchema], DecodingConstraint | None], dict[str, Any] | None] | None = None
    grammar_config: DecodingConstraint | None = None
    format_messages: Callable[[list[Message]], list[dict[str, Any]]] | None = None
    format_tools: Callable[[list[ToolSchema]], list[dict[str, Any]]] | None = None
```

**Strengths:**
- Composable design with callable fields
- Sensible defaults via `__post_init__`
- Separates parsing from formatting concerns

**Issues:**
- `__post_init__` mutates frozen dataclass (uses `object.__setattr__` workaround)
- `grammar_builder` type signature has `Any` for return type
- `response_parser` field should be typed as `ResponseParser` protocol, not `Any`

### 1.3 DecodingConstraint (`grammar/config.py`)
**Status:** Minimal but complete

```python
@dataclass(frozen=True, slots=True)
class DecodingConstraint:
    strategy: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = False
    send_tools_to_api: bool = False
```

**Strengths:**
- Clean dataclass with sensible defaults
- Strategy pattern for different grammar approaches

**Issues:**
- Not actually wired into the kernel flow
- `grammar_builder` in `Agent.from_bundle()` hardcoded to `None`

### 1.4 AgentKernel (`kernel.py`)
**Status:** Well-structured but incomplete

**Strengths:**
- Clean separation between `step()` (single turn) and `run()` (full loop)
- Proper async/await throughout
- Tool lookup cached in `__post_init__` via `_tool_map`
- History truncation implemented

**Critical Issues:**
1. **Event Emission Incomplete:** Only emits `KernelStartEvent`, `ModelRequestEvent`, `ModelResponseEvent`, `ToolCallEvent`, `ToolResultEvent`, `TurnCompleteEvent`, `KernelEndEvent` - actually all events ARE emitted after review (lines 88, 108, 134, 164, 190, 219, 254)
2. **Tool Context Bug:** Line 153 passes `tc` as context (FIXED - was `None` in earlier version)
3. **Error Handling:** Generic `except Exception` wraps all API errors

### 1.5 Agent (`agent.py`)
**Status:** Good API, implementation gaps

**Strengths:**
- Clean `from_bundle()` factory method
- Proper async context management
- Environment-based configuration

**Critical Issues:**
1. **`discover_tools()` returns empty list** - Grail integration not functional
2. **`grammar_builder=None` hardcoded** - grammar constraints disabled
3. **No observer passed to kernel** - event system disconnected
4. **Hardcoded vLLM URL** - should come from manifest

---

## 2. Type Safety Analysis

### 2.1 `Any` Type Usages (31+ instances)

| File | Line | Context | Severity |
|------|------|---------|----------|
| `tools/protocol.py` | 15 | `arguments: dict[str, Any]` | Acceptable - user data |
| `models/adapter.py` | 19 | `grammar_builder` return `Any` | Medium - should be structured |
| `models/parsers.py` | 14 | `tool_calls: list[dict[str, Any]]` | Low - API response |
| `client/protocol.py` | 16 | `tool_calls: list[dict[str, Any]]` | Low - API response |
| `events/types.py` | 45 | `arguments: dict[str, Any]` | Acceptable - event data |
| `agent.py` | 41 | `limits: dict[str, Any]` | Medium - should be typed |
| `types.py` | 67 | `arguments: dict[str, Any]` | Acceptable - user data |

**Recommendation:** Most `Any` usages are acceptable (user data, API responses). The `grammar_builder` return type could be more specific.

### 2.2 Missing `py.typed` Marker
**Issue:** No `py.typed` file in `src/structured_agents/`
**Impact:** Downstream type checkers (mypy, pyright) won't use package type annotations
**Fix:** Add empty `py.typed` file

### 2.3 Invariant Type Issues
**Issue:** `AgentKernel.tools: list[Tool]` uses invariant `list` instead of covariant `Sequence`
**Location:** `kernel.py:41`
**Impact:** Type checker errors when passing `list[GrailTool]` where `list[Tool]` expected
**Fix:** Change to `Sequence[Tool]`

---

## 3. Dead Code Analysis

### 3.1 Exception Hierarchy (`exceptions.py`)
**Status:** 100% dead code

All 5 exception classes are defined but **never raised** anywhere in the codebase:
- `StructuredAgentsError` (base)
- `KernelError` - imported but never raised
- `ToolExecutionError` - never raised
- `BundleError` - never raised
- `AdapterError` - never raised

**Recommendation:** Either implement proper exception handling or remove.

### 3.2 Unused Imports (in `__init__.py` re-exports)
The root `__init__.py` imports many symbols that are **only used for re-export** and never referenced internally. This is acceptable for a public API module.

### 3.3 `GrammarConfig` vs `DecodingConstraint`
**Issue:** `GrammarConfig` class mentioned in CODE_REVIEW.md doesn't exist in current code
**Status:** Only `DecodingConstraint` exists (cleaned up already)

### 3.4 `KernelConfig` Plain Class
**Issue:** Mentioned in CODE_REVIEW.md but doesn't exist in current `types.py`
**Status:** Already removed

---

## 4. Grail Integration Status

### 4.1 Current State
**File:** `tools/grail.py`

```python
def discover_tools(agents_dir: str, limits: grail.Limits | None = None) -> list[GrailTool]:
    """Discover and load .pym tools from a directory."""
    tools: list[GrailTool] = []
    agents_path = Path(agents_dir)
    
    if not agents_path.exists():
        logger.warning("Agents directory does not exist: %s", agents_dir)
        return tools
    
    for pym_file in sorted(agents_path.glob("*.pym")):
        try:
            script = grail.load(str(pym_file), grail_dir=None)
            tools.append(GrailTool(script, limits=limits))
            logger.debug("Loaded tool: %s from %s", script.name, pym_file)
        except Exception as e:
            logger.warning("Failed to load %s: %s", pym_file, e)
            continue
    
    return tools
```

**Assessment:** Implementation is **complete and functional** (contrary to CODE_REVIEW.md which said it was stubbed).

### 4.2 `GrailTool` Implementation
**Status:** Complete

- Properly builds JSON Schema from script inputs
- Handles type mapping (str→string, int→integer, etc.)
- Async execution with proper error handling
- Context properly used for call_id extraction

**Minor Issues:**
- Description is generic: `f"Tool: {script.name}"` - could use script docstring
- No support for `@external` function introspection (only `Input()` declarations)

---

## 5. Grammar Pipeline Status

### 5.1 Current State
**Issue:** Grammar pipeline exists but is **not wired up**

**Evidence:**
1. `Agent.from_bundle()` line 117: `grammar_builder=None` (hardcoded)
2. `xgrammar` dependency declared but never imported in source
3. `DecodingConstraint` configured but never passed to client

**Missing:**
- Grammar builder implementation using xgrammar
- Integration with vLLM's `/v1/chat/completions` extra_body parameter
- EBNF grammar generation from ToolSchema

---

## 6. Event System Status

### 6.1 Implementation Review
**Status:** Fully implemented (contrary to CODE_REVIEW.md)

After reviewing `kernel.py`, all 7 event types ARE emitted:

| Event | Line | Context |
|-------|------|---------|
| `KernelStartEvent` | 219 | `run()` start |
| `ModelRequestEvent` | 88, 234 | `step()` and `run()` |
| `ModelResponseEvent` | 108 | After API call |
| `ToolCallEvent` | 134 | Before tool execution |
| `ToolResultEvent` | 164 | After tool execution |
| `TurnCompleteEvent` | 190 | End of step |
| `KernelEndEvent` | 254 | `run()` end |

**Note:** CODE_REVIEW.md was outdated - events are properly emitted in current version.

### 6.2 CompositeObserver
**Status:** Implemented in `events/observer.py`

```python
class CompositeObserver:
    """Fan out events to multiple observers."""
    def __init__(self, observers: list[Observer]) -> None:
        self._observers = observers
    
    async def emit(self, event: Event) -> None:
        for observer in self._observers:
            await observer.emit(event)
```

---

## 7. Client Implementation

### 7.1 OpenAICompatibleClient (`client/openai.py`)
**Status:** Good implementation

**Strengths:**
- Proper async OpenAI client usage
- Token usage extraction
- Raw response preservation
- Configurable timeout

**Issues:**
- **BUG:** Line 86 uses `response.model_dump()` which is correct (was `to_dict()` in older version)
- `tool_choice="auto"` sent even when no tools (may cause backend issues)

### 7.2 Duplicate `build_client`
**Status:** Already fixed

CODE_REVIEW.md mentioned duplicate in `client/factory.py`, but that file doesn't exist. Only `client/openai.py:93-100` has `build_client`.

---

## 8. Parser Implementation

### 8.1 QwenResponseParser (`models/parsers.py`)
**Status:** Functional

**Features:**
- Handles OpenAI-style tool_calls from API
- XML-style tool call parsing for grammar-constrained outputs
- JSON error handling

**Issues:**
- **BUG FIXED:** Line 34 now preserves `tc["id"]` (was generating new UUID in older version)
- XML parsing uses `ToolCall.create()` which generates new ID - should preserve from XML if present

---

## 9. AGENTS.md Compliance

### 9.1 Rules Followed
- Minimal diffs philosophy observed in current implementation
- Fully typed code (with acceptable `Any` usage)
- Frozen dataclasses with `slots=True`
- Explicit imports preferred
- No circular imports detected

### 9.2 Rules Violated
- **Dependency Introspection:** vLLM/xgrammar not actually used despite being vendored
- **Testing Policy:** Test suite has gaps (no negative paths)
- **Documentation Policy:** README.md still stale (describes pre-v0.3.0 API)

---

## 10. Summary of Fixes Since CODE_REVIEW.md

The following issues from CODE_REVIEW.md have been **fixed**:

1. ✅ **BUG-1:** `response.model_dump()` now used correctly
2. ✅ **BUG-2:** Tool call IDs preserved in parser
3. ✅ **BUG-3:** Context (`tc`) passed to tool.execute()
4. ✅ **FEAT-1:** Grail integration fully implemented (not stubbed)
5. ✅ **FEAT-3:** All 7 event types now emitted
6. ✅ Duplicate `build_client` removed (factory.py doesn't exist)

**Remaining Critical Issues:**
1. ❌ **FEAT-2:** Grammar pipeline still inert (hardcoded `None`)
2. ❌ Exception hierarchy unused
3. ❌ No `py.typed` marker
4. ❌ README.md still stale

---

## 11. Recommendations

### P0 (Before Release)
1. Wire up grammar pipeline or remove xgrammar dependency
2. Add `py.typed` marker file
3. Update README.md with actual v0.3.1 API

### P1 (Quality)
1. Implement exception handling (use custom exceptions)
2. Add negative test cases
3. Remove unused exception classes or implement raising them

### P2 (Polish)
1. Add more descriptive tool descriptions from Grail script docstrings
2. Add validation of tool arguments against schema
3. Consider supporting `@external` function introspection

---

*Analysis completed. See CODE_REVIEW.md for original review context.*
