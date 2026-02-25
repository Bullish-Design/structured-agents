# Qwen3 xgrammar Structured Outputs Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix Qwen3 structural_tag grammar mode to use xgrammar's JSONSchemaFormat with qwen_xml style, enabling proper tool call argument parsing.

**Architecture:** Update `Qwen3GrammarBuilder._build_structural_tag()` to use `JSONSchemaFormat` with `style="qwen_xml"` instead of `GrammarFormat`. This leverages xgrammar's built-in support for Qwen XML format which accepts both JSON and XML-style parameters.

**Tech Stack:** structured-agents, xgrammar, vLLM, Qwen3-4B-Instruct-2507-FP8

---

### Task 1: Update Qwen3 Grammar Builder to Use JSONSchemaFormat

**Files:**
- Modify: `src/structured_agents/grammar/builders/qwen3.py:72-108`

**Step 1: Read the current implementation**

Run: `cat src/structured_agents/grammar/builders/qwen3.py`

**Step 2: Write the failing test**

```python
# tests/test_grammar/test_qwen3_json_schema_format.py
"""Tests for Qwen3 JSONSchemaFormat with qwen_xml style."""
from structured_agents.grammar.builders.qwen3 import Qwen3GrammarBuilder
from structured_agents.grammar.config import GrammarConfig
from structured_agents.types import ToolSchema


def test_structural_tag_uses_json_schema_format():
    """Test that structural_tag mode uses JSONSchemaFormat with qwen_xml style."""
    builder = Qwen3GrammarBuilder()
    config = GrammarConfig(mode="structural_tag", allow_parallel_calls=False)
    
    tool = ToolSchema(
        name="calculator",
        description="Calculator tool",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["add", "subtract"]},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
        },
    )
    
    grammar = builder.build([tool], config)
    assert grammar is not None
    
    # The grammar should contain JSONSchemaFormat, not GrammarFormat
    # Check that it uses JSON schema with qwen_xml style
    import json
    tag_json = grammar.tag.model_dump_json()
    tag_dict = json.loads(tag_json)
    
    # Verify the structure uses JSONSchemaFormat
    format_type = tag_dict.get("format", {}).get("type")
    elements = tag_dict.get("format", {}).get("elements", [{}])
    if elements:
        content = elements[0].get("content", {})
        # Should be JSONSchemaFormat, not GrammarFormat
        assert content.get("type") == "json_schema", f"Expected json_schema format, got {content.get('type')}"
        assert content.get("style") == "qwen_xml", f"Expected qwen_xml style, got {content.get('style')}"
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_grammar/test_qwen3_json_schema_format.py -v`

Expected: FAIL - current implementation uses GrammarFormat

**Step 4: Implement the fix**

Modify `src/structured_agents/grammar/builders/qwen3.py`:

```python
from xgrammar.structural_tag import (
    GrammarFormat,
    JSONSchemaFormat,
    OrFormat,
    SequenceFormat,
    TagFormat,
)

def _build_structural_tag(
    self, tools: list[ToolSchema], config: GrammarConfig
) -> StructuralTagGrammar:
    """Build structural tag grammar for Qwen3 format.
    
    Uses JSONSchemaFormat with style="qwen_xml" to allow both
    JSON and XML-style parameter formats.
    """
    tool_tags = []
    for tool in tools:
        # Use JSONSchemaFormat with qwen_xml style
        args_schema = JSONSchemaFormat(
            json_schema=tool.parameters,
            style="qwen_xml",
        )
        tool_tags.append(
            TagFormat(
                begin=f"<function={tool.name}>",
                content=args_schema,
                end="</function>",
            )
        )

    if len(tool_tags) == 1:
        tag_choice = tool_tags[0]
    else:
        tag_choice = OrFormat(elements=tool_tags)

    if config.allow_parallel_calls:
        format_spec = SequenceFormat(elements=[tag_choice])
    else:
        format_spec = tag_choice

    structural_tag = StructuralTag(format=format_spec)
    return StructuralTagGrammar(tag=structural_tag)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_grammar/test_qwen3_json_schema_format.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/structured_agents/grammar/builders/qwen3.py tests/test_grammar/test_qwen3_json_schema_format.py
git commit -m "fix(qwen3): use JSONSchemaFormat with qwen_xml style for structural_tag mode"
```

---

### Task 2: Test Existing Demo Scripts

**Files:**
- Test: `demo/demo_steps/test_grammar_modes.py`
- Test: `demo/demo_steps/step07_grammar_decoding.py`
- Test: `demo/demo_steps/step08_shell_agent_single.py`
- Test: `demo/demo_steps/step09_shell_agent_extended.py`

**Step 1: Run test_grammar_modes.py with structural_tag**

Run: `cd demo/demo_steps && python test_grammar_modes.py`

Expected: structural_tag mode should now properly parse tool call arguments

**Step 2: Run step07_grammar_decoding.py with each mode**

Run each mode separately:
- `python -c "import asyncio; from test_grammar_modes import test_grammar_mode; asyncio.run(test_grammar_mode('ebnf', 'What is 5 + 3?'))"`
- `python -c "import asyncio; from test_grammar_modes import test_grammar_mode; asyncio.run(test_grammar_mode('structural_tag', 'What is 5 + 3?'))"`

Expected: Both modes should produce valid tool calls with correct arguments

**Step 3: Run step08 and step09**

Run: `python step08_shell_agent_single.py`
Run: `python step09_shell_agent_extended.py`

Expected: Both should work with tool calling

**Step 4: Commit**

```bash
git add demo/demo_steps/
git commit -m "test: verify grammar modes work with Qwen3 tool calling"
```

---

### Task 3: Create Challenging Demo Scripts

**Files:**
- Create: `demo/demo_steps/step12_calculator_agent.py` - Complex calculator with multiple operations
- Create: `demo/demo_steps/step13_filesystem_agent.py` - File operations (read, write, list)
- Create: `demo/demo_steps/step14_weather_agent.py` - Multi-step reasoning with multiple tools

**Step 1: Create calculator agent with many operations**

```python
# demo/demo_steps/step12_calculator_agent.py
"""Step 12: Calculator agent with complex operations."""
import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin, ToolSchema
from structured_agents.client.factory import build_client
from structured_agents.grammar.config import GrammarConfig


CALCULATOR_TOOLS = [
    ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="subtract",
        description="Subtract b from a",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="multiply",
        description="Multiply two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="divide",
        description="Divide a by b",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
    ToolSchema(
        name="power",
        description="Raise a to the power of b",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
]


async def test_calculator(plugin, client, prompt: str):
    messages = [
        Message(role="developer", content="You are a calculator. Use the appropriate tool."),
        Message(role="user", content=prompt),
    ]
    
    formatted = plugin.format_messages(messages, CALCULATOR_TOOLS)
    formatted_tools = plugin.format_tools(CALCULATOR_TOOLS)
    grammar = plugin.build_grammar(CALCULATOR_TOOLS, GrammarConfig(mode="structural_tag"))
    extra_body = plugin.to_extra_body(grammar)
    
    response = await client.chat_completion(
        messages=formatted,
        tools=formatted_tools,
        tool_choice="auto",
        extra_body=extra_body,
    )
    
    content, tool_calls = plugin.parse_response(response.content, response.tool_calls)
    return content, tool_calls


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    client = build_client(config)
    plugin = QwenPlugin()
    
    # Test various operations
    prompts = [
        "What is 15 + 27?",
        "Calculate 100 minus 37",
        "Multiply 12 by 8",
        "Divide 144 by 12",
        "What is 2 to the power of 10?",
    ]
    
    for prompt in prompts:
        print(f"\n=== {prompt} ===")
        content, tool_calls = await test_calculator(plugin, client, prompt)
        if tool_calls:
            tc = tool_calls[0]
            print(f"Tool: {tc.name}, Args: {tc.arguments}")
        else:
            print(f"No tool call: {content}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Create filesystem agent**

```python
# demo/demo_steps/step13_filesystem_agent.py
"""Step 13: Filesystem agent with read, write, list operations."""
# Similar structure to calculator agent with file tools
```

**Step 3: Create weather agent with multi-step reasoning**

```python
# demo/demo_steps/step14_weather_agent.py
"""Step 14: Weather agent requiring multi-step reasoning."""
# Tools: get_weather, get_forecast, compare_cities
# Requires the model to reason about multiple cities and timeframes
```

**Step 4: Run all new demos**

Run each demo and verify:
- Tool selection is correct
- Arguments are properly parsed
- Model handles complex prompts

**Step 5: Commit**

```bash
git add demo/demo_steps/step12_*.py demo/demo_steps/step13_*.py demo/demo_steps/step14_*.py
git commit -m "feat(demos): add challenging tool calling demos"
```

---

### Task 4: Verify All Grammar Modes Work

**Step 1: Test all three grammar modes**

Run the test script with all modes and verify:
- ebnf: Works but may have empty args issue
- structural_tag: Should now work with our fix
- json_schema: May have issues (document findings)

**Step 2: Create summary**

Document which modes work and any workarounds needed.

**Step 3: Commit**

```bash
git commit --amend -m "feat(demos): add challenging tool calling demos"
```
