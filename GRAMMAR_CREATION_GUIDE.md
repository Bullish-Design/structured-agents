# Grammar-Constrained Decoding Guide

A comprehensive developer guide for the grammar-constrained decoding system in `structured-agents`.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Architecture](#3-architecture)
4. [GrammarConfig Reference](#4-grammarconfig-reference)
5. [Grammar Modes](#5-grammar-modes)
6. [xgrammar Format Types](#6-xgrammar-format-types)
7. [Existing Builders](#7-existing-builders)
8. [Creating a Custom Builder](#8-creating-a-custom-builder)
9. [The send_tools_to_api Interaction](#9-the-send_tools_to_api-interaction)
10. [Common Pitfalls](#10-common-pitfalls)
11. [Testing Grammar Builders](#11-testing-grammar-builders)

---

## 1. Overview

### What is Grammar-Constrained Decoding?

Grammar-constrained decoding restricts the tokens an LLM can generate at each step so that its output always conforms to a predefined format. Instead of hoping the model produces valid tool calls, the grammar makes it structurally impossible to produce invalid ones.

### Why It Matters for Tool Calling

LLMs can hallucinate tool names, produce malformed arguments, or mix free text into structured regions. Grammar constraints eliminate these failure modes:

- **Tool names** are restricted to exactly the set of registered tools.
- **Arguments** conform to parameter schemas (types, required fields, valid values).
- **Delimiters** (XML tags, JSON braces) are always properly balanced.

### How structured-agents Uses It

The system runs xgrammar (vendored at v0.1.29) inside vLLM (vendored at v0.15.1). The flow works as follows:

1. A `GrammarConfig` (from `bundle.yaml` or code) specifies the grammar mode.
2. A model-specific `GrammarBuilder` converts tool schemas into a grammar artifact.
3. The artifact is serialized into the `extra_body` dict sent to vLLM.
4. vLLM's xgrammar backend compiles the grammar and applies token-level constraints during generation.
5. The model's constrained output is parsed back into structured `ToolCall` objects.

---

## 2. Quick Start

### Minimal bundle.yaml

The grammar section lives under `model.grammar` in your bundle configuration:

**EBNF mode** (maximum flexibility, raw EBNF grammar):

```yaml
model:
  plugin: "qwen"
  grammar:
    mode: "ebnf"
    allow_parallel_calls: true
    send_tools_to_api: false  # REQUIRED for ebnf mode
```

**Structural tag mode** (recommended for Qwen3, uses xgrammar's optimized format):

```yaml
model:
  plugin: "qwen"
  grammar:
    mode: "structural_tag"
    allow_parallel_calls: true
    send_tools_to_api: true
```

**JSON schema mode** (strictest type safety):

```yaml
model:
  plugin: "qwen"
  grammar:
    mode: "json_schema"
    allow_parallel_calls: true
    send_tools_to_api: false
```

### Using GrammarConfig in Code

```python
from structured_agents.grammar.config import GrammarConfig
from structured_agents.kernel import AgentKernel
from structured_agents.types import KernelConfig

kernel = AgentKernel(
    config=KernelConfig(
        base_url="http://localhost:8000/v1",
        model="Qwen/Qwen3-8B",
    ),
    plugin=QwenPlugin(),
    tool_source=my_tool_source,
    grammar_config=GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=True,
    ),
)
```

The kernel uses the grammar config at every `step()` call to build and send grammar constraints to vLLM.

---

## 3. Architecture

### Data Flow

```
bundle.yaml
    |
    v
GrammarConfig                         (src/structured_agents/grammar/config.py:7-14)
    |
    v
AgentKernel.step()                    (src/structured_agents/kernel.py:108-165)
    |
    +---> plugin.build_grammar(tools, config)
    |         |
    |         v
    |     GrammarBuilder.build()      (src/structured_agents/grammar/builders/protocol.py:13)
    |         |
    |         v
    |     GrammarArtifact             (src/structured_agents/grammar/artifacts.py:54)
    |         |
    |         v
    +---> artifact.to_vllm_payload()  (src/structured_agents/grammar/artifacts.py:16-51)
    |         |
    |         v
    |     extra_body dict  {"structured_outputs": {...}}
    |         |
    |         v
    +---> client.chat_completion(extra_body=...)
              |                       (src/structured_agents/client/openai_compat.py:28-37)
              v
          vLLM server
              |
              v
          XgrammarBackend.compile_grammar()
              |                       (.context/vllm/vllm-0.15.1/vllm/v1/structured_output/backend_xgrammar.py:99-144)
              v
          Token-constrained generation
              |
              v
          response
              |
              v
          plugin.parse_response()     (src/structured_agents/plugins/protocol.py:80-94)
              |
              v
          (content, list[ToolCall])
```

### Key Source Files

| File | Description | Lines |
|------|-------------|-------|
| `src/structured_agents/grammar/config.py` | `GrammarConfig` dataclass | 25 |
| `src/structured_agents/grammar/artifacts.py` | Three artifact types + `to_vllm_payload()` | 55 |
| `src/structured_agents/grammar/builders/protocol.py` | `GrammarBuilder` protocol | 28 |
| `src/structured_agents/grammar/builders/qwen3.py` | `Qwen3GrammarBuilder` | 138 |
| `src/structured_agents/grammar/builders/function_gemma.py` | `FunctionGemmaGrammarBuilder` | 128 |
| `src/structured_agents/grammar/utils.py` | `escape_ebnf_string`, `validate_ebnf` | 32 |
| `src/structured_agents/plugins/protocol.py` | `ModelPlugin` protocol | 95 |
| `src/structured_agents/plugins/composed.py` | `ComposedModelPlugin` base class | 72 |
| `src/structured_agents/plugins/qwen.py` | `QwenPlugin` (default: `structural_tag`) | 36 |
| `src/structured_agents/plugins/function_gemma.py` | `FunctionGemmaPlugin` | 25 |
| `src/structured_agents/kernel.py` | `AgentKernel.step()` at lines 108-165 | 425 |
| `src/structured_agents/client/openai_compat.py` | `OpenAICompatibleClient` | 120 |

### How the Kernel Uses Grammar

From `src/structured_agents/kernel.py:108-165`:

```python
async def step(self, messages, tools, context=None, turn=1, model=None) -> StepResult:
    # 1. Resolve tools from names or schemas
    resolved_tools = self._resolve_tools(tools)

    # 2. Format messages for the model
    formatted_messages = self.plugin.format_messages(messages, resolved_tools)

    # 3. Conditionally format tools for API (depends on send_tools_to_api)
    formatted_tools = (
        self.plugin.format_tools(resolved_tools)
        if resolved_tools and self.grammar_config.send_tools_to_api
        else None
    )

    # 4. Build grammar artifact
    grammar = (
        self.plugin.build_grammar(resolved_tools, self.grammar_config)
        if resolved_tools
        else None
    )

    # 5. Convert to extra_body for vLLM
    extra_body = self.plugin.to_extra_body(grammar)

    # 6. Send to vLLM
    response = await self._client.chat_completion(
        messages=formatted_messages,
        tools=formatted_tools,
        extra_body=extra_body,
        ...
    )

    # 7. Parse response
    content, tool_calls = self.plugin.parse_response(
        response.content, response.tool_calls,
    )
```

---

## 4. GrammarConfig Reference

Defined in `src/structured_agents/grammar/config.py:7-14`:

```python
@dataclass(frozen=True, slots=True)
class GrammarConfig:
    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = True
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"
    send_tools_to_api: bool = True
```

### Fields

#### `mode`

**Type:** `Literal["ebnf", "structural_tag", "json_schema"]`
**Default:** `"ebnf"`

Selects the grammar compilation strategy:

| Mode | Artifact Type | Description |
|------|--------------|-------------|
| `"ebnf"` | `EBNFGrammar` | Raw EBNF grammar string compiled by xgrammar |
| `"structural_tag"` | `StructuralTagGrammar` | xgrammar's native structural tag format |
| `"json_schema"` | `JsonSchemaGrammar` | JSON Schema constraint |

#### `allow_parallel_calls`

**Type:** `bool`
**Default:** `True`

Controls whether the grammar allows the model to emit multiple tool calls in a single response.

- `True`: Root rule uses `+` (one or more) -- e.g., `root ::= tool_call+`
- `False`: Root rule matches exactly one call -- e.g., `root ::= tool_call`

For structural_tag mode, this controls the `stop_after_first` parameter on `TriggeredTagsFormat`.

#### `args_format`

**Type:** `Literal["permissive", "escaped_strings", "json"]`
**Default:** `"permissive"`

Controls argument grammar strictness (primarily used by `FunctionGemmaGrammarBuilder`):

| Format | Grammar Pattern | Use Case |
|--------|----------------|----------|
| `"permissive"` | `[^}]*` or `[^<]+` | Fast, accepts any text within delimiters |
| `"escaped_strings"` | `<escape>` delimited strings | FunctionGemma-specific escaping |
| `"json"` | Full JSON grammar | Strict JSON argument validation |

#### `send_tools_to_api`

**Type:** `bool`
**Default:** `True`

Whether to include the `tools` parameter in the OpenAI-compatible API request. See [Section 9](#9-the-send_tools_to_api-interaction) for critical details on how this interacts with grammar modes.

---

## 5. Grammar Modes

### 5.1 EBNF Mode

**How it works:** The builder generates an EBNF grammar string that defines the exact syntax the model must produce. xgrammar compiles this into a token-level constraint.

**Artifact produced:** `EBNFGrammar` (`src/structured_agents/grammar/artifacts.py:10-21`)

```python
@dataclass(frozen=True, slots=True)
class EBNFGrammar:
    grammar: str

    def to_vllm_payload(self) -> dict[str, Any]:
        return {"structured_outputs": {"grammar": self.grammar}}
```

**How vLLM processes it:** The `extra_body` arrives as `{"structured_outputs": {"grammar": "<ebnf string>"}}`. vLLM maps this to `StructuredOutputOptions.GRAMMAR` and calls `self.compiler.compile_grammar(grammar_spec)` (`.context/vllm/vllm-0.15.1/vllm/v1/structured_output/backend_xgrammar.py:110-111`).

**Example EBNF output** (Qwen3, two tools):

```
root ::= tool_call+

tool_call ::= "<function=" tool_name ">" parameters "</function>"

tool_name ::= "get_weather" | "search"

parameters ::= (parameter)*
parameter ::= "<parameter=" param_name ">" param_value "</parameter>"
param_name ::= [a-zA-Z_][a-zA-Z0-9_]*
param_value ::= [^<]+
```

**Trade-offs:**

| Advantage | Disadvantage |
|-----------|-------------|
| Full control over syntax | No per-parameter type constraints (permissive mode) |
| Works with any model format | Must set `send_tools_to_api=False` (see [Section 9](#9-the-send_tools_to_api-interaction)) |
| Easy to debug (readable grammar) | Slower compilation for complex grammars |

**When to use:** When you need a custom output format that does not fit structural tags or JSON schema, or when debugging grammar behavior.

### 5.2 Structural Tag Mode

**How it works:** The builder constructs an xgrammar `StructuralTag` object using the format types from `xgrammar.structural_tag`. This is xgrammar's native, optimized representation for structured output with interleaved free text.

**Artifact produced:** `StructuralTagGrammar` (`src/structured_agents/grammar/artifacts.py:24-35`)

```python
@dataclass(frozen=True, slots=True)
class StructuralTagGrammar:
    tag: StructuralTag

    def to_vllm_payload(self) -> dict[str, Any]:
        return {"structured_outputs": {"structural_tag": self.tag.model_dump_json()}}
```

**How vLLM processes it:** The payload arrives as `{"structured_outputs": {"structural_tag": "<json string>"}}`. vLLM parses the JSON and calls `self.compiler.compile_structural_tag(grammar_spec)` (`.context/vllm/vllm-0.15.1/vllm/v1/structured_output/backend_xgrammar.py:114-128`).

**Trade-offs:**

| Advantage | Disadvantage |
|-----------|-------------|
| Optimized compilation in xgrammar | Must use `TriggeredTagsFormat` at top level |
| Per-parameter type constraints (via `QwenXMLParameterFormat` or `JSONSchemaFormat`) | Format type nesting rules are strict |
| Supports free text between tool calls | Requires understanding xgrammar format types |
| Compatible with `send_tools_to_api=True` | |

**When to use:** Recommended default for models with tag-based tool calling (Qwen3, FunctionGemma). Provides the best balance of type safety and flexibility.

### 5.3 JSON Schema Mode

**How it works:** The builder constructs a JSON Schema that describes the expected output structure. xgrammar compiles this into a grammar that only accepts valid JSON matching the schema.

**Artifact produced:** `JsonSchemaGrammar` (`src/structured_agents/grammar/artifacts.py:38-51`)

```python
@dataclass(frozen=True, slots=True)
class JsonSchemaGrammar:
    schema: dict[str, Any]

    def to_vllm_payload(self) -> dict[str, Any]:
        return {"structured_outputs": {"json": {"json_schema": self.schema}}}
```

**How vLLM processes it:** The payload arrives as `{"structured_outputs": {"json": {"json_schema": {...}}}}`. vLLM maps this to `StructuredOutputOptions.JSON` and calls `self.compiler.compile_json_schema(grammar_spec)` (`.context/vllm/vllm-0.15.1/vllm/v1/structured_output/backend_xgrammar.py:102-105`).

**Example schema** (Qwen3, two tools):

```json
{
  "type": "array",
  "items": {
    "anyOf": [
      {
        "type": "object",
        "properties": {
          "name": {"const": "get_weather"},
          "arguments": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"]
          }
        },
        "required": ["name", "arguments"]
      },
      {
        "type": "object",
        "properties": {
          "name": {"const": "search"},
          "arguments": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
          }
        },
        "required": ["name", "arguments"]
      }
    ]
  }
}
```

**Trade-offs:**

| Advantage | Disadvantage |
|-----------|-------------|
| Strictest type safety | Output is pure JSON (no free text) |
| Schema reusable from OpenAI format | Not all builders support it (e.g., FunctionGemma does not) |
| Well-understood format | Single-tool case produces object, not array |

**When to use:** When you need guaranteed JSON output with full type validation, and the model supports JSON-formatted tool calls.

---

## 6. xgrammar Format Types

All types are defined in `.context/xgrammar-0.1.29/python/xgrammar/structural_tag.py`. They form the `Format` discriminated union (line 221-236) used inside `StructuralTag.format`.

### Basic Formats

#### `ConstStringFormat` (lines 18-24)

Matches an exact constant string.

```python
from xgrammar.structural_tag import ConstStringFormat

fmt = ConstStringFormat(value="hello world")
# Accepts only: "hello world"
```

**Fields:**
- `value: str` -- The exact string to match.

#### `JSONSchemaFormat` (lines 27-33)

Matches JSON conforming to a JSON Schema.

```python
from xgrammar.structural_tag import JSONSchemaFormat

fmt = JSONSchemaFormat(json_schema={
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
})
# Accepts: {"name": "Alice", "age": 30}
```

**Fields:**
- `json_schema: Union[bool, Dict[str, Any]]` -- The JSON Schema definition.

#### `QwenXMLParameterFormat` (lines 36-66)

Matches Qwen-style XML function call parameters. Each parameter is encoded as `<parameter=name>value</parameter>`.

```python
from xgrammar.structural_tag import QwenXMLParameterFormat

fmt = QwenXMLParameterFormat(json_schema={
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
})
# Accepts: <parameter=name>Bob</parameter><parameter=age>100</parameter>
```

**Fields:**
- `json_schema: Union[bool, Dict[str, Any]]` -- JSON Schema for the parameters.

#### `AnyTextFormat` (lines 68-72)

Matches any text (no constraint).

```python
from xgrammar.structural_tag import AnyTextFormat

fmt = AnyTextFormat()
# Accepts anything
```

**Fields:** None.

#### `GrammarFormat` (lines 75-82)

Matches text conforming to an EBNF grammar.

```python
from xgrammar.structural_tag import GrammarFormat

fmt = GrammarFormat(grammar="root ::= [a-zA-Z]+")
# Accepts: any sequence of letters
```

**Fields:**
- `grammar: str` -- An EBNF grammar string.

#### `RegexFormat` (lines 85-92)

Matches text conforming to a regex pattern.

```python
from xgrammar.structural_tag import RegexFormat

fmt = RegexFormat(pattern=r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# Accepts: 2025-01-15
```

**Fields:**
- `pattern: str` -- A regex pattern.

### Combinatorial Formats

#### `SequenceFormat` (lines 98-104)

Matches an ordered sequence of formats.

```python
from xgrammar.structural_tag import SequenceFormat, ConstStringFormat, AnyTextFormat

fmt = SequenceFormat(elements=[
    ConstStringFormat(value="BEGIN:"),
    AnyTextFormat(),
    ConstStringFormat(value=":END"),
])
# Accepts: BEGIN:<any text>:END
```

**Fields:**
- `elements: List[Format]` -- Ordered list of sub-formats.

#### `OrFormat` (lines 107-113)

Matches one of several formats.

```python
from xgrammar.structural_tag import OrFormat, ConstStringFormat

fmt = OrFormat(elements=[
    ConstStringFormat(value="yes"),
    ConstStringFormat(value="no"),
])
# Accepts: "yes" or "no"
```

**Fields:**
- `elements: List[Format]` -- List of alternative formats.

**Warning:** Do NOT use `OrFormat` as the top-level format for tool calling. vLLM requires `TriggeredTagsFormat` at the top level. See [Section 10](#10-common-pitfalls).

#### `TagFormat` (lines 116-126)

Matches `begin + content + end`. This is the building block for individual tool call tags.

```python
from xgrammar.structural_tag import TagFormat, JSONSchemaFormat

fmt = TagFormat(
    begin="<function=get_weather>",
    content=JSONSchemaFormat(json_schema={"type": "object", "properties": {"city": {"type": "string"}}}),
    end="</function>",
)
# Accepts: <function=get_weather>{"city": "London"}</function>
```

**Fields:**
- `begin: str` -- Opening delimiter.
- `content: Format` -- Any format type for the content between delimiters.
- `end: str` -- Closing delimiter.

#### `TriggeredTagsFormat` (lines 129-177)

Allows free text until a trigger prefix is encountered, then dispatches to the matching tag. This is the **required** top-level format for structural tag tool calling.

```python
from xgrammar.structural_tag import TriggeredTagsFormat, TagFormat, JSONSchemaFormat

fmt = TriggeredTagsFormat(
    triggers=["<function="],
    tags=[
        TagFormat(
            begin="<function=get_weather>",
            content=JSONSchemaFormat(json_schema={"type": "object", "properties": {"city": {"type": "string"}}}),
            end="</function>",
        ),
        TagFormat(
            begin="<function=search>",
            content=JSONSchemaFormat(json_schema={"type": "object", "properties": {"query": {"type": "string"}}}),
            end="</function>",
        ),
    ],
    at_least_one=True,
    stop_after_first=False,
)
# Accepts: any_text<function=get_weather>{"city": "London"}</function>more_text<function=search>{"query": "foo"}</function>
```

**Fields:**
- `triggers: List[str]` -- Prefix strings that activate tag matching. Each trigger must be a prefix of at least one tag's `begin`.
- `tags: List[TagFormat]` -- The tags to dispatch to.
- `at_least_one: bool` (default `False`) -- Whether at least one tag must appear.
- `stop_after_first: bool` (default `False`) -- Whether to stop after the first tag (disables parallel calls).

#### `TagsWithSeparatorFormat` (lines 180-215)

Matches tags separated by a fixed separator, with no free text between them.

```python
from xgrammar.structural_tag import TagsWithSeparatorFormat, TagFormat, JSONSchemaFormat

fmt = TagsWithSeparatorFormat(
    tags=[
        TagFormat(
            begin="<function=func1>",
            content=JSONSchemaFormat(json_schema={"type": "object"}),
            end="</function>",
        ),
        TagFormat(
            begin="<function=func2>",
            content=JSONSchemaFormat(json_schema={"type": "object"}),
            end="</function>",
        ),
    ],
    separator=",",
    at_least_one=False,
    stop_after_first=False,
)
# Accepts: <function=func1>{}</function>,<function=func2>{}</function>
```

**Fields:**
- `tags: List[TagFormat]` -- The tags.
- `separator: str` -- String separating consecutive tags.
- `at_least_one: bool` (default `False`) -- Whether at least one tag must appear.
- `stop_after_first: bool` (default `False`) -- Whether to stop after the first tag.

### Top-Level Wrapper

#### `StructuralTag` (lines 273-314)

The top-level wrapper that vLLM expects. Contains a `type` field (always `"structural_tag"`) and a `format` field (any `Format` type).

```python
from xgrammar import StructuralTag
from xgrammar.structural_tag import TriggeredTagsFormat, TagFormat, QwenXMLParameterFormat

tag = StructuralTag(
    format=TriggeredTagsFormat(
        triggers=["<function="],
        tags=[
            TagFormat(
                begin="<function=get_weather>",
                content=QwenXMLParameterFormat(json_schema={...}),
                end="</function>",
            )
        ],
        at_least_one=True,
    )
)
```

---

## 7. Existing Builders

### 7.1 Qwen3GrammarBuilder

**File:** `src/structured_agents/grammar/builders/qwen3.py`
**Supported modes:** `ebnf`, `structural_tag`, `json_schema`

The Qwen3 builder targets the Qwen3 tool calling format:

```
<function=tool_name>
<parameter=param_name>param_value</parameter>
</function>
```

#### EBNF mode (lines 42-69)

Generates a grammar where each tool call is wrapped in `<function=...>...</function>` tags with `<parameter=...>...</parameter>` for arguments:

```python
def _build_ebnf(self, tools, config):
    tool_names = [escape_ebnf_string(tool.name) for tool in tools]
    tool_alts = " | ".join(f'"{name}"' for name in tool_names)

    root_rule = "root ::= tool_call+" if config.allow_parallel_calls else "root ::= tool_call"

    grammar = "\n".join([
        root_rule,
        "",
        'tool_call ::= "<function=" tool_name ">" parameters "</function>"',
        "",
        f"tool_name ::= {tool_alts}",
        "",
        "parameters ::= (parameter)*",
        'parameter ::= "<parameter=" param_name ">" param_value "</parameter>"',
        "param_name ::= [a-zA-Z_][a-zA-Z0-9_]*",
        "param_value ::= [^<]+",
    ])
    return EBNFGrammar(grammar=grammar)
```

Note that the EBNF mode uses `[^<]+` for parameter values (permissive -- accepts any text that is not `<`). It does not enforce per-parameter type constraints.

#### Structural tag mode (lines 71-104)

Uses `TriggeredTagsFormat` with `QwenXMLParameterFormat` for type-safe parameter encoding:

```python
def _build_structural_tag(self, tools, config):
    tool_tags = []
    for tool in tools:
        tool_tags.append(
            TagFormat(
                begin=f"<function={tool.name}>",
                content=QwenXMLParameterFormat(json_schema=tool.parameters),
                end="</function>",
            )
        )

    structural_tag = StructuralTag(
        format=TriggeredTagsFormat(
            triggers=["<function="],
            tags=tool_tags,
            at_least_one=True,
            stop_after_first=not config.allow_parallel_calls,
        )
    )
    return StructuralTagGrammar(tag=structural_tag)
```

Key details:
- The trigger `"<function="` is a common prefix for all tool tags.
- `at_least_one=True` ensures the model produces at least one tool call.
- `stop_after_first` is set based on `allow_parallel_calls`.
- `QwenXMLParameterFormat` uses the tool's JSON Schema to enforce parameter types.

#### JSON schema mode (lines 112-137)

Generates a JSON Schema where each tool call is an object with `name` (const) and `arguments` (from tool parameters):

```python
def _build_json_schema(self, tools, config):
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

    if len(tool_choices) > 1:
        schema = {"type": "array", "items": {"anyOf": tool_choices}}
    else:
        schema = tool_choices[0]

    return JsonSchemaGrammar(schema=schema)
```

Note: When there is only one tool, the schema is a single object (not an array). When there are multiple tools, it becomes an array of `anyOf`.

### 7.2 FunctionGemmaGrammarBuilder

**File:** `src/structured_agents/grammar/builders/function_gemma.py`
**Supported modes:** `ebnf`, `structural_tag` (no `json_schema`)

The FunctionGemma builder targets the FunctionGemma format:

```
<start_function_call>call:tool_name{arg_body}<end_function_call>
```

#### EBNF mode (lines 31-62)

Generates EBNF with three `args_format` variants:

**Permissive** (`args_format="permissive"`):
```
arg_body ::= [^}]*
```

**Escaped strings** (`args_format="escaped_strings"`, lines 102-113):
```
arg_body ::= (arg_pair ("," arg_pair)*)?
arg_pair ::= arg_name ":" arg_value
arg_name ::= [a-zA-Z_][a-zA-Z0-9_]*
arg_value ::= escaped_string | number | "true" | "false" | "null"
escaped_string ::= "<escape>" [^<]* "<escape>"
number ::= "-"? [0-9]+ ("." [0-9]+)?
```

**JSON** (`args_format="json"`, lines 115-127):
```
arg_body ::= (pair ("," pair)*)?
pair ::= string ":" value
string ::= "\"" [^\"]* "\""
value ::= string | number | object | array | "true" | "false" | "null"
object ::= "{" (pair ("," pair)*)? "}"
array ::= "[" (value ("," value)*)? "]"
number ::= "-"? [0-9]+ ("." [0-9]+)?
```

#### Structural tag mode (lines 64-94)

Uses `TriggeredTagsFormat` with `GrammarFormat` (EBNF) for argument content:

```python
def _build_structural_tag(self, tools, config):
    tool_formats = []
    for tool in tools:
        args_grammar = self._build_args_grammar_for_tool(tool, config)
        tool_formats.append(
            TagFormat(
                begin=f"<start_function_call>call:{tool.name}{{",
                content=GrammarFormat(grammar=args_grammar),
                end="}<end_function_call>",
            )
        )

    tag = StructuralTag(
        format=TriggeredTagsFormat(
            triggers=["<start_function_call>call:"],
            tags=tool_formats,
            at_least_one=True,
            stop_after_first=not config.allow_parallel_calls,
        )
    )
    return StructuralTagGrammar(tag=tag)
```

Key differences from Qwen3:
- The trigger is `"<start_function_call>call:"` (longer prefix).
- Arguments use `GrammarFormat` (EBNF inside the tag) instead of `QwenXMLParameterFormat`.
- The opening brace `{` is part of the `begin` string; the closing `}` is part of `end`.

---

## 8. Creating a Custom Builder

### Step 1: Implement the GrammarBuilder Protocol

The protocol is defined in `src/structured_agents/grammar/builders/protocol.py:10-27`:

```python
class GrammarBuilder(Protocol):
    def build(self, tools: list[ToolSchema], config: GrammarConfig) -> GrammarArtifact:
        ...

    def supports_mode(self, mode: str) -> bool:
        ...
```

You need exactly two methods:
- `build()`: Takes tool schemas and config, returns a `GrammarArtifact` (or `None` if no tools).
- `supports_mode()`: Returns whether this builder handles a given mode string.

### Step 2: Choose Your Artifact Type

Depending on the mode, return one of:
- `EBNFGrammar(grammar=<ebnf_string>)`
- `StructuralTagGrammar(tag=<StructuralTag>)`
- `JsonSchemaGrammar(schema=<dict>)`

### Step 3: Complete Example

Here is a complete builder for a hypothetical model that uses `[TOOL:name]args[/TOOL]` format:

```python
"""Grammar builder for hypothetical BracketTool model format."""

from __future__ import annotations

from structured_agents.grammar.artifacts import (
    EBNFGrammar,
    GrammarArtifact,
    StructuralTagGrammar,
)
from structured_agents.grammar.config import GrammarConfig
from structured_agents.grammar.utils import escape_ebnf_string
from structured_agents.types import ToolSchema

from xgrammar import StructuralTag
from xgrammar.structural_tag import (
    GrammarFormat,
    JSONSchemaFormat,
    TagFormat,
    TriggeredTagsFormat,
)


class BracketToolGrammarBuilder:
    """Grammar builder for BracketTool model format.

    Output format:
        [TOOL:tool_name]{"key": "value"}[/TOOL]
    """

    def supports_mode(self, mode: str) -> bool:
        return mode in ("ebnf", "structural_tag")

    def build(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> GrammarArtifact | None:
        if not tools:
            return None

        if config.mode == "structural_tag":
            return self._build_structural_tag(tools, config)

        return self._build_ebnf(tools, config)

    def _build_ebnf(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> EBNFGrammar:
        tool_names = [escape_ebnf_string(tool.name) for tool in tools]
        tool_alts = " | ".join(f'"{name}"' for name in tool_names)

        root_rule = (
            "root ::= tool_call+"
            if config.allow_parallel_calls
            else "root ::= tool_call"
        )

        grammar = "\n".join([
            root_rule,
            "",
            'tool_call ::= "[TOOL:" tool_name "]" args "[/TOOL]"',
            "",
            f"tool_name ::= {tool_alts}",
            "",
            "args ::= [^\\[]*",  # permissive: anything that is not '['
        ])

        return EBNFGrammar(grammar=grammar)

    def _build_structural_tag(
        self, tools: list[ToolSchema], config: GrammarConfig
    ) -> StructuralTagGrammar:
        tool_tags = []
        for tool in tools:
            tool_tags.append(
                TagFormat(
                    begin=f"[TOOL:{tool.name}]",
                    content=JSONSchemaFormat(json_schema=tool.parameters),
                    end="[/TOOL]",
                )
            )

        tag = StructuralTag(
            format=TriggeredTagsFormat(
                triggers=["[TOOL:"],
                tags=tool_tags,
                at_least_one=True,
                stop_after_first=not config.allow_parallel_calls,
            )
        )
        return StructuralTagGrammar(tag=tag)
```

### Step 4: Wire It Into a Plugin

Create a `GrammarProvider` component (or use the builder directly in a `ComposedModelPlugin`):

```python
from structured_agents.plugins.composed import ComposedModelPlugin

class BracketToolPlugin(ComposedModelPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="bracket_tool",
            message_formatter=BracketToolMessageFormatter(),
            tool_formatter=BracketToolToolFormatter(),
            response_parser=BracketToolResponseParser(),
            grammar_provider=BracketToolGrammarProvider(),  # wraps BracketToolGrammarBuilder
        )
```

### Step 5: Register in bundle.yaml

```yaml
model:
  plugin: "bracket_tool"
  grammar:
    mode: "structural_tag"
    allow_parallel_calls: true
    send_tools_to_api: true
```

---

## 9. The `send_tools_to_api` Interaction

This is one of the most critical configuration details in the grammar system. The `send_tools_to_api` field controls whether the `tools` parameter is included in the OpenAI-compatible API request alongside the grammar constraint.

### What Happens in the Kernel

From `src/structured_agents/kernel.py:133-137`:

```python
formatted_tools = (
    self.plugin.format_tools(resolved_tools)
    if resolved_tools and self.grammar_config.send_tools_to_api
    else None
)
```

When `send_tools_to_api=True`, both `tools` (OpenAI format) and `extra_body.structured_outputs` (grammar) are sent. When `False`, only the grammar is sent.

### Interaction Matrix

| Mode | `send_tools_to_api` | What Happens | Result |
|------|---------------------|-------------|--------|
| `ebnf` | `True` | vLLM receives both `tools` and `grammar`. vLLM's tool calling overrides the EBNF grammar with its own JSON schema. | **BROKEN** -- your EBNF is ignored |
| `ebnf` | `False` | vLLM receives only `grammar`. EBNF is compiled and applied correctly. | Correct |
| `structural_tag` | `True` | vLLM receives both `tools` and `structural_tag`. Structural tag takes precedence over the tools parameter. | Correct |
| `structural_tag` | `False` | vLLM receives only `structural_tag`. Works correctly. Response parser must extract tool calls from raw content. | Correct |
| `json_schema` | `True` | vLLM receives both `tools` and `json` schema. May conflict with vLLM's own tool schema handling. | Potentially conflicting |
| `json_schema` | `False` | vLLM receives only `json` schema. Output is pure JSON, parsed by response parser. | Correct |

### Rules of Thumb

1. **EBNF mode MUST use `send_tools_to_api=False`.** There is no exception.
2. **Structural tag mode works with either setting**, but `True` allows vLLM to provide additional tool metadata to the model's chat template.
3. **JSON schema mode should use `send_tools_to_api=False`** to avoid conflicts between vLLM's native tool calling and the JSON schema constraint.

### Default Configurations

The `QwenPlugin` uses `structural_tag` mode with `send_tools_to_api=True` by default (`src/structured_agents/plugins/qwen.py:18-21`):

```python
DEFAULT_GRAMMAR_CONFIG = GrammarConfig(
    mode="structural_tag",
    allow_parallel_calls=True,
)
```

---

## 10. Common Pitfalls

### Pitfall 1: Using OrFormat or TagFormat as Top-Level Format

**Symptom:** `KeyError: 'triggers'` crash in vLLM's xgrammar backend.

**Cause:** vLLM's structural tag compilation path expects `TriggeredTagsFormat` (which has a `triggers` field) at the top level. If you use `OrFormat` wrapping multiple `TagFormat` instances, or a bare `TagFormat`, the backend crashes because it looks for `triggers` in the parsed JSON.

**Fix:** Always use `TriggeredTagsFormat` as the top-level format:

```python
# WRONG -- will crash vLLM
tag = StructuralTag(
    format=OrFormat(elements=[
        TagFormat(begin="<function=a>", content=..., end="</function>"),
        TagFormat(begin="<function=b>", content=..., end="</function>"),
    ])
)

# CORRECT
tag = StructuralTag(
    format=TriggeredTagsFormat(
        triggers=["<function="],
        tags=[
            TagFormat(begin="<function=a>", content=..., end="</function>"),
            TagFormat(begin="<function=b>", content=..., end="</function>"),
        ],
        at_least_one=True,
    )
)
```

### Pitfall 2: EBNF Mode with send_tools_to_api=True

**Symptom:** The model ignores your EBNF grammar and produces standard JSON tool calls instead.

**Cause:** When `tools` is sent alongside an EBNF grammar, vLLM's tool calling mechanism overrides the grammar with its own JSON schema constraint.

**Fix:** Set `send_tools_to_api=False` when using EBNF mode:

```yaml
model:
  grammar:
    mode: "ebnf"
    send_tools_to_api: false  # REQUIRED
```

### Pitfall 3: Trigger Must Be a Prefix of Tag Begin Strings

**Symptom:** xgrammar fails to match tool calls, or matches the wrong tool.

**Cause:** Each trigger in `TriggeredTagsFormat.triggers` must be an exact prefix of the `begin` field of at least one tag. xgrammar uses this prefix to dispatch to the correct tag grammar.

**Fix:** Ensure trigger is a common prefix:

```python
# WRONG -- trigger doesn't match begin
TriggeredTagsFormat(
    triggers=["<tool:"],
    tags=[
        TagFormat(begin="<function=get_weather>", ...),  # "<tool:" is not a prefix of "<function="
    ],
)

# CORRECT
TriggeredTagsFormat(
    triggers=["<function="],
    tags=[
        TagFormat(begin="<function=get_weather>", ...),  # "<function=" IS a prefix
    ],
)
```

### Pitfall 4: Mixing Content Format Types

**Symptom:** Grammar compiles but produces unexpected output structure.

**Cause:** Using the wrong content format type inside `TagFormat.content`. The three main options serve different purposes:

- `QwenXMLParameterFormat` -- for `<parameter=name>value</parameter>` format (Qwen3 only)
- `JSONSchemaFormat` -- for JSON content matching a schema
- `GrammarFormat` -- for content matching an EBNF grammar

Using `QwenXMLParameterFormat` in a FunctionGemma builder (which expects `key:value` pairs) would produce XML-formatted arguments that the FunctionGemma parser cannot read.

### Pitfall 5: Forgetting allow_parallel_calls Affects stop_after_first

**Symptom:** Model produces only one tool call when you expected multiple, or vice versa.

**Cause:** In structural tag mode, `allow_parallel_calls` maps to `stop_after_first`:

```python
stop_after_first = not config.allow_parallel_calls
```

When `stop_after_first=True`, the grammar stops accepting input after the first tool call's end tag, so only one call is generated.

### Pitfall 6: Empty Tools List

**Symptom:** `None` grammar artifact, no constraints applied.

**Cause:** All builders return `None` when the tools list is empty. The kernel also skips grammar building when there are no resolved tools (`src/structured_agents/kernel.py:139-142`).

This is correct behavior -- grammar constraints only apply when tools are available.

---

## 11. Testing Grammar Builders

### Test Structure

Existing tests follow a consistent pattern. See:
- `tests/test_grammar/test_qwen3_builder.py` (246 lines)
- `tests/test_grammar/test_function_gemma_builder.py` (74 lines)

### Helper Pattern

Create a helper to build `ToolSchema` instances:

```python
from structured_agents.types import ToolSchema

def _tool(name: str, parameters: dict | None = None) -> ToolSchema:
    return ToolSchema(
        name=name,
        description="Test tool",
        parameters=parameters or {"type": "object", "properties": {}},
    )
```

### What to Test

#### 1. Mode support

```python
def test_supports_mode() -> None:
    builder = MyGrammarBuilder()
    assert builder.supports_mode("ebnf") is True
    assert builder.supports_mode("structural_tag") is True
    assert builder.supports_mode("json_schema") is False
    assert builder.supports_mode("unknown") is False
```

#### 2. Empty tools return None

```python
def test_build_empty_tools() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="structural_tag")
    grammar = builder.build([], config)
    assert grammar is None
```

#### 3. Correct artifact type per mode

```python
def test_build_ebnf_returns_ebnf_artifact() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="ebnf")
    grammar = builder.build([_tool("test")], config)
    assert isinstance(grammar, EBNFGrammar)

def test_build_structural_tag_returns_structural_tag_artifact() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="structural_tag")
    grammar = builder.build([_tool("test")], config)
    assert isinstance(grammar, StructuralTagGrammar)
```

#### 4. Tool names appear in grammar

```python
def test_ebnf_contains_tool_names() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="ebnf")
    grammar = builder.build([_tool("get_weather"), _tool("search")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "get_weather" in grammar.grammar
    assert "search" in grammar.grammar
```

#### 5. Parallel calls behavior

```python
def test_ebnf_parallel_calls() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="ebnf", allow_parallel_calls=True)
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "+" in grammar.grammar  # root ::= tool_call+

def test_ebnf_single_call() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="ebnf", allow_parallel_calls=False)
    grammar = builder.build([_tool("tool_a")], config)
    assert isinstance(grammar, EBNFGrammar)
    assert "tool_call+" not in grammar.grammar
```

#### 6. Structural tag uses TriggeredTagsFormat (critical)

This test verifies the fix for the OrFormat crash (see [Pitfall 1](#pitfall-1-using-orformat-or-tagformat-as-top-level-format)):

```python
import json

def test_structural_tag_uses_triggered_tags_format() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="structural_tag", allow_parallel_calls=True)
    tools = [_tool("tool_a"), _tool("tool_b")]
    grammar = builder.build(tools, config)

    assert isinstance(grammar, StructuralTagGrammar)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    fmt = tag_json["format"]

    assert fmt["type"] == "triggered_tags"
    assert "triggers" in fmt
    assert len(fmt["tags"]) == 2
```

#### 7. stop_after_first reflects allow_parallel_calls

```python
def test_structural_tag_parallel_does_not_stop() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="structural_tag", allow_parallel_calls=True)
    grammar = builder.build([_tool("a"), _tool("b")], config)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    assert tag_json["format"]["stop_after_first"] is False

def test_structural_tag_sequential_stops_after_first() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="structural_tag", allow_parallel_calls=False)
    grammar = builder.build([_tool("a"), _tool("b")], config)
    payload = grammar.to_vllm_payload()
    tag_json = json.loads(payload["structured_outputs"]["structural_tag"])
    assert tag_json["format"]["stop_after_first"] is True
```

#### 8. Payload structure validation

```python
def test_ebnf_payload_structure() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="ebnf")
    grammar = builder.build([_tool("test")], config)
    payload = grammar.to_vllm_payload()
    assert "structured_outputs" in payload
    assert "grammar" in payload["structured_outputs"]
    assert isinstance(payload["structured_outputs"]["grammar"], str)
```

### EBNF Validation

Use `validate_ebnf` from `src/structured_agents/grammar/utils.py:16-31` to check grammar syntax against xgrammar's parser:

```python
from structured_agents.grammar.utils import validate_ebnf

def test_ebnf_grammar_is_valid() -> None:
    builder = MyGrammarBuilder()
    config = GrammarConfig(mode="ebnf")
    grammar = builder.build([_tool("test")], config)
    errors = validate_ebnf(grammar.grammar)
    assert errors == [], f"EBNF validation errors: {errors}"
```

Note: `validate_ebnf` depends on `xgrammar.testing._get_matcher_from_grammar` being available at test time.

### Running Tests

```bash
pytest tests/test_grammar/ -v
```
