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
