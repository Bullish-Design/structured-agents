# Qwen3 Integration Plan for structured-agents

## Overview

This document provides a detailed step-by-step plan to add first-class support for `Qwen/Qwen3-4B-Instruct-2507-FP8` to structured-agents. The existing `QwenPlugin` is incomplete—it lacks grammar support. This plan addresses that gap.

## Current State Analysis

### Existing Qwen Plugin (`src/structured_agents/plugins/qwen.py`)
- Already registered in `PluginRegistry` with name `"qwen"`
- Has basic message/tool formatting (passes through to OpenAI format)
- Has response parser for vLLM `tool_calls_raw` output
- **Missing**: Grammar provider (returns `None` for all grammar modes)

### xgrammar Native Support
The `.context/xgrammar/` library already has native support for Qwen formats:

1. **`JSONSchemaFormat` with `style: "qwen_xml"`** (`.context/xgrammar/python/xgrammar/structural_tag.py:27-38`)
   - Accepts: `<parameter=name>value</parameter>` format
   - Works with `structural_tag` mode

2. **`QwenXMLParameterFormat`** (`.context/xgrammar/python/xgrammar/structural_tag.py:40-70`)
   - Dedicated format for Qwen XML function calls
   - Type: `"qwen_xml_parameter"`

3. **`TriggeredTagsFormat`** (`.context/xgrammar/python/xgrammar/structural_tag.py:157-207`)
   - Supports triggers like `"<function="`
   - Supports tool call patterns: `<function=tool_name>...</function>`

### Qwen3 Tool Call Format
```
<tool_call>
<function=get_weather>
<parameter=city>{"city": "London"}</parameter>
</function>
</tool_call>
```
Or with `qwen3_xml` parser:
```
<tool_call>
<tool name="get_weather">
<parameter name="city">London</parameter>
</tool>
</tool_call>
```

---

## Implementation Steps

### Phase 1: Grammar Builder

**Step 1.1:** Create `src/structured_agents/grammar/builders/qwen3.py`

```python
"""Grammar builder for Qwen3 tool calling format."""

from structured_agents.grammar.artifacts import (
    GrammarArtifact,
    StructuralTagGrammar,
)
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema

from xgrammar import StructuralTag
from xgrammar.structural_tag import (
    GrammarFormat,
    JSONSchemaFormat,
    OrFormat,
    SequenceFormat,
    TagFormat,
    TriggeredTagsFormat,
)


class Qwen3GrammarBuilder:
    """Grammar builder for Qwen3 models."""

    def supports_mode(self, mode: str) -> bool:
        return mode in ("structural_tag", "json_schema")

    def build(self, tools: list[ToolSchema], config: GrammarConfig) -> GrammarArtifact | None:
        if not tools:
            return None

        if config.mode == "json_schema":
            return self._build_json_schema(tools, config)

        return self._build_structural_tag(tools, config)

    def _build_structural_tag(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> StructuralTagGrammar:
        """Build structural tag grammar for Qwen3 format.
        
        Qwen3 format:
        <tool_call>
        <function=tool_name>
        <parameter=name>value</parameter>
        </function>
        </tool_call>
        """
        tool_tags = []
        for tool in tools:
            tool_tags.append(
                TagFormat(
                    begin=f"<function={tool.name}>",
                    content=JSONSchemaFormat(
                        json_schema=tool.parameters,
                        style="qwen_xml",
                    ),
                    end="</function>",
                )
            )

        if len(tool_tags) == 1:
            tag_choice = tool_tags[0]
        else:
            tag_choice = OrFormat(elements=tool_tags)

        if config.allow_parallel_calls:
            format_spec = SequenceFormat(
                elements=[tag_choice],
            )
        else:
            format_spec = tag_choice

        structural_tag = StructuralTag(format=format_spec)
        return StructuralTagGrammar(tag=structural_tag)

    def _build_json_schema(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> GrammarArtifact:
        """Build JSON schema grammar for Qwen3 format."""
        tool_choices = []
        for tool in tools:
            tool_choices.append({
                "type": "object",
                "properties": {
                    "name": {"const": tool.name},
                    "arguments": tool.parameters,
                },
                "required": ["name", "arguments"],
            })

        schema = {
            "type": "array",
            "items": {"anyOf": tool_choices} if len(tool_choices) > 1 else tool_choices[0],
        }

        return JsonSchemaGrammar(schema=schema)
```

**Step 1.2:** Update `src/structured_agents/grammar/builders/__init__.py` to export the new builder.

---

### Phase 2: Component Implementation

**Step 2.1:** Update `src/structured_agents/plugins/qwen_components.py`

Replace `QwenGrammarProvider` with a full implementation:

```python
class QwenGrammarProvider(GrammarProvider):
    """Grammar provider for Qwen3 models."""

    def __init__(self) -> None:
        self._grammar_builder = Qwen3GrammarBuilder()

    def supports_mode(self, mode: str) -> bool:
        return self._grammar_builder.supports_mode(mode)

    def build_grammar(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> GrammarArtifact | None:
        return self._grammar_builder.build(tools, config)

    def to_extra_body(self, artifact: GrammarArtifact | None) -> dict[str, Any] | None:
        if artifact is None:
            return None

        if isinstance(artifact, StructuralTagGrammar):
            return artifact.to_vllm_payload()

        raise ValueError(f"Unsupported artifact type: {type(artifact)}")
```

**Step 2.2:** Update `QwenResponseParser` to handle raw content parsing.

The current parser only handles `tool_calls_raw` from vLLM. We need to add parsing of raw text content for cases where vLLM doesn't extract tool calls:

```python
class QwenResponseParser(ResponseParser):
    """Response parser for Qwen3."""

    _TOOL_CALL_PATTERN = re.compile(
        r"<function=([a-zA-Z_][a-zA-Z0-9_-]*)>"
        r"((?:<parameter=[^>]+>[^<]*</parameter>)*)"
        r"</function>"
    )

    def parse_response(
        self, content: str | None, tool_calls_raw: list[dict[str, Any]] | None
    ) -> tuple[str | None, list[ToolCall]]:
        tool_calls: list[ToolCall] = []

        # First, try tool_calls_raw from vLLM
        if tool_calls_raw:
            for tc in tool_calls_raw:
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = (
                        json.loads(args_str) if isinstance(args_str, str) else args_str
                    )
                except json.JSONDecodeError:
                    args = {}
                    logger.warning("Failed to parse arguments: %s", args_str)

                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", f"call_{id(tc)}"),
                        name=func.get("name", "unknown"),
                        arguments=args,
                    )
                )

        # If no tool_calls_raw, try parsing from content
        if not tool_calls and content:
            matches = self._TOOL_CALL_PATTERN.findall(content)
            for name, params_str in matches:
                args = self._parse_qwen_xml_parameters(params_str)
                tool_calls.append(ToolCall.create(name=name, arguments=args))

            if tool_calls:
                return None, tool_calls

        return content, tool_calls

    def _parse_qwen_xml_parameters(self, params_str: str) -> dict[str, Any]:
        """Parse Qwen XML parameter format: <parameter=name>value</parameter>"""
        args = {}
        param_pattern = r"<parameter=([^>]+)>([^<]*)</parameter>"
        for match in re.finditer(param_pattern, params_str):
            key = match.group(1)
            value = match.group(2)
            try:
                args[key] = json.loads(value)
            except json.JSONDecodeError:
                args[key] = value
        return args
```

---

### Phase 3: Tests

**Step 3.1:** Create `tests/test_grammar/test_qwen3_builder.py`

```python
"""Tests for Qwen3 grammar builder."""

from structured_agents.grammar.artifacts import StructuralTagGrammar
from structured_agents.grammar.builders.qwen3 import Qwen3GrammarBuilder
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


def _tool(name: str, parameters: dict = None) -> ToolSchema:
    return ToolSchema(
        name=name,
        description="Test tool",
        parameters=parameters or {"type": "object", "properties": {}},
    )


def test_supports_mode() -> None:
    builder = Qwen3GrammarBuilder()
    assert builder.supports_mode("structural_tag") is True
    assert builder.supports_mode("json_schema") is True
    assert builder.supports_mode("ebnf") is False


def test_build_structural_tag_single_tool() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=False,
    )
    tool = _tool("get_weather", {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    })
    grammar = builder.build([tool], config)
    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    assert payload["structured_outputs"]["type"] == "structural_tag"


def test_build_structural_tag_multiple_tools() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    )
    tools = [
        _tool("get_weather"),
        _tool("search"),
    ]
    grammar = builder.build(tools, config)
    assert isinstance(grammar, StructuralTagGrammar)


def test_build_structural_tag_parallel_calls() -> None:
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    )
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, StructuralTagGrammar)
```

**Step 3.2:** Update `tests/test_plugins/test_qwen_plugin.py` to include grammar tests.

---

### Phase 4: Documentation

**Step 4.1:** Update docstrings in the new files.

**Step 4.2:** Optionally add usage example in a new file `examples/qwen3_demo.py`.

---

## File Changes Summary

| File | Change | Priority |
|------|--------|----------|
| `src/structured_agents/grammar/builders/qwen3.py` | New file - Qwen3 grammar builder | Required |
| `src/structured_agents/grammar/builders/__init__.py` | Export new builder | Required |
| `src/structured_agents/plugins/qwen_components.py` | Implement QwenGrammarProvider, enhance QwenResponseParser | Required |
| `src/structured_agents/plugins/qwen.py` | No changes needed (uses existing components) | - |
| `tests/test_grammar/test_qwen3_builder.py` | New file - grammar builder tests | Required |
| `tests/test_plugins/test_qwen_plugin.py` | Add grammar tests | Required |

---

## Verification Checklist

- [ ] `QwenPlugin` loads successfully via `get_plugin("qwen")`
- [ ] Grammar builder supports `structural_tag` mode
- [ ] Grammar builder supports `json_schema` mode  
- [ ] Grammar payload is correctly formatted for vLLM
- [ ] Response parser handles `tool_calls_raw` from vLLM
- [ ] Response parser handles raw content with Qwen XML format
- [ ] All existing Qwen plugin tests still pass
- [ ] New grammar builder tests pass
- [ ] Integration test with actual vLLM server (manual/optional)

---

## Usage

After implementation, users can configure Qwen3 in `bundle.yaml`:

```yaml
model:
  plugin: qwen
  adapter: Qwen/Qwen3-4B-Instruct-2507-FP8
  grammar:
    mode: structural_tag
    allow_parallel_calls: true
```

And start vLLM with:

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_xml \
    --max-num-seqs 32 \
    --max-model-len 32768 \
    --enable-prefix-caching
```

---

## Notes

1. **vLLM Parser**: The intern's document recommends `--tool-call-parser qwen3_xml` due to a bug in `qwen3_coder` (see QwenLM/Qwen3#1700).

2. **Grammar Mode**: We implement `structural_tag` mode using xgrammar's native `JSONSchemaFormat` with `style="qwen_xml"`, which is the most robust approach.

3. **Parallel Calls**: Qwen3 supports parallel tool calls. The grammar builder uses `SequenceFormat` to enforce this when `allow_parallel_calls: true`.

4. **No EBNF**: Qwen3 works best with `structural_tag` mode. We do not implement EBNF support as xgrammar's structural tags are the recommended approach for this model.
