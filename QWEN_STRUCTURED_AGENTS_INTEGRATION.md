# Qwen Model Integration Report for structured-agents

## Executive Summary

This report documents how to add Qwen/Qwen3-4B-Instruct-2507-FP8 as a first-class model in the remora library, which uses structured-agents for tool calling. The integration involves two main components:

1. **vLLM Server Configuration** (done)
2. **structured-agents Grammar/Plugin for xgrammar** (requires new development)

---

## Part 1: Current functiongemma Integration (Reference)

### 1.1 vLLM Server Startup

**File:** `server/entrypoint.sh`

```bash
vllm serve google/functiongemma-270m-it \
    --enable-auto-tool-choice \
    --tool-call-parser functiongemma \
    --chat-template /app/tool_chat_template_functiongemma.jinja \
    --structured-outputs-config.backend xgrammar \
    --max-num-seqs 32 \
    --max-model-len 32768 \
    --enable-prefix-caching
```

### 1.2 Configuration Files

- **`src/remora/config.py:72`** - `default_adapter: str = "google/functiongemma-270m-it"`
- **`remora.yaml`** - `default_adapter: "google/functiongemma-270m-it"`

### 1.3 Bundle Configuration (`agents/*/bundle.yaml`)

```yaml
model:
  plugin: function_gemma
  adapter: google/functiongemma-270m-it
  grammar:
    mode: ebnf
    allow_parallel_calls: true
    args_format: permissive
```

---

## Part 2: Qwen Tool Calling Format

### 2.1 vLLM Server Flags (Implemented)

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --max-num-seqs 32 \
    --max-model-len 32768 \
    --enable-prefix-caching
```

### 2.2 Qwen Tool Calling Format

The Qwen3 models use an XML-like format:

```
<tool_call>
<function=get_weather>
<parameter=city>{"city": "London"}</parameter>
</function>
</tool_call>
```

Or the newer format (qwen3_xml parser):

```
<tool_call>
<tool_call>
<tool name="get_weather">
<parameter name="city">London</parameter>
</tool>
</tool_call>
```

### 2.3 Known Issue

⚠️ **Qwen3-4B-Instruct-2507-FP8 has a bug** causing endless generation with structured output:

- See: https://github.com/QwenLM/Qwen3/issues/1700
- Recommendation: Use `--tool-call-parser qwen3_xml` instead of `qwen3_coder`

---

## Part 3: How structured-agents Handles Grammars

### 3.1 Architecture Overview

The grammar flows through these layers:

```
Remora                           structured-agents              vLLM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
bundle.yaml ──────────────────► GrammarConfig ───────────────► xgrammar
  │                                │                             │
  │ mode: ebnf                     │                             │
  │ allow_parallel_calls: true     │                             │
  │ args_format: permissive        │                             │
  │                                ▼                             ▼
  │                    ┌─────────────────────┐    ┌──────────────────┐
  │                    │ ToolCallPlugin      │    │ Constrained      │
  │                    │ (function_gemma)    │    │ Decoding         │
  │                    └─────────────────────┘    └──────────────────┘
  │
  ▼
KernelRunner._build_kernel()
  │
  ├─► bundle.get_grammar_config() ──► GrammarConfig object
  │
  └─► bundle.get_plugin("function_gemma") ──► ToolCallPlugin
```

### 3.2 Grammar Configuration in Bundle

From `agents/lint/bundle.yaml`:

```yaml
grammar:
  mode: ebnf                    # Format type: "ebnf", "json_schema", "structural_tag"
  allow_parallel_calls: true     # Allow multiple tool calls in one response
  args_format: permissive       # How to format arguments: "strict", "permissive"
```

### 3.3 structured-agents Built-in Support

According to structured-agents documentation, it already has **built-in support for Qwen formats**:

> **QwenXMLParameterFormat**: Qwen-coder XML style format. The output uses XML-style tags such as `<parameter=name>value</parameter>` to represent schema properties.
>
> Usage: `"style": "qwen_xml"`

This is configured via the `response_format` in structured-agents:

```python
response_format = {
    "type": "structural_tag",
    "format": {
        "type": "triggered_tags",
        "triggers": ["<tool_call>"],
        "tags": [
            {
                "begin": "<function=",
                "content": {"type": "json_schema", "json_schema": ...},
                "end": "</function>",
            },
            ...
        ]
    }
}
```

---

## Part 4: Implementation Plan for Junior Developer

### 4.1 Option A: Use Built-in Qwen Support (Simplest)

structured-agents already has `qwen_xml` style support. You just need to:

1. **Update bundle.yaml files** to use a new plugin or grammar config:

```yaml
model:
  plugin: qwen_xml  # or create new plugin
  adapter: Qwen/Qwen3-4B-Instruct-2507-FP8
  grammar:
    mode: structural_tag
    style: qwen_xml
```

2. **Create a new plugin** in structured-agents or configure existing one

### 4.2 Option B: Create Custom xgrammar (Recommended for Full Control)

If you need custom behavior, create a custom grammar builder:

#### Step 1: Create Grammar Builder Module

Create `src/remora/grammars/qwen3.py`:

```python
"""Qwen3 tool calling grammar builder for xgrammar."""

from typing import Any

def build_qwen3_grammar(tools: list[dict[str, Any]], **kwargs: Any) -> str:
    """
    Build an EBNF grammar for Qwen3 tool calling.
    
    The Qwen3 format uses XML-like tags:
    <tool_call>
    <function=tool_name>
    <parameter=name>value</parameter>
    </function>
    </tool_call>
    
    Args:
        tools: List of tool schemas in OpenAI format
        allow_parallel: Whether to allow parallel tool calls
        args_format: "strict" or "permissive" for argument formatting
    
    Returns:
        EBNF grammar string in GBNF format
    """
    allow_parallel = kwargs.get("allow_parallel_calls", True)
    args_format = kwargs.get("args_format", "perissive")
    
    # Build tool name alternations
    tool_names = [f'"{t["function"]["name"]}"' for t in tools]
    tool_names_alternation = " | ".join(tool_names) if tool_names else '""'
    
    # Build grammar based on format
    if args_format == "strict":
        param_format = r'<parameter=name>[^<]+</parameter>'
    else:
        param_format = r'<parameter=name>[^<]*</parameter>'
    
    grammar = f"""
root ::= tool_call+

tool_call ::= "<tool_call>" tool_body "</tool_call>"

tool_body ::= "<function=" {tool_names_alternation}>" parameters "</function>"

parameters ::= ({param_format})*

"""
    return grammar
```

#### Step 2: Register with structured-agents

```python
# In structured-agents or remora
from xgrammar import Grammar

def get_grammar_config(tools: list[dict], config: dict) -> Grammar:
    """Get xgrammar Grammar object for Qwen3 format."""
    from remora.grammars.qwen3 import build_qwen3_grammar
    
    grammar_str = build_qwen3_grammar(
        tools,
        allow_parallel_calls=config.get("allow_parallel_calls", True),
        args_format=config.get("args_format", "perissive"),
    )
    
    return Grammar.from_ebnf(grammar_str)
```

#### Step 3: Create ToolCallPlugin for Qwen

```python
# In structured-agents plugins/
from typing import Any
from .base import ToolCallPlugin

class Qwen3ToolCallPlugin(ToolCallPlugin):
    """Plugin for Qwen3 tool calling format."""
    
    name = "qwen3"
    
    # Trigger sequences that indicate tool call start
    TOOL_CALL_TRIGGERS = ["<tool_call>", "<function="]
    
    # Tool call end markers
    TOOL_CALL_END = ["</tool_call>", "</function>"]
    
    def parse_tool_calls(self, response: str) -> list[dict[str, Any]]:
        """Parse Qwen3 tool calls from response."""
        import re
        
        tool_calls = []
        # Match <function=tool_name>...<parameter=name>value</parameter>...
        pattern = r'<function=(\w+)>((?:<parameter=\w+>[^<]*</parameter>)*)</function>'
        
        for match in re.finditer(pattern, response):
            tool_name = match.group(1)
            params_str = match.group(2)
            
            # Parse parameters
            params = {}
            param_pattern = r'<parameter=(\w+)>([^<]*)</parameter>'
            for param_match in re.finditer(param_pattern, params_str):
                params[param_match.group(1)] = param_match.group(2)
            
            tool_calls.append({
                "name": tool_name,
                "arguments": params,
            })
        
        return tool_calls
    
    def format_tools_for_prompt(self, tools: list[dict]) -> str:
        """Format tools for inclusion in the prompt."""
        # Qwen3 uses a specific format in system prompt
        lines = ["# Tools\n", "You may call one or more functions:\n\n"]
        
        for tool in tools:
            func = tool["function"]
            lines.append(f"## {func['name']}\n")
            lines.append(f"{func.get('description', '')}\n\n")
            lines.append("Arguments:\n")
            for name, prop in func.get("parameters", {}).get("properties", {}).items():
                lines.append(f"- {name}: {prop.get('description', '')}\n")
        
        return "".join(lines)
```

---

## Part 5: Key Files to Modify

| File | Change | Priority |
|------|--------|----------|
| `server/entrypoint.sh` | Switch between functiongemma/Qwen | ✅ Done |
| `src/remora/config.py` | default_adapter | ✅ Done |
| `remora.yaml` | default_adapter | ✅ Done |
| `src/remora/grammars/qwen3.py` | New grammar builder | 🔲 Todo |
| `structured-agents` | Register Qwen3Plugin | 🔲 Todo |
| `agents/*/bundle.yaml` | Update grammar config | 🔲 Todo |

---

## Part 6: Testing Checklist

- [ ] vLLM server starts with Qwen model
- [ ] Tool calls are parsed correctly from model response
- [ ] Parallel tool calls work (if enabled)
- [ ] Grammar constraints are enforced (no invalid output)
- [ ] Error handling works for malformed tool calls
- [ ] Integration with remora orchestrator works end-to-end

---

## References

1. **XGrammar Documentation**: https://xgrammar.mlc.ai/docs/api/python/grammar.html
2. **structured-agents Tool Calling**: Built-in support for qwen_xml style
3. **Qwen3 vLLM Deployment**: https://qwen.readthedocs.io/en/latest/deployment/vllm.html
4. **vLLM Tool Parsers**: https://docs.vllm.ai/en/latest/api/vllm/tool_parsers/qwen3xml_tool_parser/
5. **FunctionGemma Format**: Uses `<start_function_call>call:tool_name{...}<end_function_call>`
6. **Qwen3-4B-Instruct-2507-FP8 Issue**: https://github.com/QwenLM/Qwen3/issues/1700
