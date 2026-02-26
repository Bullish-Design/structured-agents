# Structural Tag vLLM Error Report

## Executive Summary

This document details the issues encountered when using xgrammar's `structural_tag` feature with vLLM 0.15.1. Two bugs were identified in the `structured-agents` library, and one compatibility issue was discovered between the xgrammar library and vLLM's backend.

---

## Issue 1: JSON Serialization Bug (FIXED)

### Description
The `structural_tag` payload was being sent as a Python dictionary instead of a JSON string.

### Root Cause
In `src/structured_agents/grammar/pipeline.py`, when using the new xgrammar `StructuralTag` format, the code was using `model_dump()` which returns a dict:

```python
# BEFORE (broken - for new format)
return {"structured_outputs": {"structural_tag": payload.model_dump()}}
```

vLLM expects a JSON string for the `structural_tag` field, as shown in the vLLM protocol layer (`chat_completion/protocol.py:440`):

```python
# vLLM's protocol layer converts dict to JSON string
s_tag_obj = structural_tag.model_dump(by_alias=True)
structured_outputs_kwargs["structural_tag"] = json.dumps(s_tag_obj)
```

### Fix Applied
Changed to serialize the payload as a JSON string:

```python
# AFTER (fixed)
import json
return {"structured_outputs": {"structural_tag": json.dumps(payload.model_dump())}}
```

**Note**: When using the legacy format (dict-based), the payload is already a dict and gets serialized correctly by the OpenAI client, so this fix primarily applies to the new pydantic-based format.

---

## Issue 2: Format Compatibility - Legacy vs New Format

### Description
The code was initially using the new xgrammar `StructuralTag` format.

### Resolution
Switched to legacy format to avoid additional complexity. The legacy format is better supported and documented in vLLM examples.

### Legacy Format Used
```python
legacy_payload = {
    "type": "structural_tag",
    "structures": [
        {
            "begin": "<function=add_task>",
            "schema": tool.parameters,  # Raw JSON schema (no qwen_xml_parameter wrapper)
            "end": "</function>"
        }
    ],
    "triggers": ["<function="]
}
```

**Note**: Even with the legacy format, Issue 3 (unsupported schema type) caused the crash.

---

## Issue 3: Unsupported Schema Type - "qwen_xml_parameter" (ROOT CAUSE)

### Description
vLLM crashed with a fatal error when processing the structural_tag grammar.

### Actual Error
```
RuntimeError: [09:44:28] /project/cpp/json_schema_converter.cc:902: Unsupported type "qwen_xml_parameter"
```

### Root Cause
The xgrammar C++ compiler (in `json_schema_converter.cc`) does not support the `qwen_xml_parameter` type in JSON schemas. When the legacy format was used with this schema type:

```python
{
    "type": "qwen_xml_parameter",
    "json_schema": {
        "type": "object",
        "properties": {...}
    }
}
```

The xgrammar compiler throws a `RuntimeError` because it only supports standard JSON Schema types (`string`, `number`, `object`, `array`, `boolean`, `null`).

### Stack Trace
```
File "backend_xgrammar.py", line 126, in compile_grammar
    ctx = self.compiler.compile_structural_tag(tags, s_tag["triggers"])
File "compiler.py", line 279, in compile_structural_tag
    self._handle.compile_structural_tag(structural_tag_str)
RuntimeError: /project/cpp/json_schema_converter.cc:902: Unsupported type "qwen_xml_parameter"
```

### Fix Attempted
Removed the `qwen_xml_parameter` wrapper and used raw JSON schema:

```python
# BEFORE (caused crash - "qwen_xml_parameter" not supported)
args_schema = {
    "type": "qwen_xml_parameter",
    "json_schema": tool.parameters,
}

# AFTER (still crashed due to other issues, so disabled for demo)
args_schema = tool.parameters
```

However, even with this fix, there may be additional compatibility issues with the legacy format, so grammar was disabled for the demo.

## Additional Context: vLLM Server Configuration

The vLLM server is configured with:
```
tool_call_parser: qwen3_xml
enable_auto_tool_choice: True
```

This means vLLM natively supports Qwen-style XML tool calls without requiring grammar constraints. The model can generate tool calls in the format:
```
<function=add_task>{"title": "QA Review", "status": "open"}</function>
```

This is why the demo works without grammar constraints - the model has been trained/instructured to output tool calls in this format, and vLLM's `qwen3_xml` parser handles the extraction.

---

## Current Status

The demo runs successfully with grammar constraints **disabled** (`DISABLE_GRAMMAR = True` in `config.py`).

### What Works
- Main coordinator agent with tools (`add_task`, `update_task_status`, `record_risk`, `log_update`)
- Subagent delegation (`task_planner`, `risk_analyst`)
- State management and result aggregation

### What Doesn't Work
- Grammar-constrained decoding (structural tags)

---

## Recommendations

### Option A: Use JSON Schema Instead of Structural Tag (Recommended)
The `qwen_xml_parameter` type is not supported by xgrammar's C++ compiler. Instead of using structural tags with Qwen XML format, use standard JSON Schema:

1. Change `DecodingConstraint` strategy to `json_schema`
2. Let vLLM handle the tool parsing natively via `tool_call_parser: qwen3_xml` (which is already configured in the server)

### Option B: Use Native Tool Calling
Since the vLLM server is already configured with `tool_call_parser: qwen3_xml`, rely on the model's native tool-calling capability without grammar constraints.

### Option C: Upgrade xgrammar
The `qwen_xml_parameter` type may be supported in newer versions of xgrammar. Consider upgrading if available.

### Option D: Custom Grammar Compilation
If structural tags are required, compile the grammar server-side using xgrammar directly (bypassing the vLLM API's grammar parameter).

---

## Files Modified

| File | Change |
|------|--------|
| `src/structured_agents/grammar/pipeline.py` | Fixed JSON serialization bug |
| `demo/ultimate_demo/config.py` | Added `DISABLE_GRAMMAR` flag |
| `demo/ultimate_demo/coordinator.py` | Conditional grammar usage |
| `demo/ultimate_demo/subagents.py` | Conditional grammar usage |

---

## References

- vLLM Structured Outputs: `docs/features/structured_outputs.md`
- xgrammar Structural Tag: `python/xgrammar/structural_tag.py`
- vLLM Backend: `vllm/v1/structured_output/backend_xgrammar.py`
- Example Usage: `examples/online_serving/structured_outputs/structured_outputs.py`

---

# Appendix: Architecture Analysis and Recommendations

## The v0.3.0 Ethos

Before evaluating options, it's important to understand the guiding principles of this library:

1. **Minimal complexity** - Use what's already available rather than adding layers
2. **Deterministic behavior** - Avoid fragile workarounds or speculative fixes
3. **Reliability** - Fail fast, don't mask errors
4. **Dependency introspection** - Ground answers in vendored sources (`.context/`)
5. **Verifiable answers** - All behavior must be traceable to source

---

## Current Library Architecture

### Grammar Constraint System

The library currently implements a grammar constraint system with the following components:

```
DecodingConstraint (config.py)
    └── strategy: "ebnf" | "structural_tag" | "json_schema"
    └── allow_parallel_calls: bool
    └── send_tools_to_api: bool

ConstraintPipeline (pipeline.py)
    └── builder: Callable for building constraints
    └── config: DecodingConstraint
    └── constrain(tools) -> dict | None

build_structural_tag_constraint (pipeline.py)
    └── Converts ToolSchema list -> vLLM extra_body payload
```

### Integration Points

The grammar pipeline integrates at the `AgentKernel` level:

```python
# kernel.py
grammar_constraint = self.adapter.constraint_pipeline.constrain(resolved_tools)
extra_body = grammar_constraint
response = await self.client.chat_completion(..., extra_body=extra_body)
```

---

## Why Native Tool Calling Already Works

### vLLM's Native Tool Parsing

The vLLM server is configured with:
```python
tool_call_parser: qwen3_xml
enable_auto_tool_choice: True
```

This means:

1. **Model outputs in Qwen XML format**:
   ```
   <function=add_task>{"title": "QA Review", "status": "open"}</function>
   ```

2. **vLLM's Qwen3XMLToolParser** (`qwen3xml_tool_parser.py`) extracts:
   - Tool name: `add_task`
   - Arguments: `{"title": "QA Review", "status": "open"}`

3. **No grammar constraint needed** - The parsing happens automatically

### Evidence from Server Logs

```
2026-02-26 08:21:40.871 | (APIServer pid=7) INFO: qwen3xml_tool_parser.py:1178] vLLM Successfully import tool parser Qwen3XMLToolParser !
```

The parser is loaded and active. Every successful request in the logs shows this parser being invoked.

---

## Evaluation of Options

### Option A: Fix Grammar Constraints

**Description**: Fix the `qwen_xml_parameter` issue and make structural tags work.

**Implementation**:
- Remove `qwen_xml_parameter` wrapper from schema
- Use raw JSON Schema in structural tag definitions
- Add error handling for grammar compilation failures

**Pros**:
- Provides deterministic output format
- Can force model to output specific structure even if native parsing fails
- May be useful for non-Qwen models that don't have native tool support

**Cons**:
- **Adds unnecessary complexity** - native parsing already works
- **Fragile** - depends on xgrammar/vLLM compatibility
- **Performance cost** - grammar compilation adds latency
- **Maintenance burden** - must track xgrammar/vLLM changes
- **Violates ethos** - adding work when solution already exists

**Implications**:
- Requires ongoing testing against xgrammar/vLLM combinations
- Will likely break again with version mismatches
- Creates divergence between "grammar-constrained" and "native" paths

---

### Option B: Use Native Tool Calling (Recommended)

**Description**: Remove grammar constraint dependency entirely. Rely on vLLM's native tool parsing.

**Implementation**:
- Default `GRAMMAR_CONFIG = None` or don't create a constraint pipeline
- Let vLLM handle tool extraction via `tool_call_parser`
- Document that grammar constraints are optional

**Pros**:
- **Simpler** - no extra layer of complexity
- **Faster** - no grammar compilation overhead
- **More reliable** - fewer failure points
- **Aligned with v0.3.0 ethos** - minimal, deterministic, verifiable
- **Future-proof** - works regardless of xgrammar/vLLM changes
- **Better for Qwen models** - uses built-in capabilities

**Cons**:
- Less control over exact output format
- Depends on model following training/instruction
- May not work for non-Qwen models without native tool support

**Implications**:
- Demo runs with `DISABLE_GRAMMAR = True`
- Grammar module becomes optional/opt-in
- Library documents native tool calling as the default path

---

### Option C: Hybrid Approach

**Description**: Use native tool calling by default, with grammar constraints as an optional fallback.

**Implementation**:
- Default: No grammar constraint (native tool parsing)
- Optional: Enable grammar via config flag
- Graceful degradation: If grammar fails, fall back to native parsing

**Pros**:
- Best of both worlds
- Works for Qwen (native) and non-Qwen (grammar) models
- User can choose based on their needs

**Cons**:
- More complex code paths to maintain
- Requires careful error handling
- Two code paths to test

**Implications**:
- Config becomes: `grammar: "none" | "structural_tag" | "json_schema"`
- Default: `grammar: "none"` (native)
- Demo can document both approaches

---

## Recommendation

### For v0.3.x: Option B (Native Tool Calling)

Given the v0.3.0 ethos, **Option B is recommended**:

1. **Remove grammar constraints from the default demo** - The demo should showcase the simplest, most reliable path

2. **Keep the grammar module in the library** - But mark it as:
   - Optional feature
   - Currently incompatible with xgrammar 0.1.29 + vLLM 0.15.1
   - YMMV depending on backend

3. **Document the native path** - Explain how vLLM users should configure:
   ```python
   # Server-side (vLLM)
   --tool-call-parser qwen3_xml
   --enable-auto-tool-choice
   
   # Client-side (structured-agents)
   # No grammar config needed - native parsing handles it
   ```

4. **Fix the JSON serialization bug anyway** - Keep the fix in `pipeline.py` as it's correct, just document that the whole grammar path is experimental

### For Future Versions: Consider Option C

Once the grammar system is more stable, a hybrid approach could be valuable:
- Default to native for Qwen-family models
- Offer grammar constraints for:
  - Non-Qwen models that need structure
  - Users who want guaranteed output format
  - Advanced use cases requiring tight control

---

## Code Changes Required

### Minimal Fix (Option B)

```python
# demo/ultimate_demo/config.py
# Change from:
GRAMMAR_CONFIG = DecodingConstraint(...)
DISABLE_GRAMMAR = True

# To:
# Grammar constraints disabled - using native vLLM tool parsing
# Set to a DecodingConstraint to enable grammar constraints (experimental)
GRAMMAR_CONFIG = None
```

```python
# demo/ultimate_demo/coordinator.py
# In build_demo_kernel:
if GRAMMAR_CONFIG is None:
    adapter = ModelAdapter(..., constraint_pipeline=None)
else:
    pipeline = ConstraintPipeline(...)
    adapter = ModelAdapter(..., constraint_pipeline=pipeline)
```

### Full Refactor (Option C)

Add to config:
```python
GRAMMAR_STRATEGY = "none"  # "none" | "structural_tag" | "json_schema"
```

Update pipeline to handle `"none"`:
```python
def build_structural_tag_constraint(tools, config):
    if config is None or config.strategy == "none":
        return None
    # ... existing logic
```

---

## Conclusion

The root cause (`qwen_xml_parameter` not supported by xgrammar) is a symptom of a deeper architectural question: **should the library add grammar constraints when the backend already provides native tool parsing?**

Given the v0.3.0 ethos of minimal complexity and deterministic behavior, the answer is **no**. The library should:

1. **Default to native tool calling** - simplest, most reliable
2. **Keep grammar as optional** - for advanced use cases
3. **Document both paths** - let users choose

This aligns with the principle: "Don't build what you don't need." The model + vLLM already provides structured outputs; the library's value is in orchestration, not in re-implementing what already works.
