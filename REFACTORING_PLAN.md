# Refactoring Plan: Modular Grammar + Grail Registry Architecture

## Goals
- Make structured-agents **EBNF-first** with a clean, optional **structural-tag** path.
- Introduce a **grammar builder layer** that is modular, composable, and model-aware.
- Align with vLLM structured outputs, while supporting other model backends cleanly.
- Treat Grail as a **first-class tool provider** via a dedicated registry (Option C).
- Provide the cleanest, most elegant architecture with **no backward-compat constraints**.

---

## Future State Architecture Overview

### Core Ideas
1. **Grammar Builder Layer**
   - Centralized and composable grammar construction.
   - Produces artifacts in one of three forms:
     - EBNF string (default)
     - StructuralTag object
     - XGrammar Grammar object

2. **Model Plugin Layer**
   - Owns formatting, parsing, and model-specific output constraints.
   - Declares capabilities (EBNF, structural tags, JSON schema).
   - Converts grammar artifacts into vLLM request payloads.

3. **Kernel Layer (Agent loop)**
   - Orchestrates messages, tools, and tool execution.
   - Delegates grammar construction and payload formatting to the plugin.

4. **Tool Registry Layer (Composable)**
   - Unified interface to resolve tools and schemas.
   - Grail lives here as a plugin (Option C).
   - Future registries can wrap non-Grail tool systems.

5. **Bundle Layer**
   - Pure configuration and composition: prompts + tools + grammar strategy.
   - Delegates tool schema resolution to registries.

---

## Module Layout (Target)

```
structured_agents/
  grammar/
    __init__.py
    artifacts.py          # GrammarArtifact definitions
    specs.py              # GrammarSpec protocol + strategies
    builders/
      __init__.py
      function_gemma.py   # FunctionGemma grammar builder
      qwen.py             # JSON-first builder (optional)
      json_schema.py      # JSON-schema -> grammar utilities
      structural_tags.py  # StructuralTag builders + helpers
    utils.py              # escaping, validation helpers

  plugins/
    protocol.py           # ModelPlugin capabilities
    function_gemma.py     # uses grammar artifacts
    qwen.py               # uses grammar artifacts
    registry.py           # plugin registry

  registries/
    protocol.py           # ToolRegistry interface
    grail.py              # Grail registry (inputs.json + grail check)
    inline.py             # inline schema registry (optional)

  bundles/
    schema.py             # grammar strategy configuration
    loader.py             # bundle loader (tool refs + registry binding)

  kernel.py               # uses plugin grammar builder
```

---

## Interfaces (Exact Sketches)

### Grammar Artifacts
```python
# structured_agents/grammar/artifacts.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class GrammarArtifact:
    kind: Literal["ebnf", "structural_tag", "xgrammar"]
    value: str | object
```

### Grammar Strategy
```python
# structured_agents/grammar/specs.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class GrammarStrategy:
    mode: Literal["ebnf", "structural_tag", "xgrammar"] = "ebnf"
    allow_multiple_calls: bool = False
    args_mode: Literal["permissive", "function_gemma", "json_schema"] = "permissive"
```

### Grammar Builder Protocol
```python
# structured_agents/grammar/specs.py
from typing import Protocol

class GrammarSpec(Protocol):
    def build(self, tools: list[ToolSchema]) -> GrammarArtifact:
        ...
```

### Tool Registry Protocol (Option C)
```python
# structured_agents/registries/protocol.py
from typing import Protocol

class ToolRegistry(Protocol):
    def resolve_tools(self, bundle: BundleManifest) -> list[ToolSchema]:
        ...
```

### Grail Tool Registry
```python
# structured_agents/registries/grail.py
class GrailToolRegistry:
    def resolve_tools(self, bundle: BundleManifest) -> list[ToolSchema]:
        # 1) read `.grail/.../inputs.json` if present
        # 2) optional dev mode: run `grail check` and re-read
        # 3) build ToolSchema objects
        ...
```

### Model Plugin Capabilities
```python
# structured_agents/plugins/protocol.py
class ModelPlugin(Protocol):
    name: str
    supports_ebnf: bool
    supports_structural_tags: bool

    def format_messages(...): ...
    def format_tools(...): ...
    def build_grammar(self, tools: list[ToolSchema], strategy: GrammarStrategy) -> GrammarArtifact | None: ...
    def extra_body(self, artifact: GrammarArtifact | None) -> dict[str, Any] | None: ...
    def parse_response(...): ...
```

### Kernel Integration
```python
# structured_agents/kernel.py
artifact = self.plugin.build_grammar(tools, strategy)
extra_body = self.plugin.extra_body(artifact)
```

### Plugin Registry
```python
# structured_agents/plugins/registry.py
class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, type[ModelPlugin]] = {}

    def register(self, name: str, plugin_cls: type[ModelPlugin]) -> None:
        self._plugins[name] = plugin_cls

    def resolve(self, name: str) -> ModelPlugin:
        return self._plugins[name]()
```

---

## Tool Registry Architecture (Option C)

### Rationale
- Keeps bundle loader lean and declarative.
- Makes Grail schema extraction reusable across systems.
- Enables future tool registries for other backends without touching core.

### Example Bundle Flow
1. Bundle loader parses YAML and identifies tool references.
2. Bundle loader asks registry to resolve tool schemas.
3. Registry returns `ToolSchema` objects.
4. Kernel uses the schemas, plugin builds grammar constraints.

---

## Grammar Builder Design (EBNF-first, Structural Tag opt-in)

### FunctionGemma Builder
```python
# structured_agents/grammar/builders/function_gemma.py
class FunctionGemmaGrammarBuilder:
    def __init__(self, strategy: GrammarStrategy) -> None:
        self._strategy = strategy

    def build(self, tools: list[ToolSchema]) -> GrammarArtifact:
        if self._strategy.mode == "structural_tag":
            tag = build_functiongemma_structural_tag(tools, self._strategy)
            return GrammarArtifact(kind="structural_tag", value=tag)

        ebnf = build_functiongemma_ebnf(tools, self._strategy)
        return GrammarArtifact(kind="ebnf", value=ebnf)
```

### Structural Tag Builder (Opt-In)
```python
# structured_agents/grammar/builders/structural_tags.py
from xgrammar.structural_tag import StructuralTag, TagFormat, OrFormat, GrammarFormat

def build_functiongemma_structural_tag(tools: list[ToolSchema], strategy: GrammarStrategy) -> StructuralTag:
    tags = []
    for tool in tools:
        args_grammar = build_args_grammar(tool, strategy)
        tags.append(
            TagFormat(
                begin=f"<start_function_call>call:{tool.name}{{",
                content=GrammarFormat(grammar=args_grammar),
                end="}<end_function_call>",
            )
        )

    return StructuralTag(format=OrFormat(elements=tags) if len(tags) > 1 else tags[0])
```

### EBNF Builder (Default)
```python
# structured_agents/grammar/builders/function_gemma.py

def build_functiongemma_ebnf(tools: list[ToolSchema], strategy: GrammarStrategy) -> str:
    tool_names = [escape_ebnf(tool.name) for tool in tools]
    tool_alts = " | ".join(f'"{name}"' for name in tool_names)

    args = build_args_grammar(tool=None, strategy=strategy)
    call_rule = "function_call+" if strategy.allow_multiple_calls else "function_call"

    return "\n".join([
        f"root ::= {call_rule}",
        "",
        "function_call ::= \"<start_function_call>\" \"call:\" tool_name \"{\" arg_body \"}\" \"<end_function_call>\"",
        "",
        f"tool_name ::= {tool_alts}",
        "",
        f"arg_body ::= {args}",
    ])
```

---

## vLLM Integration (Future State)

### EBNF Flow
- Grammar builder returns EBNF string.
- Plugin emits:
```json
{"structured_outputs": {"type": "grammar", "grammar": "..."}}
```

### Structural Tag Flow
- Grammar builder returns StructuralTag.
- Plugin checks capability:
  - If vLLM supports `structural_tag`, send directly.
  - Otherwise convert via `xgr.Grammar.from_structural_tag()` and send EBNF.

```python
# structured_agents/plugins/function_gemma.py
if artifact.kind == "structural_tag":
    if self.supports_structural_tags:
        return {"structured_outputs": {"type": "structural_tag", "structural_tag": artifact.value}}
    grammar = xgr.Grammar.from_structural_tag(artifact.value)
    return {"structured_outputs": {"type": "grammar", "grammar": str(grammar)}}

if artifact.kind == "ebnf":
    return {"structured_outputs": {"type": "grammar", "grammar": artifact.value}}
```

---

## Bundle Configuration (Target)

```yaml
model:
  plugin: function_gemma
  grammar:
    mode: ebnf                     # ebnf | structural_tag | xgrammar
    allow_multiple_calls: false
    args_mode: function_gemma      # permissive | function_gemma | json_schema

registries:
  - type: grail
    root: agents
    dev_mode: false
```

---

## Grail Agent Integration (Registry Model)

### How Grail Fits
- Grail lives in `registries/grail.py` and implements `ToolRegistry`.
- Each `.pym` tool defines inputs; the registry uses `.grail/.../inputs.json` as source of truth.
- Context providers remain `.pym` scripts referenced by the bundle.

### Benefits
- Tools are fully decoupled from bundle parsing.
- Grail tools are composable across bundles.
- Registry can evolve independently (e.g., caching, schema validation, linting).

---

## Minimal FunctionGemma Demo (SHELLper-Inspired)

### Intent
- Provide a **small, deterministic demo** that mirrors the distil‑SHELLper workflow without excessive defaults.
- Use **Grail `.pym` tools** and the same tool naming/argument patterns from the Gorilla filesystem task.
- Keep the tool set tiny so FunctionGemma’s tool selection is easy to evaluate.

### Minimal Tool Set
Use only the core four commands that show navigation and inspection:
- `pwd(folder: str | None)` → returns current directory (no args in practice)
- `ls(a: bool = False)` → list files
- `cd(folder: str)` → change directory
- `cat(file_name: str)` → read file contents

These map directly to the Gorilla tool definitions from the distil-SHELLper example (`.context/functiongemma_examples/distil-SHELLper-main/functions.md:1`).

### Example Bundle Layout
```
agents/
  shellper_min/
    shellper_min.yaml
    tools/
      pwd.pym
      ls.pym
      cd.pym
      cat.pym
      submit.pym
```

### Example `shellper_min.yaml`
```yaml
name: shellper_min
max_turns: 5

initial_context:
  system_prompt: |
    You are a model that can do function calling with the following functions.
    <task_description>You are a filesystem assistant. Use the tools to inspect
    and navigate the workspace. Respond with a single tool call each turn.</task_description>
  node_context: |
    Task: {{ input }}

tools:
  - tool_name: pwd
    pym: shellper_min/tools/pwd.pym
    tool_description: Return the current working directory.

  - tool_name: ls
    pym: shellper_min/tools/ls.pym
    tool_description: List files in the current directory.

  - tool_name: cd
    pym: shellper_min/tools/cd.pym
    tool_description: Change directory to a given folder.
    inputs_override:
      folder:
        description: "Relative path of the target folder."

  - tool_name: cat
    pym: shellper_min/tools/cat.pym
    tool_description: Read a file and return its contents.
    inputs_override:
      file_name:
        description: "File path to read."

  - tool_name: submit_result
    pym: shellper_min/tools/submit.pym
    tool_description: Submit the final result.
```

### Example `.pym` Tool Behavior (Simplified)
- Keep tools tiny: no context providers, no extra defaults, no command execution.
- Each tool reads from the workspace and returns a small Two‑Track payload.
- `submit.pym` reports summary + changed_files only.

This mirrors the distil‑SHELLper concept (single tool call per turn, minimal tool set) while staying inside the Grail execution model.

### Example `.pym` Skeletons

```python
# agents/shellper_min/tools/pwd.pym
from grail import external

@external
async def run_command(command: str) -> dict[str, str | int]:
    ...

try:
    result = await run_command(command="pwd")
    output = result.get("stdout", "").strip()
    payload = {"cwd": output}
    response = {
        "result": payload,
        "summary": f"Current directory: {output}",
        "knowledge_delta": {"cwd": output},
        "outcome": "success",
    }
except Exception as exc:
    response = {
        "result": None,
        "summary": f"Error: {exc}",
        "knowledge_delta": {},
        "outcome": "error",
        "error": str(exc),
    }

response
```

```python
# agents/shellper_min/tools/ls.pym
from grail import Input, external

show_all: bool = Input("a", default=False)

@external
async def run_command(command: str) -> dict[str, str | int]:
    ...

try:
    flag = "-a" if show_all else ""
    result = await run_command(command=f"ls {flag}".strip())
    output = result.get("stdout", "").strip()
    response = {
        "result": {"listing": output},
        "summary": "Listed directory contents",
        "knowledge_delta": {},
        "outcome": "success",
    }
except Exception as exc:
    response = {
        "result": None,
        "summary": f"Error: {exc}",
        "knowledge_delta": {},
        "outcome": "error",
        "error": str(exc),
    }

response
```

```python
# agents/shellper_min/tools/cd.pym
from grail import Input, external

folder: str = Input("folder")

@external
async def run_command(command: str) -> dict[str, str | int]:
    ...

try:
    _ = await run_command(command=f"cd {folder}")
    response = {
        "result": {"folder": folder},
        "summary": f"Changed directory to {folder}",
        "knowledge_delta": {"cwd": folder},
        "outcome": "success",
    }
except Exception as exc:
    response = {
        "result": None,
        "summary": f"Error: {exc}",
        "knowledge_delta": {},
        "outcome": "error",
        "error": str(exc),
    }

response
```

```python
# agents/shellper_min/tools/cat.pym
from grail import Input, external

file_name: str = Input("file_name")

@external
async def read_file(path: str) -> str:
    ...

try:
    contents = await read_file(path=file_name)
    preview = contents[:500]
    response = {
        "result": {"preview": preview},
        "summary": f"Read {file_name}",
        "knowledge_delta": {},
        "outcome": "success",
    }
except Exception as exc:
    response = {
        "result": None,
        "summary": f"Error: {exc}",
        "knowledge_delta": {},
        "outcome": "error",
        "error": str(exc),
    }

response
```

```python
# agents/shellper_min/tools/submit.pym
from grail import Input

summary: str = Input("summary")
changed_files: list[str] = Input("changed_files")

result = {
    "status": "success",
    "changed_files": [str(path) for path in changed_files],
    "summary": str(summary),
}

result
```

---

## Architecture Diagram

```
Bundle (bundle.yaml)
  ├─ grammar strategy
  ├─ tool references
  └─ registry bindings
          │
          ▼
ToolRegistry (Grail)
  └─ ToolSchema list
          │
          ▼
AgentKernel ───────► ModelPlugin
  │                  ├─ format_messages/tools
  │                  ├─ build_grammar(strategy)
  │                  └─ extra_body(artifact)
  │
  ├─ sends OpenAI-compatible request
  │      └─ extra_body: structured_outputs
  │
  ├─ receives tool calls
  │
  └─ ToolBackend
         ├─ GrailBackend (.pym)
         └─ PythonBackend
```

---

## Decision Matrix

### Structural Tag Delivery to vLLM
- **Direct structural tag payload**
  - **Pros**: preserves structural tag semantics; future-ready.
  - **Cons**: depends on vLLM/XGrammar support.
  - **Recommendation**: Allow when supported; otherwise convert to EBNF.
- **Always convert to EBNF**
  - **Pros**: reliable across backends.
  - **Cons**: loses some structural tag nuance.
  - **Recommendation**: Use as fallback, not default.

### `args_mode: json_schema` Handling
- **Strict JSON strings**
  - **Pros**: aligns with JSON schema expectations.
  - **Cons**: conflicts with FunctionGemma `<escape>` format.
  - **Recommendation**: Use for JSON-native models (Qwen-like).
- **FunctionGemma `<escape>` grammar**
  - **Pros**: matches FunctionGemma tool call syntax.
  - **Cons**: requires custom grammar conversion from JSON schema.
  - **Recommendation**: Default for FunctionGemma.

### Per-Tool Schema Enforcement
- **Default on**
  - **Pros**: strongest safety guarantees.
  - **Cons**: may reduce tool-call rate on small models.
  - **Recommendation**: Enable only for robust models.
- **Opt-in**
  - **Pros**: safer for FunctionGemma-270M.
  - **Cons**: less strict by default.
  - **Recommendation**: Default opt-in, with tool-level flags.

---

## Phased Rollout Plan

### Phase 1: Core Infrastructure
- Implement `grammar/` package and `GrammarArtifact`/`GrammarStrategy`.
- Add plugin registry and resolve plugins via registry.
- Add tool registry interface and Grail registry implementation.
- Update kernel to use grammar artifacts and plugin `extra_body()`.

### Phase 2: FunctionGemma Parity
- Migrate FunctionGemma plugin to new grammar builder layer.
- Implement strict EBNF builder with escaped tool names.
- Update FunctionGemma parsing for multi-call + `<escape>` compatibility.

### Phase 3: Structural Tag Opt-In
- Add structural tag builders and optional conversion to EBNF.
- Add bundle config flags for `mode: structural_tag` and capability checks.
- Add focused tests for structural tag conversion.

### Phase 4: Grail-First Tool Schemas
- Add Grail registry support for `.grail/.../inputs.json` ingestion.
- Simplify bundle manifests to reference `.pym` tools only.
- Add validation for missing `.grail` artifacts and dev-mode generation.

### Phase 5: Argument Schema Enforcement
- Implement `args_mode: json_schema` for JSON-native models.
- Implement FunctionGemma-compatible schema grammar option.
- Add opt-in per-tool schema enforcement flags.

---

## Recommendation Summary
- **Adopt the grammar builder layer** with artifacts and strategies.
- **Use ToolRegistry (Option C)** to make Grail a composable tool provider.
- **Default to strict EBNF** with structural tags opt-in.
- **Convert structural tags to EBNF** when the backend doesn’t support them.
- **Make Grail `.pym` + inputs.json the schema source of truth**.

This architecture emphasizes modularity, composability, and clean separation of concerns while remaining EBNF-first and ready for structural-tag-powered tool calling when desired.
