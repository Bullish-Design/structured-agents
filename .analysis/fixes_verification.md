# Code Review Fixes Verification

**Date:** 2026-02-26  
**Scope:** Verification of fixes for CODE_REVIEW.md issues

---

## Summary

| Issue | Status | Evidence |
|-------|--------|----------|
| BUG-1: response.to_dict() vs model_dump() | **FIXED** | `client/openai.py:86` uses `response.model_dump()` |
| BUG-2: Parser drops tool call IDs | **FIXED** | `models/parsers.py:33-34` preserves `tc["id"]` |
| BUG-3: Tool context always None | **FIXED** | `kernel.py:153` passes `tc` (ToolCall) as context |
| FEAT-1: Grail discover_tools() stub | **FIXED** | `tools/grail.py:78-98` fully implemented with `grail.load()` |
| FEAT-2: Grammar pipeline wired | **OPEN** | `agent.py:117` sets `grammar_builder=None` |
| FEAT-3: Observer events (7 types) | **FIXED** | All 7 events emitted in `kernel.py` |

---

## Detailed Verification

### BUG-1: response.to_dict() vs model_dump()

**File:** `src/structured_agents/client/openai.py:86`

**Expected Fix:** Change `response.to_dict()` to `response.model_dump()`

**Current State:**
```python
return CompletionResponse(
    content=content,
    tool_calls=tool_calls,
    usage=usage,
    finish_reason=choice.finish_reason,
    raw_response=response.model_dump(),  # Line 86 - CORRECT
)
```

**Status:** ✅ FIXED

---

### BUG-2: Parser drops tool call IDs

**File:** `src/structured_agents/models/parsers.py:30`

**Expected Fix:** Preserve original `tc["id"]` instead of generating new UUID via `ToolCall.create()`

**Current State:**
```python
parsed.append(
    ToolCall(id=tc["id"], name=func["name"], arguments=args)  # Line 33-34 - CORRECT
)
```

**Status:** ✅ FIXED

---

### BUG-3: Tool context always None

**File:** `src/structured_agents/kernel.py:117`

**Expected Fix:** Pass `ToolCall` object (which has `.id`) as context instead of `None`

**Current State:**
```python
result = await tool.execute(tc.arguments, tc)  # Line 153 - CORRECT
```

The `tc` (ToolCall) object is now passed as context, and `GrailTool.execute` extracts the ID:
```python
call_id = context.id if context else "unknown"  # tools/grail.py:59
```

**Status:** ✅ FIXED

---

### FEAT-1: Grail discover_tools() stub

**File:** `src/structured_agents/tools/grail.py:47`

**Expected Fix:** Implement actual tool discovery using `grail.load()`

**Current State:**
```python
def discover_tools(
    agents_dir: str, limits: grail.Limits | None = None
) -> list[GrailTool]:
    """Discover and load .pym tools from a directory."""
    tools: list[GrailTool] = []
    agents_path = Path(agents_dir)

    if not agents_path.exists():
        logger.warning("Agents directory does not exist: %s", agents_dir)
        return tools

    for pym_file in sorted(agents_path.glob("*.pym")):
        try:
            script = grail.load(str(pym_file), grail_dir=None)  # Line 91 - CORRECT
            tools.append(GrailTool(script, limits=limits))
            logger.debug("Loaded tool: %s from %s", script.name, pym_file)
        except Exception as e:
            logger.warning("Failed to load %s: %s", pym_file, e)
            continue

    return tools
```

**Status:** ✅ FIXED - Full implementation with proper error handling and logging

---

### FEAT-2: Grammar pipeline wired

**File:** `src/structured_agents/agent.py:117`

**Expected Fix:** Wire the grammar-constraint pipeline instead of `lambda t, c: None`

**Current State:**
```python
adapter = ModelAdapter(
    name=manifest.model,
    response_parser=parser,
    grammar_builder=None,  # Line 117 - STILL OPEN
    grammar_config=manifest.grammar_config,
)
```

**Analysis:**
- `grammar_builder` is set to `None` in `agent.py:117`
- In `kernel.py:77-81`, when `grammar_builder` is `None`, `grammar_constraint` remains `None`
- `DecodingConstraint` and `GrammarConfig` exist but are not wired into the pipeline
- `xgrammar` is available in `.context/` but not integrated

**Status:** ❌ OPEN - Grammar pipeline exists but is not wired to production code path

---

### FEAT-3: Observer events (7 types)

**File:** `src/structured_agents/kernel.py`

**Expected Fix:** Emit all 7 event types

**Current State:** All 7 events are now emitted:

1. **KernelStartEvent** - `kernel.py:219-225` (in `run()` method)
2. **KernelEndEvent** - `kernel.py:254-260` (in `run()` method)
3. **ModelRequestEvent** - `kernel.py:87-94` (in `step()` method)
4. **ModelResponseEvent** - `kernel.py:108-116` (in `step()` method)
5. **ToolCallEvent** - `kernel.py:133-140` (in `execute_one()` nested function)
6. **ToolResultEvent** - `kernel.py:164-173` (in `execute_one()` nested function)
7. **TurnCompleteEvent** - `kernel.py:190-197` (in `step()` method)

**Status:** ✅ FIXED - All 7 event types are now emitted

---

## Conclusion

**Fixed (5/6):**
- BUG-1: response.to_dict() vs model_dump()
- BUG-2: Parser drops tool call IDs
- BUG-3: Tool context always None
- FEAT-1: Grail discover_tools() implementation
- FEAT-3: All 7 observer events emitted

**Still Open (1/6):**
- FEAT-2: Grammar pipeline is not wired (grammar_builder=None in agent.py)

The grammar constraint system exists in the codebase (`DecodingConstraint`, `GrammarConfig`, `xgrammar` in `.context/`) but is not connected to the production code path in `Agent.from_bundle()`.
