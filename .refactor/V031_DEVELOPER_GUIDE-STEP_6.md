You are writing a developer guide document for a junior developer. Write the file:
/home/andrew/Documents/Projects/structured-agents/V031_DEVELOPER_GUIDE-STEP_6.md
This is Step 6 of 7: "Agent & Grammar — Fix from_bundle, load_manifest, wire grammar, add adapter registry"
IMPORTANT: Write the file in small chunks. Write the first section to the file, then append subsequent sections. Do NOT try to write the entire file in one call.
## Context
The Agent is the user-facing API. This step fixes the bundle loading, manifest parsing, grammar wiring, and adds a model adapter registry so different model families can be supported without modifying source code.
## Current state of files:
### agent.py:
```python
"""Agent - high-level entry point for structured-agents."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
import yaml
from structured_agents.client.protocol import LLMClient
from structured_agents.client.factory import build_client  # WRONG: factory.py deleted in Step 2
from structured_agents.events.observer import NullObserver, Observer
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.kernel import AgentKernel
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import QwenResponseParser
from structured_agents.tools.grail import discover_tools
from structured_agents.types import Message, RunResult, ToolSchema
@dataclass
class AgentManifest:
    name: str
    system_prompt: str
    agents_dir: Path
    limits: Any = None
    model: str = "qwen"
    grammar_config: DecodingConstraint | None = None
    max_turns: int = 20
def load_manifest(bundle_path: str | Path) -> AgentManifest:
    path = Path(bundle_path)
    if path.is_dir():
        path = path / "bundle.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)
    return AgentManifest(
        name=data.get("name", "unnamed"),
        system_prompt=data.get("system_prompt", ""),  # BUG: should be initial_context.system_prompt
        agents_dir=Path(bundle_path).parent / data.get("agents_dir", "agents"),  # BUG: wrong path resolution
        limits=data.get("limits"),
        model=data.get("model", "qwen"),
        grammar_config=None,  # Never reads from YAML
        max_turns=data.get("max_turns", 20),
    )
class Agent:
    def __init__(self, kernel: AgentKernel, manifest: AgentManifest, observer: Observer | None = None):
        self.kernel = kernel
        self.manifest = manifest
        self.observer = observer or NullObserver()
    @classmethod
    async def from_bundle(cls, path: str | Path, **overrides) -> "Agent":
        manifest = load_manifest(path)
        tools = discover_tools(str(manifest.agents_dir))
        adapter = ModelAdapter(
            name=manifest.model,
            grammar_builder=lambda t, c: None,  # NO-OP! Grammar is inert.
            response_parser=QwenResponseParser(),
        )
        client = build_client({
            "model": manifest.model,
            "base_url": "http://localhost:8000/v1",  # HARDCODED!
            "api_key": "EMPTY",
        })
        kernel = AgentKernel(client=client, adapter=adapter, tools=tools)
        return cls(kernel, manifest)  # Observer not passed!
    async def run(self, user_input: str, **kwargs) -> RunResult:
        messages = [
            Message(role="system", content=self.manifest.system_prompt),
            Message(role="user", content=user_input),
        ]
        tool_schemas = [t.schema for t in self.kernel.tools]
        return await self.kernel.run(messages, tool_schemas, max_turns=kwargs.get("max_turns", self.manifest.max_turns))
    async def close(self) -> None:
        await self.kernel.close()
```
### grammar/config.py:
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
@dataclass(frozen=True, slots=True)
class DecodingConstraint:
    strategy: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = False
    send_tools_to_api: bool = False
@dataclass(frozen=True, slots=True)
class GrammarConfig:
    mode: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = True
    args_format: Literal["permissive", "escaped_strings", "json"] = "permissive"
    send_tools_to_api: bool = True
```
### grammar/pipeline.py:
```python
from __future__ import annotations
from typing import Any, Callable
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.types import ToolSchema
class ConstraintPipeline:
    def __init__(self, builder: Callable[[list[ToolSchema], DecodingConstraint], dict[str, Any] | None], config: DecodingConstraint):
        self._builder = builder
        self._config = config
    def constrain(self, tools: list[ToolSchema]) -> dict[str, Any] | None:
        if not tools:
            return None
        return self._builder(tools, self._config)
```
### grammar/__init__.py:
```python
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.grammar.pipeline import ConstraintPipeline
__all__ = ["ConstraintPipeline", "DecodingConstraint"]
```
### The actual bundle.yaml format (from tests/fixtures/sample_bundle/bundle.yaml):
```yaml
name: "sample_bundle"
version: "1.0"
model:
  plugin: "function_gemma"
initial_context:
  system_prompt: "You are a test agent."
  user_template: "Handle: {{ input }}"
max_turns: 3
termination_tool: "submit_result"
tools:
  - name: "echo"
    registry: "grail"
  - name: "submit_result"
    registry: "grail"
registries:
  - type: "grail"
```
## What the guide should instruct the developer to do:
### 1. Remove ConstraintPipeline entirely:
The code review correctly identified it as "adding indirection without value." It wraps a callable in a class with a 3-line method. Replace it with the bare callable pattern. The grammar_builder on ModelAdapter IS the pipeline — it takes `(tools, config)` and returns `dict | None`.
Delete `grammar/pipeline.py`. Update `grammar/__init__.py` to only export `DecodingConstraint`.
### 2. Remove GrammarConfig — keep only DecodingConstraint:
`GrammarConfig` duplicates `DecodingConstraint` with contradictory defaults. Remove it. `DecodingConstraint` is the single source of truth for grammar configuration.
### 3. Fix load_manifest:
Multiple bugs:
- `system_prompt` reads from `data.get("system_prompt")` but the YAML has it under `initial_context.system_prompt`
- `model` reads `data.get("model", "qwen")` but the YAML has `model.plugin: "function_gemma"` — it's a dict, not a string
- `agents_dir` path resolution: `Path(bundle_path).parent` is wrong when bundle_path is a directory — should use the manifest file's parent
- `grammar_config` is hardcoded to `None` — should read from YAML
- `base_url` is hardcoded to localhost — should come from manifest or env
Fix:
```python
def load_manifest(bundle_path: str | Path) -> AgentManifest:
    path = Path(bundle_path)
    if path.is_dir():
        path = path / "bundle.yaml"
    
    with open(path) as f:
        data = yaml.safe_load(f)
    
    # Resolve agents_dir relative to the manifest file's directory
    bundle_dir = path.parent
    
    # Read system_prompt from nested initial_context
    initial_context = data.get("initial_context", {})
    
    # Read model — could be a string or a dict with "plugin" key
    model_config = data.get("model", "qwen")
    if isinstance(model_config, dict):
        model_name = model_config.get("plugin", "qwen")
    else:
        model_name = model_config
    
    # Read grammar config if present
    grammar_data = data.get("grammar", {})
    grammar_config = None
    if grammar_data:
        grammar_config = DecodingConstraint(
            strategy=grammar_data.get("strategy", "ebnf"),
            allow_parallel_calls=grammar_data.get("allow_parallel_calls", False),
            send_tools_to_api=grammar_data.get("send_tools_to_api", False),
        )
    
    return AgentManifest(
        name=data.get("name", "unnamed"),
        system_prompt=initial_context.get("system_prompt", ""),
        agents_dir=bundle_dir / data.get("agents_dir", "agents"),
        limits=data.get("limits"),
        model=model_name,
        grammar_config=grammar_config,
        max_turns=data.get("max_turns", 20),
    )
```
### 4. Add adapter registry:
Instead of hardcoding `QwenResponseParser()`, create a registry mapping model names to their adapter configuration:
```python
import os
# Adapter registry — maps model family names to their parser/config
_ADAPTER_REGISTRY: dict[str, type] = {
    "qwen": QwenResponseParser,
    "function_gemma": QwenResponseParser,  # Uses same parser for now
}
def get_response_parser(model_name: str) -> ResponseParser:
    """Look up the response parser for a model family."""
    parser_cls = _ADAPTER_REGISTRY.get(model_name)
    if parser_cls is None:
        # Default to Qwen parser — most OpenAI-compatible models work with it
        parser_cls = QwenResponseParser
    return parser_cls()
```
### 5. Fix from_bundle:
- Use adapter registry instead of hardcoded QwenResponseParser
- Read base_url from environment variable or manifest, not hardcoded
- Pass observer to kernel
- Apply overrides
- Wire grammar_config into the adapter
```python
@classmethod
async def from_bundle(cls, path: str | Path, observer: Observer | None = None, **overrides) -> "Agent":
    manifest = load_manifest(path)
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(manifest, key):
            object.__setattr__(manifest, key, value)
    
    tools = discover_tools(str(manifest.agents_dir))
    
    parser = get_response_parser(manifest.model)
    
    adapter = ModelAdapter(
        name=manifest.model,
        response_parser=parser,
        grammar_builder=None,  # TODO: wire actual grammar builder when xgrammar is integrated
        grammar_config=manifest.grammar_config,
    )
    
    base_url = os.environ.get("STRUCTURED_AGENTS_BASE_URL", "http://localhost:8000/v1")
    api_key = os.environ.get("STRUCTURED_AGENTS_API_KEY", "EMPTY")
    
    client = build_client({
        "model": manifest.model,
        "base_url": base_url,
        "api_key": api_key,
    })
    
    obs = observer or NullObserver()
    kernel = AgentKernel(client=client, adapter=adapter, tools=tools, observer=obs)
    
    return cls(kernel, manifest, observer=obs)
```
### 6. Fix AgentManifest typing:
- `limits: Any` should be `limits: dict[str, Any] | None = None`
- Add import for `grail.Limits` if needed, or keep as dict since we parse it in from_bundle
### 7. Update grammar/__init__.py:
Remove ConstraintPipeline export, only export DecodingConstraint.
## IMPORTANT NOTES:
- Show COMPLETE final versions of agent.py, grammar/config.py, grammar/__init__.py
- Delete grammar/pipeline.py (instruct to delete the file)
- The import in agent.py needs to change from `client.factory` to `client` (fix from Step 2)
- Explain the adapter registry pattern and why it's better than hardcoding
- Include "Verification" section
Return a brief (2-3 sentence) confirmation when done.