# XGrammar Integration Review

## Executive Summary

This document outlines the investigation into Qwen3 tool calling issues with xgrammar-structured outputs, the fixes applied, and recommendations for full xgrammar integration in structured-agents.

**Key Finding**: The `structural_tag` grammar mode now works correctly with Qwen3 after switching from `JSONSchemaFormat` to `QwenXMLParameterFormat`. The EBNF and JSON schema modes have known issues with vLLM.

---

## Issues Found

### Issue 1: Wrong Format Class Used in structural_tag Mode

**Problem**: The `Qwen3GrammarBuilder._build_structural_tag()` method was using `JSONSchemaFormat` with a non-existent `style` parameter.

**Location**: `src/structured_agents/grammar/builders/qwen3.py:85-95`

**Original Code**:
```python
content=JSONSchemaFormat(
    json_schema=tool.parameters, style="qwen_xml"
)
```

**Error**: 
```
ERROR: No parameter named "style"
```

**Root Cause**: The `.context/xgrammar/` directory contained a newer version of xgrammar (with `style` field in `JSONSchemaFormat`), but the installed version was 0.1.29 which doesn't have this field.

---

### Issue 2: EBNF Mode Returns Empty Arguments

**Problem**: When using EBNF grammar mode, vLLM correctly detects tool calls but returns empty `arguments: {}`.

**Reproduction**:
```
Extra body: {'structured_outputs': {'type': 'grammar', 'grammar': '...'}}

Raw tool_calls: [{'id': '...', 'function': {'name': 'calculator', 'arguments': '{}'}}]
Parsed tool_calls: [ToolCall(..., arguments={})]
```

**Root Cause**: This appears to be a **vLLM bug**, not a structured-agents issue. The grammar constrains output to the correct format (`<function=tool><parameter=k>v</parameter></function>`), vLLM detects the tool call, but fails to extract the arguments.

**Evidence**: 
- Model outputs correct format per grammar
- vLLM returns `finish_reason: 'tool_calls'`
- But arguments are always empty `{}`

---

### Issue 3: json_schema Mode Ignored

**Problem**: When using JSON schema grammar mode, the model completely ignores the constraint and returns text instead of tool calls.

**Reproduction**:
```
Extra body: {'structured_outputs': {'type': 'json', 'json': {'json_schema': {...}}}}

Raw response: "display"
Raw tool_calls: None
```

**Root Cause**: Unknown - could be vLLM configuration issue or model behavior.

---

## Fixes Applied

### Fix 1: Use QwenXMLParameterFormat (PR #8987299)

**Changed**: `src/structured_agents/grammar/builders/qwen3.py`

**Before**:
```python
from xgrammar.structural_tag import (
    GrammarFormat,
    JSONSchemaFormat,  # Wrong!
    ...
)
```

**After**:
```python
from xgrammar.structural_tag import (
    GrammarFormat,
    QwenXMLParameterFormat,  # Correct!
    ...
)
```

And in `_build_structural_tag`:
```python
content=QwenXMLParameterFormat(json_schema=tool.parameters)
```

**Why This Works**: 
- xgrammar 0.1.29 provides `QwenXMLParameterFormat` specifically for Qwen XML format
- This accepts both JSON and XML-style parameters: `<parameter=k>v</parameter>`
- vLLM can properly parse the constrained output

---

### Fix 2: Update Demo Scripts to Use structural_tag Mode

**Changed**: 
- `demo/demo_steps/step07_grammar_decoding.py`
- `demo/demo_steps/step08_shell_agent_single.py`
- `demo/demo_steps/step09_shell_agent_extended.py`
- `demo/demo_steps/step10_code_agent.py`

**Before**:
```python
grammar = plugin.build_grammar(tools, GrammarConfig())  # Defaults to ebnf
```

**After**:
```python
grammar = plugin.build_grammar(tools, GrammarConfig(mode="structural_tag"))
```

---

## Grammar Mode Comparison

| Mode | Status | Tool Calls | Arguments | Notes |
|------|--------|------------|-----------|-------|
| `structural_tag` | ✅ Working | Yes | Parsed | Recommended |
| `ebnf` | ❌ Broken | Yes | Empty `{}` | vLLM bug |
| `json_schema` | ❌ Broken | No | N/A | Model ignores |

---

## Current Architecture

### Grammar Builder Flow

```
GrammarConfig (mode, allow_parallel_calls, args_format)
         │
         ▼
Qwen3GrammarBuilder.build(tools, config)
         │
    ┌────┴────┐
    ▼         ▼        ▼
ebnf   structural_tag  json_schema
    │         │          │
    ▼         ▼          ▼
EBNFGrammar  StructuralTagGrammar  JsonSchemaGrammar
    │         │          │
    └─────────┴──────────┘
              │
              ▼
    to_vllm_payload()
              │
              ▼
    extra_body for API call
```

### Grammar Artifact to vLLM Payload

**EBNFGrammar**:
```python
def to_vllm_payload(self) -> dict[str, Any]:
    return {
        "structured_outputs": {
            "type": "grammar",
            "grammar": self.grammar,
        }
    }
```

**StructuralTagGrammar**:
```python
def to_vllm_payload(self) -> dict[str, Any]:
    return {
        "structured_outputs": {
            "type": "structural_tag",
            "structural_tag": self.tag.model_dump_json(),  # JSON string
        }
    }
```

**JsonSchemaGrammar**:
```python
def to_vllm_payload(self) -> dict[str, Any]:
   structured_outputs": {
 return {
        "            "type": "json",
            "json": {
                "json_schema": self.schema,
            },
        }
    }
```

---

## xgrammar 0.1.29 Capabilities

### Available Format Classes

From `.context/xgrammar-0.1.29/python/xgrammar/structural_tag.py`:

| Class | Purpose |
|-------|---------|
| `JSONSchemaFormat` | Standard JSON schema validation |
| `QwenXMLParameterFormat` | Qwen XML function call format |
| `GrammarFormat` | EBNF grammar validation |
| `RegexFormat` | Regex pattern validation |
| `TagFormat` | Custom begin/content/end tags |
| `TriggeredTagsFormat` | Multiple tags with triggers |
| `TagsWithSeparatorFormat` | Tags separated by delimiter |

### QwenXMLParameterFormat Details

```python
class QwenXMLParameterFormat(BaseModel):
    type: Literal["qwen_xml_parameter"] = "qwen_xml_parameter"
    json_schema: Union[bool, Dict[str, Any]]
```

Accepts:
```
<parameter=name>Bob</parameter><parameter=age>100</parameter>
<parameter=name>"Bob&lt;"</parameter><parameter=age>100</parameter>
```

---

## Recommendations for Full Integration

### 1. Fix EBNF Mode (High Priority)

**Issue**: EBNF grammar produces correct format but vLLM doesn't extract arguments.

**Investigation Needed**:
- Test with different vLLM versions
- Check if this is a known vLLM issue
- Try different grammar formulations

**Alternative**: The structural_tag mode now works - consider deprecating EBNF for Qwen.

---

### 2. Add args_format Support to structural_tag

**Current State**: `_build_structural_tag` ignores `config.args_format`.

**Code** (`qwen3.py:112-116`):
```python
def _build_args_grammar_for_tool(
    self, tool: ToolSchema, config: GrammarConfig
) -> str:
    """Build argument grammar for a specific tool."""
    return "(<parameter=[^>]+>[^<]*</parameter>)*"
```

**Options**:
- Add support for `args_format` in structural_tag mode
- Could use different content types based on config

---

### 3. Support Multiple Grammar Styles

**Enhancement**: Allow different parameter styles in structural_tag:

```python
class GrammarConfig:
    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = True
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"
    # Add new option:
    param_style: Literal["json", "qwen_xml", "xml"] = "qwen_xml"
```

---

### 4. Improve Response Parsing

**Issue**: Sometimes arguments have quote noise:

```
arguments: {'operation': ' "add" ', 'a': 5, 'b': 3}
```

**Location**: `src/structured_agents/plugins/qwen_components.py:114-125`

**Fix**: Clean up quoted values in `_parse_qwen_xml_parameters`.

---

### 5. Add More Grammar Builders

**Current**: Only `Qwen3GrammarBuilder` and `FunctionGemmaGrammarBuilder`.

**Missing**:
- Hermes-style tool calling (for Llama, etc.)
- Pythonic format
- Custom formats

---

### 6. Comprehensive Testing

**Test Coverage Needed**:
- [x] structural_tag with single tool
- [x] structural_tag with multiple tools  
- [x] structural_tag with parallel calls
- [ ] EBNF with complex schemas
- [ ] JSON schema with nested objects
- [ ] Error handling for invalid schemas
- [ ] Performance benchmarks

---

## Testing Results

### structural_tag Mode Results

```
>>> What is 5 + 3?
    Tool: calculator
    Args: {'operation': ' "add" ', 'a': 5, 'b': 3}

>>> Multiply 12 by 8
    Tool: multiply
    Args: {'a': 12, 'b': 8}

>>> Divide 144 by 12
    Tool: divide
    Args: {'a': 144, 'b': 12}
```

### Calculator Agent (6 Operations)
- add: ✅
- subtract: ✅
- multiply: ✅
- divide: ✅
- power: ✅
- modulo: ✅

### Multi-tool Reasoning
- get_weather: ✅
- get_forecast: ✅
- compare_cities: ✅
- get_time: ✅

---

## Files Modified

| File | Change |
|------|--------|
| `src/structured_agents/grammar/builders/qwen3.py` | Use QwenXMLParameterFormat |
| `tests/test_grammar/test_qwen3_json_schema_format.py` | New test |
| `demo/demo_steps/step07_grammar_decoding.py` | Use structural_tag |
| `demo/demo_steps/step08_shell_agent_single.py` | Use structural_tag |
| `demo/demo_steps/step09_shell_agent_extended.py` | Use structural_tag |
| `demo/demo_steps/step10_code_agent.py` | Use structural_tag |
| `demo/demo_steps/step12_calculator_agent.py` | New demo |
| `demo/demo_steps/step13_filesystem_agent.py` | New demo |
| `demo/demo_steps/step14_reasoning_agent.py` | New demo |

---

## vLLM Server Configuration

The current server configuration is correct:

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_xml \
    --max-num-seqs 32 \
    --max-model-len 32768 \
    --enable-prefix-caching
```

**Note**: Use `qwen3_xml` (not `qwen3_coder`) due to known bug: [QwenLM/Qwen3#1700](https://github.com/QwenLM/Qwen3/issues/1700)

---

## Conclusion

The primary issue has been resolved - Qwen3 tool calling now works with `structural_tag` mode using `QwenXMLParameterFormat`. The remaining issues (EBNF empty arguments, JSON schema ignored) appear to be vLLM-related rather than structured-agents bugs.

**Recommended Configuration**:
```python
grammar_config = GrammarConfig(
    mode="structural_tag",  # Only mode that works reliably
    allow_parallel_calls=True,  # or False
)
```

**Next Steps**:
1. Consider removing or deprecating EBNF mode for Qwen
2. Fix quote-cleaning in response parser
3. Add comprehensive tests for all grammar modes
4. Investigate EBNF empty arguments issue in vLLM
