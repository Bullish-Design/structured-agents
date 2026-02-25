Comprehensive Overview of structured-agents Library
1. What the Library Is and Its Purpose
structured-agents is a minimal, reusable agent kernel for tool-calling workflows. It provides:
- A focused agent loop that integrates model calls, tool execution, and observable events
- Grammar-constrained decoding via XGrammar for structured outputs
- A toolkit for bundling tools, prompts, and model configuration
- A clean integration layer for Grail .pym tools and Python tool backends
The library is designed to be a building block for larger systems, NOT a full multi-agent orchestrator or workspace manager.
---
2. Key Components and Architecture
Core Components (by layer):
Kernel Layer (kernel.py)
- AgentKernel: The central orchestrator that handles the agent loop
  - Makes model calls with appropriate formatting
  - Parses responses and extracts tool calls
  - Executes tools via the backend
  - Manages conversation history
  - Emits events to observers
Plugin Layer (plugins/)
- ModelPlugin (protocol): Defines how to format messages, tools, parse responses, and build grammar for different models
- Model-specific plugins:
  - FunctionGemmaPlugin: For Google's FunctionGemma models
  - QwenPlugin: For Qwen models
  - ComposedModelPlugin: Composes message formatter, tool formatter, response parser, and grammar provider
Tool Execution Layer (backends/ + tool_sources/)
- ToolBackend (protocol): Handles actual tool execution
  - PythonBackend: Executes Python functions directly (for testing/simple use cases)
  - GrailBackend: Executes Grail .pym scripts (the main production backend)
  - CompositeBackend: Combines multiple backends
- ToolSource (protocol): Unified tool discovery + execution
  - RegistryBackendToolSource: Combines a registry with a backend
Registry Layer (registries/)
- ToolRegistry (protocol): Resolves tool schemas from a source
  - PythonRegistry: For Python functions
  - GrailRegistry: For Grail tools
  - CompositeRegistry: Combines multiple registries
Grammar Layer (grammar/)
- GrammarConfig: Configuration for grammar generation (mode: EBNF, structural_tag, or json_schema)
- GrammarArtifact: EBNFGrammar, StructuralTagGrammar, or JsonSchemaGrammar
- Grammar builders: Convert tool schemas to grammar constraints
Bundle System (bundles/)
- AgentBundle: Packages prompts, tools, and model configuration into a directory with bundle.yaml
- load_bundle(): Loads a bundle from a directory
Observer System (observer/)
- Observer (protocol): Receives kernel execution events for logging, TUIs, telemetry
---
3. Main Entry Points and Core Classes
Main Classes
| Class | Purpose |
|-------|---------|
| AgentKernel | Core agent loop orchestrator |
| KernelConfig | Configuration (base_url, model, tool_execution_strategy, etc.) |
| Message | Conversation message (role, content, tool_calls, tool_call_id) |
| ToolCall | Parsed tool call from model output |
| ToolResult | Result of executing a tool |
| ToolSchema | Schema for a tool (in OpenAI function format) |
| ToolExecutionStrategy | Controls sequential vs concurrent tool calls |
| FunctionGemmaPlugin / QwenPlugin | Model-specific plugins |
Key Functions
| Function | Purpose |
|----------|---------|
| load_bundle(path) | Load an agent bundle from a directory |
| build_client(config) | Build an OpenAI-compatible client from config |
---
4. How It Works (Core Functionality and Flow)
The Agent Loop (AgentKernel.run())
┌─────────────────────────────────────────────────────────────┐
│                     AgentKernel.run()                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Initialize: Resolve tools, emit kernel_start event      │
│                                                             │
│ 2. Loop (until max_turns or termination):                 │
│    ┌─────────────────────────────────────────────────────┐ │
│    │ a. Build context (context_provider + tool sources)  │ │
│    │ b. Trim history (SlidingWindowHistory strategy)     │ │
│    │ c. step():                                          │ │
│    │    i. Format messages + tools (via plugin)          │ │
│    │    ii. Build grammar (via plugin + XGrammar)         │ │
│    │    iii. Call LLM (with grammar constraints)          │ │
│    │    iv. Parse response (extract tool calls)           │ │
│    │    v. Execute tools (sequential or concurrent)       │ │
│    │    vi. Emit events (model_request, tool_call, etc) │ │
│    │ d. Add response + results to history                 │ │
│    │ e. Check termination condition                       │ │
│    └─────────────────────────────────────────────────────┘ │
│                                                             │
│ 3. Return: RunResult (final_message, history, usage, etc)  │
└─────────────────────────────────────────────────────────────┘
Single Step (AgentKernel.step())
1. Resolve tools from names or use provided ToolSchemas
2. Format messages using the plugin's message formatter
3. Format tools using the plugin's tool formatter
4. Build grammar using XGrammar (EBNF, structural tags, or JSON schema)
5. Make LLM call with grammar constraints via vLLM extra_body
6. Parse response to extract text content and tool calls
7. Execute tools (concurrently or sequentially based on strategy)
8. Emit observer events for observability
Grammar-Constrained Decoding
The library uses XGrammar for structured output:
ToolSchemas → Grammar Builder → GrammarArtifact → vLLM extra_body
                              ↓
                   EBNFGrammar / StructuralTagGrammar / JsonSchemaGrammar
This ensures the model produces valid tool calls that conform to the tool schemas.
---
5. Key Dependencies
From pyproject.toml:
| Dependency | Purpose |
|------------|---------|
| vllm (>=0.15.1) | LLM inference server (OpenAI-compatible API) |
| xgrammar (>=0.1.7) | Grammar-constrained decoding |
| grail | Tool execution framework (for GrailBackend) |
| pydantic (>=2.0) | Data validation |
| httpx (>=0.25) | HTTP client |
| openai (>=1.0) | OpenAI API client |
| pyyaml (>=6.0) | YAML parsing for bundles |
| jinja2 (>=3.0) | Template rendering for bundles |
| fsdantic | Custom pydantic extensions |
Required at Runtime
- OpenAI-compatible API server (vLLM) running locally or remotely
- XGrammar runtime for grammar constraints
---
Example Usage Flow
from structured_agents import (
    AgentKernel, FunctionGemmaPlugin, KernelConfig,
    Message, ToolSchema
)
from structured_agents.backends import PythonBackend
from structured_agents.registries import PythonRegistry
from structured_agents.tool_sources import RegistryBackendToolSource
# 1. Configure kernel
config = KernelConfig(
    base_url="http://localhost:8000/v1",
    model="google/functiongemma-270m-it",
)
# 2. Setup tools
registry = PythonRegistry()
backend = PythonBackend(registry=registry)
backend.register("greet", lambda name: f"Hello, {name}!")
tool_source = RegistryBackendToolSource(registry, backend)
# 3. Create kernel
kernel = AgentKernel(
    config=config,
    plugin=FunctionGemmaPlugin(),
    tool_source=tool_source,
)
# 4. Run agent
result = await kernel.run(
    initial_messages=[Message(role="user", content="Greet Alice")],
    tools=[ToolSchema(name="greet", description="Greet someone", parameters={...})],
    max_turns=3,
)
print(result.final_message.content)
await kernel.close()
---
Summary
structured-agents is a lightweight, focused agent kernel that:
- Provides a clean separation of concerns (plugin, backend, registry, tool source)
- Uses grammar-constrained decoding for reliable tool calling
- Supports concurrent tool execution with configurable strategies
- Includes bundle system for packaging agents
- Has observable events for integration with logging/telemetry
- Requires vLLM + XGrammar for the grammar-constrained LLM calls
It is NOT a multi-agent orchestrator, workspace manager, or code discovery engine - those responsibilities belong to consumer applications.