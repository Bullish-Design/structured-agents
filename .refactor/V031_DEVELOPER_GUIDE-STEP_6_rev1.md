# Developer Guide: Step 6 — Agent & Grammar Fixes

## Overview

This step fixes the bundle loading, manifest parsing, grammar wiring, and adds a model adapter registry so different model families can be supported without modifying source code.

## 1. Remove ConstraintPipeline (Delete File)

The `ConstraintPipeline` class adds indirection without value — it wraps a callable in a class with a 3-line method. The `grammar_builder` on `ModelAdapter` already serves this purpose.

**Action:** Delete `grammar/pipeline.py`

## 2. Remove GrammarConfig

`GrammarConfig` duplicates `DecodingConstraint` with contradictory defaults. Remove it. `DecodingConstraint` is the single source of truth.

**Action:** Update `grammar/config.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DecodingConstraint:
    strategy: Literal["ebnf", "structural_tag", "json_schema"] = "ebnf"
    allow_parallel_calls: bool = False
    send_tools_to_api: bool = False
```

## 3. Update grammar/__init__.py

Remove `ConstraintPipeline` export, only export `DecodingConstraint`.

```python
from structured_agents.grammar.config import DecodingConstraint

__all__ = ["DecodingConstraint"]
```

## 4. Fix AgentManifest Typing

Update `agent.py` to fix the `limits` type:

```python
@dataclass
class AgentManifest:
    name: str
    system_prompt: str
    agents_dir: Path
    limits: dict[str, Any] | None = None
    model: str = "qwen"
    grammar_config: DecodingConstraint | None = None
    max_turns: int = 20
```

## 5. Fix load_manifest

Multiple bugs exist:
- `system_prompt` reads from `data.get("system_prompt")` but YAML has it under `initial_context.system_prompt`
- `model` reads `data.get("model", "qwen")` but YAML has `model.plugin: "function_gemma"` — it's a dict
- `agents_dir` path resolution: `Path(bundle_path).parent` is wrong when bundle_path is a directory
- `grammar_config` is hardcoded to `None`
- `base_url` is hardcoded to localhost

**Action:** Update `load_manifest` in `agent.py`:

```python
def load_manifest(bundle_path: str | Path) -> AgentManifest:
    path = Path(bundle_path)
    if path.is_dir():
        path = path / "bundle.yaml"
    
    with open(path) as f:
        data = yaml.safe_load(f)
    
    bundle_dir = path.parent
    
    initial_context = data.get("initial_context", {})
    
    model_config = data.get("model", "qwen")
    if isinstance(model_config, dict):
        model_name = model_config.getqwen")
   ("plugin", " else:
        model_name = model_config
    
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

## 6. Add Adapter Registry

Instead of hardcoding `QwenResponseParser()`, create a registry mapping model names to their adapter configuration. This allows supporting different model families without modifying source code.

**Action:** Add to `agent.py`:

```python
import os

from structured_agents.models.parsers import QwenResponseParser, ResponseParser

_ADAPTER_REGISTRY: dict[str, type[ResponseParser]] = {
    "qwen": QwenResponseParser,
    "function_gemma": QwenResponseParser,
}


def get_response_parser(model_name: str) -> ResponseParser:
    """Look up the response parser for a model family."""
    parser_cls = _ADAPTER_REGISTRY.get(model_name, QwenResponseParser)
    return parser_cls()
```

## 7. Fix from_bundle

- Use adapter registry instead of hardcoded parser
- Read base_url from environment variable or manifest
- Pass observer to kernel
- Apply overrides
- Wire grammar_config into the adapter

**Action:** Update `from_bundle` in `agent.py`:

```python
@classmethod
async def from_bundle(cls, path: str | Path, observer: Observer | None = None, **overrides) -> "Agent":
    manifest = load_manifest(path)
    
    for key, value in overrides.items():
        if hasattr(manifest, key):
            object.__setattr__(manifest, key, value)
    
    tools = discover_tools(str(manifest.agents_dir))
    
    parser = get_response_parser(manifest.model)
    
    adapter = ModelAdapter(
        name=manifest.model,
        response_parser=parser,
        grammar_builder=None,
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

## 8. Fix Import

The import in `agent.py` changed from `client.factory` to `client` (fixed from Step 2):

```python
from structured_agents.client import build_client
```

## Final agent.py

```python
"""Agent - high-level entry point for structured-agents."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from dataclasses import dataclass
import yaml

from structured_agents.client import build_client
from structured_agents.events.observer import NullObserver, Observer
from structured_agents.grammar.config import DecodingConstraint
from structured_agents.kernel import AgentKernel
from structured_agents.models.adapter import ModelAdapter
from structured_agents.models.parsers import QwenResponseParser, ResponseParser
from structured_agents.tools.grail import discover_tools
from structured_agents.types import Message, RunResult


_ADAPTER_REGISTRY: dict[str, type[ResponseParser]] = {
    "qwen": QwenResponseParser,
    "function_gemma": QwenResponseParser,
}


def get_response_parser(model_name: str) -> ResponseParser:
    """Look up the response parser for a model family."""
    parser_cls = _ADAPTER_REGISTRY.get(model_name, QwenResponseParser)
    return parser_cls()


@dataclass
class AgentManifest:
    name: str
    system_prompt: str
    agents_dir: Path
    limits: dict[str, Any] | None = None
    model: str = "qwen"
    grammar_config: DecodingConstraint | None = None
    max_turns: int = 20


def load_manifest(bundle_path: str | Path) -> AgentManifest:
    path = Path(bundle_path)
    if path.is_dir():
        path = path / "bundle.yaml"
    
    with open(path) as f:
        data = yaml.safe_load(f)
    
    bundle_dir = path.parent
    
    initial_context = data.get("initial_context", {})
    
    model_config = data.get("model", "qwen")
    if isinstance(model_config, dict):
        model_name = model_config.get("plugin", "qwen")
    else:
        model_name = model_config
    
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


class Agent:
    def __init__(self, kernel: AgentKernel, manifest: AgentManifest, observer: Observer | None = None):
        self.kernel = kernel
        self.manifest = manifest
        self.observer = observer or NullObserver()
    
    @classmethod
    async def from_bundle(cls, path: str | Path, observer: Observer | None = None, **overrides) -> "Agent":
        manifest = load_manifest(path)
        
        for key, value in overrides.items():
            if hasattr(manifest, key):
                object.__setattr__(manifest, key, value)
        
        tools = discover_tools(str(manifest.agents_dir))
        
        parser = get_response_parser(manifest.model)
        
        adapter = ModelAdapter(
            name=manifest.model,
            response_parser=parser,
            grammar_builder=None,
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

## Adapter Registry Pattern

The adapter registry pattern provides:

- **Extensibility**: Add new model families by updating the registry dict, not source code
- **Separation of concerns**: Each model family maps to its specific parser
- **Default fallback**: Unknown models default to QwenResponseParser (most OpenAI-compatible)
- **Runtime configuration**: Can be extended to load adapters from plugins

To add a new model family:
```python
_ADAPTER_REGISTRY["new_model"] = NewModelResponseParser
```

## Verification

Run tests to verify the changes work correctly:

```bash
pytest tests/ -v -k "agent"
```

Check for mypy type errors:

```bash
mypy agent.py --strict
```
