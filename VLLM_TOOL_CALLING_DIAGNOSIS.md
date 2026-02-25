# vLLM Tool Calling Diagnosis

## Executive Summary

The Qwen3-4B model is not producing valid tool call arguments when grammar constraints are applied, despite the grammar correctly constraining output to tool call format. This appears to be a model-specific issue rather than a structured-agents library issue.

---

## Observed Behavior

### Test 1: No Grammar (vLLM's built-in parser)
```python
# Request without extra_body (grammar)
Response: Content: <tool_call>{"name": "calculator", "arguments": {"operation": "add", "a": 5, "b": 3}}</tool_call>
Tool calls: None
```
- Model outputs tool call in `content` as JSON-in-XML format
- vLLM's `qwen3_xml` parser does NOT parse this (expects XML format, gets JSON)
- Tool calls are NOT extracted

### Test 2: EBNF Grammar
```python
# Grammar config: mode='ebnf', allow_parallel_calls=False
Response: Content: None
Tool calls: [{'id': '...', 'function': {'name': 'calculator', 'arguments': '{}'}}]
```
- Grammar correctly constrains output to tool call format
- vLLM detects tool_calls with `finish_reason: 'tool_calls'`
- **BUT: arguments are empty `{}`**

### Test 3: Structural Tag Grammar
```python
# Grammar config: mode='structural_tag'
Error: 400 Bad Request - 'NoneType' object is not subscriptable
```
- Initial fix: Changed `model_dump_json()` to `model_dump()` → Wrong direction
- Reverted to `model_dump_json()` → vLLM returns 400 (expects string but gets dict)
- Error: `'NoneType' object is not subscriptable` - response.choices is None

### Test 4: JSON Schema Grammar  
```python
# Grammar config: mode='json_schema'
Response: Content: "display"
Tool calls: None
```
- Model ignores tool constraint and returns text "display"

---

## vLLM Server Configuration

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_xml \
    --max-num-seqs 32 \
    --max-model-len 32768 \
    --enable-prefix-caching
```

Server logs show:
- `vLLM Successfully import tool parser Qwen3XMLToolParser !`
- 200 OK when no grammar
- 400 Bad Request with grammar constraints

---

## Root Cause Analysis

### Hypothesis 1: Model Output Format Mismatch
The Qwen3-4B-Instruct model outputs JSON inside XML tags:
```xml
<tool_call>
{"name": "calculator", "arguments": {"operation": "add", "a": 5, "b": 3}}
</tool_call>
```

But vLLM's `qwen3_xml` parser expects XML format:
```xml
<tool_call>
<tool name="calculator">
<parameter name="operation">add