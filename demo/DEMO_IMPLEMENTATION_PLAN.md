# Demo Implementation Plan

## Overview

This plan provides a step-by-step guide for implementing the multi-agent demo. We start with the smallest verifiable pieces and progressively build up to the full orchestrated demo.

**Key Principle:** Each step builds on verified previous steps. We validate simple components first, then combine them into more complex systems.

**Prerequisites:**
- vLLM server running at `remora-server:8000`
- Model: `Qwen/Qwen3-4B-Instruct-2507-FP8`
- Grail tools available in `agents/` directory
- Python environment with `structured-agents` installed

---

## Phase 1: Infrastructure & Simple Components

### Step 1: Verify vLLM Connectivity

**Goal:** Confirm the vLLM server is accessible and responding.

**File:** `demo_steps/step01_verify_vllm.py`

```python
"""Step 1: Verify vLLM server connectivity."""
import asyncio
from structured_agents.client.factory import build_client
from structured_agents import KernelConfig

async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
    )
    client = build_client(config)
    
    try:
        models = await client.list_models()
        print("✓ Connected to vLLM server")
        print(f"Available models: {[m.id for m in models.data]}")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Expected Output:**
```
✓ Connected to vLLM server
Available models: ['Qwen/Qwen3-4B-Instruct-2507-FP8']
```

**Validation:** If this fails, check network access and vLLM server status.

---

### Step 2: Basic Chat with QwenPlugin

**Goal:** Make a simple chat call using QwenPlugin without tools.

**File:** `demo_steps/step02_basic_chat.py`

```python
"""Step 2: Basic chat with QwenPlugin."""
import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin
from structured_agents.client.factory import build_client

async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.7,
        max_tokens=256,
    )
    client = build_client(config)
    plugin = QwenPlugin()
    
    messages = [
        Message(role="developer", content="You are a helpful assistant."),
        Message(role="user", content="What is 2 + 2?"),
    ]
    
    formatted = plugin.format_messages(messages, [])
    
    response = await client.chat_completion(
        messages=formatted,
        tools=None,
        tool_choice="none",
    )
    
    print("=== Response ===")
    print(response.content)
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Input:** "What is 2 + 2?"
**Expected Output:** Something like "2 + 2 equals 4."

**Validation:** Response should be coherent and relevant.

---

## Phase 2: Grail Backend (Foundation for Dispatchers)

### Step 3: Single Grail Script Execution

**Goal:** Execute a single Grail `.pym` script via the GrailBackend.

**File:** `demo_steps/step03_single_grail.py`

```python
"""Step 3: Execute a single Grail script."""
import asyncio
from pathlib import Path
from structured_agents import (
    GrailBackend,
    GrailBackendConfig,
    ToolCall,
    ToolSchema,
)

async def main():
    script_path = Path("agents/shellper_demo/echo.pym")
    
    config = GrailBackendConfig(grail_dir=Path.cwd() / "agents")
    backend = GrailBackend(config)
    
    tool_schema = ToolSchema(
        name="echo",
        description="Echo back the input",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"},
            },
            "required": ["text"],
        },
        script_path=script_path,
    )
    
    tool_call = ToolCall(
        id="call_1",
        name="echo",
        arguments={"text": "Hello from Grail!"},
    )
    
    result = await backend.execute(tool_call, tool_schema, {})
    
    print("=== Result ===")
    print(f"Output: {result.output}")
    print(f"Is error: {result.is_error}")
    
    backend.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**Input:** `{"text": "Hello from Grail!"}`
**Expected Output:** `{"result": "Hello from Grail!"}`

**Validation:** Output should match input. Check `agents/shellper_demo/echo.pym` to confirm behavior.

---

### Step 4: Create and Run Custom Grail Scripts

**Goal:** Create new Grail scripts for the demo and verify they work.

**File:** `demo_steps/scripts/add.pym` (create this file)

```python
from grail import Input

a: int = Input("a", description="First number")
b: int = Input("b", description="Second number")

result = {"sum": a + b}
result
```

**File:** `demo_steps/scripts/multiply.pym` (create this file)

```python
from grail import Input

a: int = Input("a", description="First number")
b: int = Input("b", description="Second number")

result = {"product": a * b}
result
```

**File:** `demo_steps/step04_custom_grail.py`

```python
"""Step 4: Execute custom Grail scripts."""
import asyncio
from pathlib import Path
from structured_agents import (
    GrailBackend,
    GrailBackendConfig,
    ToolCall,
    ToolSchema,
)

SCRIPTS_DIR = Path(__file__).parent / "scripts"

async def main():
    config = GrailBackendConfig(grail_dir=SCRIPTS_DIR)
    backend = GrailBackend(config)
    
    # Test add
    add_schema = ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        script_path=SCRIPTS_DIR / "add.pym",
    )
    
    add_call = ToolCall(id="call_1", name="add", arguments={"a": 5, "b": 3})
    add_result = await backend.execute(add_call, add_schema, {})
    
    print("=== add(5, 3) ===")
    print(f"Output: {add_result.output}")
    
    # Test multiply
    multiply_schema = ToolSchema(
        name="multiply",
        description="Multiply two numbers",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        script_path=SCRIPTS_DIR / "multiply.pym",
    )
    
    multiply_call = ToolCall(id="call_2", name="multiply", arguments={"a": 4, "b": 7})
    multiply_result = await backend.execute(multiply_call, multiply_schema, {})
    
    print("\n=== multiply(4, 7) ===")
    print(f"Output: {multiply_result.output}")
    
    backend.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**Expected Output:**
```
=== add(5, 3) ===
Output: {"sum": 8}
=== multiply(4, 7) ===
Output: {"product": 28}
```

**Validation:** Both scripts should return correct mathematical results.

---

## Phase 3: Simple Specialized Agents

### Step 5: Grail Dispatcher (Pass-Through Agent)

**Goal:** Create a lightweight agent that routes commands to specific Grail scripts. This is the SIMPLEST agent pattern - just command routing, no LLM involved.

**File:** `demo_steps/step05_grail_dispatcher.py`

```python
"""Step 5: Grail Dispatcher - pass-through agent pattern."""
import asyncio
from pathlib import Path
from structured_agents import (
    GrailBackend,
    GrailBackendConfig,
    ToolCall,
    ToolSchema,
)
import json

SCRIPTS_DIR = Path(__file__).parent / "scripts"


class GrailDispatcher:
    """A simple agent that dispatches commands to Grail scripts.
    
    This is NOT a full agent kernel - it's a lightweight wrapper
    that routes user commands to specific .pym scripts.
    No LLM involved - just direct script execution.
    """
    
    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir
        self.backend = GrailBackend(
            GrailBackendConfig(grail_dir=scripts_dir)
        )
        
        self.available_scripts = {}
        for pym_file in scripts_dir.glob("*.pym"):
            script_name = pym_file.stem
            self.available_scripts[script_name] = pym_file
    
    def list_commands(self) -> list[str]:
        """List available commands."""
        return list(self.available_scripts.keys())
    
    async def run(self, command: str, data: dict) -> dict:
        """Run a command with provided data.
        
        Args:
            command: The script name to run (e.g., "add")
            data: Parameters to pass to the script
            
        Returns:
            The result from the script execution
        """
        if command not in self.available_scripts:
            return {"error": f"Unknown command: {command}"}
        
        tool_schema = ToolSchema(
            name=command,
            description=f"Execute {command} operation",
            parameters={
                "type": "object",
                "properties": {
                    k: {"type": "number"} for k in data.keys()
                },
            },
            script_path=self.available_scripts[command],
        )
        
        tool_call = ToolCall(id="dispatch_1", name=command, arguments=data)
        result = await self.backend.execute(tool_call, tool_schema, {})
        
        return json.loads(result.output) if result.output else {}
    
    def shutdown(self):
        self.backend.shutdown()


async def main():
    dispatcher = GrailDispatcher(SCRIPTS_DIR)
    
    print(f"Available commands: {dispatcher.list_commands()}")
    
    # Test commands
    result1 = await dispatcher.run("add", {"a": 5, "b": 3})
    print(f"\nadd(5, 3) = {result1}")
    
    result2 = await dispatcher.run("multiply", {"a": 4, "b": 7})
    print(f"multiply(4, 7) = {result2}")
    
    dispatcher.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**Commands:** `dispatcher.run("add", {"a": 5, "b": 3})`
**Expected Output:** `{"sum": 8}`

**Validation:** The dispatcher should correctly route to the right script.

**Why this is simple:** No LLM, no grammar, no tool selection - just direct routing to scripts.

---

### Step 6: Chat Agent (Stateful LLM)

**Goal:** Create a simple chat agent that maintains conversation history. This is a SIMPLE agent pattern - just LLM calls with message history, no tools.

**File:** `demo_steps/step06_chat_agent.py`

```python
"""Step 6: Stateful Chat Agent."""
import asyncio
from typing import List
from structured_agents import KernelConfig, Message, QwenPlugin
from structured_agents.client.factory import build_client


class ChatAgent:
    """A simple chat agent that maintains message history.
    
    This is NOT a tool-calling agent - it just maintains
    a conversation with the LLM. No tools involved.
    """
    
    def __init__(self, config: KernelConfig, system_prompt: str = "You are a helpful assistant."):
        self.config = config
        self.system_prompt = system_prompt
        self.client = build_client(config)
        self.plugin = QwenPlugin()
        self.history: List[Message] = [
            Message(role="developer", content=system_prompt),
        ]
    
    async def chat(self, user_message: str) -> str:
        """Send a message and get a response."""
        self.history.append(Message(role="user", content=user_message))
        
        formatted = self.plugin.format_messages(self.history, [])
        
        response = await self.client.chat_completion(
            messages=formatted,
            tools=None,
            tool_choice="none",
        )
        
        assistant_message = Message(role="assistant", content=response.content)
        self.history.append(assistant_message)
        
        return response.content
    
    def clear_history(self):
        """Clear conversation history."""
        self.history = [Message(role="developer", content=self.system_prompt)]
    
    async def close(self):
        await self.client.close()


async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.7,
        max_tokens=256,
    )
    
    agent = ChatAgent(
        config,
        system_prompt="You are a concise, helpful assistant."
    )
    
    # Multi-turn conversation
    print("=== Turn 1 ===")
    response1 = await agent.chat("Hello! What is your name?")
    print(f"Agent: {response1}")
    
    print("\n=== Turn 2 ===")
    response2 = await agent.chat("What is 2 + 2?")
    print(f"Agent: {response2}")
    
    print("\n=== Turn 3 ===")
    response3 = await agent.chat("Thanks! What was my first question?")
    print(f"Agent: {response3}")
    
    # Show history
    print("\n=== Conversation History ===")
    for msg in agent.history:
        print(f"{msg.role}: {msg.content[:50]}...")
    
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Input:** Multi-turn conversation
**Expected Output:** Each response should be contextually appropriate, and turn 3 should reference turn 1.

**Validation:** The agent should maintain context across turns.

**Why this is simple:** No tools, no grammar, no tool execution - just LLM calls with message history.

---

## Phase 4: Tool-Calling Agents (Complex)

Now that we've verified:
- vLLM connectivity (Step 1)
- Basic chat (Step 2)
- Grail backend works (Steps 3-4)
- Simple dispatcher works (Step 5)
- Simple chat works (Step 6)

We can now build more complex agents that COMBINE LLM with tool execution.

### Step 7: Grammar-Constrained Decoding

**Goal:** Use XGrammar to constrain model output to a specific format. This is foundational for tool-calling agents.

**File:** `demo_steps/step07_grammar_decoding.py`

```python
"""Step 7: Grammar-constrained decoding with XGrammar."""
import asyncio
from structured_agents import KernelConfig, Message, QwenPlugin, ToolSchema
from structured_agents.client.factory import build_client
from structured_agents.grammar.config import GrammarConfig

async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    client = build_client(config)
    plugin = QwenPlugin()
    
    # Define a simple tool schema
    tools = [
        ToolSchema(
            name="calculator",
            description="Perform a calculation",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["add", "subtract", "multiply"]},
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["operation", "a", "b"],
            },
        )
    ]
    
    messages = [
        Message(role="developer", content="You are a calculator assistant."),
        Message(role="user", content="What is 5 + 3?"),
    ]
    
    formatted = plugin.format_messages(messages, tools)
    formatted_tools = plugin.format_tools(tools)
    grammar = plugin.build_grammar(tools, GrammarConfig())
    extra_body = plugin.to_extra_body(grammar)
    
    response = await client.chat_completion(
        messages=formatted,
        tools=formatted_tools,
        tool_choice="auto",
        extra_body=extra_body,
    )
    
    print("=== Response ===")
    print(f"Content: {response.content}")
    print(f"Tool calls: {response.tool_calls}")
    
    # Parse the response
    content, tool_calls = plugin.parse_response(response.content, response.tool_calls)
    print(f"\nParsed content: {content}")
    print(f"Parsed tool calls: {tool_calls}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Input:** "What is 5 + 3?"
**Expected Output:** A tool call with `{"operation": "add", "a": 5, "b": 3}`

**Validation:** Model should produce a valid tool call conforming to the schema.

---

### Step 8: Shell Agent (Single Tool Call)

**Goal:** Build a minimal agent that calls a Grail tool based on LLM output. Combines LLM + tool execution.

**File:** `demo_steps/step08_shell_agent_single.py`

```python
"""Step 8: Shell agent with single tool call."""
import asyncio
from pathlib import Path
from structured_agents import (
    KernelConfig,
    Message,
    QwenPlugin,
    GrailBackend,
    GrailBackendConfig,
    ToolSchema,
    build_client,
)
from structured_agents.grammar.config import GrammarConfig

TOOLS_DIR = Path("agents/shellper_demo")

SHELL_TOOLS = [
    ToolSchema(
        name="echo",
        description="Echo back the input text",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"},
            },
            "required": ["text"],
        },
        script_path=TOOLS_DIR / "echo.pym",
    ),
    ToolSchema(
        name="pwd",
        description="Print working directory",
        parameters={"type": "object", "properties": {}},
        script_path=TOOLS_DIR / "pwd.pym",
    ),
]

async def main():
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    
    client = build_client(config)
    plugin = QwenPlugin()
    backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    
    messages = [
        Message(
            role="developer",
            content="You are a helpful assistant that can use shell commands.",
        ),
        Message(role="user", content="Echo 'Hello World'"),
    ]
    
    # Format for model
    formatted_messages = plugin.format_messages(messages, SHELL_TOOLS)
    formatted_tools = plugin.format_tools(SHELL_TOOLS)
    grammar = plugin.build_grammar(SHELL_TOOLS, GrammarConfig())
    extra_body = plugin.to_extra_body(grammar)
    
    # Make LLM call
    response = await client.chat_completion(
        messages=formatted_messages,
        tools=formatted_tools,
        tool_choice="auto",
        extra_body=extra_body,
    )
    
    print("=== LLM Response ===")
    print(f"Content: {response.content}")
    print(f"Tool calls: {response.tool_calls}")
    
    # Parse and execute
    content, tool_calls = plugin.parse_response(response.content, response.tool_calls)
    
    if tool_calls:
        tool_call = tool_calls[0]
        tool_schema = next(t for t in SHELL_TOOLS if t.name == tool_call.name)
        
        print(f"\n=== Executing {tool_call.name} ===")
        print(f"Arguments: {tool_call.arguments}")
        
        result = await backend.execute(tool_call, tool_schema, {})
        print(f"Result: {result.output}")
    
    await client.close()
    backend.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**Input:** "Echo 'Hello World'"
**Expected Output:** Tool call to `echo` with `{"text": "Hello World"}`, result: `{"result": "Hello World"}`

**Validation:** Model should generate correct tool call, and tool should execute successfully.

---

### Step 9: Full Shell Agent with Multiple Tools

**Goal:** Shell agent with more tools - tool selection based on LLM output.

**File:** `demo_steps/step09_shell_agent_extended.py`

```python
"""Step 9: Extended shell agent with multiple tools."""
import asyncio
from pathlib import Path
from structured_agents import (
    KernelConfig,
    Message,
    QwenPlugin,
    GrailBackend,
    GrailBackendConfig,
    ToolSchema,
    build_client,
)
from structured_agents.grammar.config import GrammarConfig

TOOLS_DIR = Path("agents/shellper_demo")

SHELL_TOOLS = [
    ToolSchema(
        name="echo",
        description="Echo back the input text",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        script_path=TOOLS_DIR / "echo.pym",
    ),
    ToolSchema(
        name="pwd",
        description="Print working directory",
        parameters={"type": "object", "properties": {}},
        script_path=TOOLS_DIR / "pwd.pym",
    ),
    ToolSchema(
        name="ls",
        description="List files in directory",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "boolean", "description": "Show hidden files"}},
        },
        script_path=TOOLS_DIR / "ls.pym",
    ),
    ToolSchema(
        name="mkdir",
        description="Create a directory",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        script_path=TOOLS_DIR / "mkdir.pym",
    ),
]


class ToolCallingAgent:
    """A simple agent that calls tools based on LLM output."""
    
    def __init__(self, config: KernelConfig, tools: list[ToolSchema], backend: GrailBackend):
        self.config = config
        self.tools = tools
        self.backend = backend
        self.client = build_client(config)
        self.plugin = QwenPlugin()
    
    async def run(self, prompt: str) -> dict:
        messages = [
            Message(role="developer", content="You are a shell assistant."),
            Message(role="user", content=prompt),
        ]
        
        formatted = self.plugin.format_messages(messages, self.tools)
        formatted_tools = self.plugin.format_tools(self.tools)
        grammar = self.plugin.build_grammar(self.tools, GrammarConfig())
        extra_body = self.plugin.to_extra_body(grammar)
        
        response = await self.client.chat_completion(
            messages=formatted,
            tools=formatted_tools,
            tool_choice="auto",
            extra_body=extra_body,
        )
        
        content, tool_calls = self.plugin.parse_response(
            response.content, response.tool_calls
        )
        
        if not tool_calls:
            return {"content": content, "tool_call": None}
        
        tool_call = tool_calls[0]
        tool_schema = next(t for t in self.tools if t.name == tool_call.name)
        result = await self.backend.execute(tool_call, tool_schema, {})
        
        return {
            "content": content,
            "tool_call": {"name": tool_call.name, "arguments": tool_call.arguments},
            "result": result.output,
        }
    
    async def close(self):
        await self.client.close()
        self.backend.shutdown()


async def main():
    backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    
    agent = ToolCallingAgent(config, SHELL_TOOLS, backend)
    
    # Test various prompts
    test_prompts = [
        "What is my current directory?",
        "List the files in the current directory",
        "Echo 'test successful'",
    ]
    
    for prompt in test_prompts:
        print(f"\n=== Prompt: {prompt} ===")
        result = await agent.run(prompt)
        print(f"Content: {result.get('content')}")
        if result.get('tool_call'):
            print(f"Tool: {result['tool_call']['name']}")
            print(f"Result: {result.get('result')}")
    
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Expected Output:** The agent should correctly route to different tools:
- "What is my current directory?" → `pwd`
- "List the files..." → `ls`
- "Echo 'test...'" → `echo`

**Validation:** Each prompt should trigger the correct tool.

---

### Step 10: Code Agent

**Goal:** Use existing code_helper tools (generate_docstring, summarize_code).

**File:** `demo_steps/step10_code_agent.py`

```python
"""Step 10: Code agent using code_helper tools."""
import asyncio
from pathlib import Path
from structured_agents import (
    KernelConfig,
    Message,
    QwenPlugin,
    GrailBackend,
    GrailBackendConfig,
    ToolSchema,
    build_client,
)
from structured_agents.grammar.config import GrammarConfig
from step09_shell_agent_extended import ToolCallingAgent  # Reuse the class

TOOLS_DIR = Path("agents/code_helper")

CODE_TOOLS = [
    ToolSchema(
        name="generate_docstring",
        description="Generate a docstring for Python code",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code"},
                "function_name": {"type": "string", "description": "Optional function name"},
            },
            "required": ["code"],
        },
        script_path=TOOLS_DIR / "generate_docstring.pym",
    ),
    ToolSchema(
        name="summarize_code",
        description="Summarize what Python code does",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to summarize"},
            },
            "required": ["code"],
        },
        script_path=TOOLS_DIR / "summarize_code.pym",
    ),
]

SAMPLE_CODE = '''
def process_data(users: list[dict]) -> dict:
    """Process a list of user dictionaries and return statistics."""
    total = len(users)
    avg_age = sum(u.get('age', 0) for u in users) / total if total > 0 else 0
    return {'total_users': total, 'avg_age': avg_age}
'''


async def main():
    backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=512,
    )
    
    agent = ToolCallingAgent(config, CODE_TOOLS, backend)
    
    # Test docstring generation
    prompt = f"Generate a docstring for this code:\n{SAMPLE_CODE}"
    print(f"=== Prompt: {prompt[:50]}... ===")
    
    result = await agent.run(prompt)
    print(f"Content: {result.get('content')}")
    if result.get('tool_call'):
        print(f"Tool: {result['tool_call']['name']}")
        print(f"Result: {result.get('result')}")
    
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Input:** "Generate a docstring for this code: [code]"
**Expected Output:** A generated docstring for the function.

**Validation:** The tool should produce a valid docstring string.

---

## Phase 5: Full Orchestration

### Step 11: Orchestrated Demo

**Goal:** Wire all agents together in a single demo script.

**File:** `demo_steps/step11_orchestrated_demo.py`

```python
"""Step 11: Full orchestrated demo combining all agent types."""
import asyncio
from pathlib import Path
from structured_agents import (
    KernelConfig,
    Message,
    QwenPlugin,
    GrailBackend,
    GrailBackendConfig,
    ToolSchema,
    build_client,
)
from structured_agents.grammar.config import GrammarConfig


async def main():
    print("=" * 60)
    print("MULTI-AGENT ORCHESTRATION DEMO")
    print("=" * 60)
    
    # Configuration
    config = KernelConfig(
        base_url="http://remora-server:8000/v1",
        model="Qwen/Qwen3-4B-Instruct-2507-FP8",
        temperature=0.0,
        max_tokens=256,
    )
    
    # =========================================================================
    # 1. CHAT AGENT: Start the conversation
    # =========================================================================
    print("\n[1] Starting with CHAT AGENT...")
    from step06_chat_agent import ChatAgent
    chat_agent = ChatAgent(config, "You are a helpful project assistant.")
    
    response = await chat_agent.chat("Hello! Let's build a project.")
    print(f"    Chat Agent: {response}")
    
    # =========================================================================
    # 2. SHELL AGENT: Create directory
    # =========================================================================
    print("\n[2] Switching to SHELL AGENT...")
    from step09_shell_agent_extended import ToolCallingAgent
    
    shell_tools = [
        ToolSchema(name="echo", description="Echo", parameters={"properties": {"text": {"type": "string"}}, "required": ["text"]}, script_path=Path("agents/shellper_demo/echo.pym")),
        ToolSchema(name="mkdir", description="Make directory", parameters={"properties": {"path": {"type": "string"}}, "required": ["path"]}, script_path=Path("agents/shellper_demo/mkdir.pym")),
    ]
    shell_backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    shell_agent = ToolCallingAgent(config, shell_tools, shell_backend)
    
    result = await shell_agent.run("Create a directory called 'demo_project'")
    print(f"    Tool: {result['tool_call']['name']}")
    print(f"    Result: {result.get('result')}")
    
    # =========================================================================
    # 3. GRAIL DISPATCHER: Run some math
    # =========================================================================
    print("\n[3] Using GRAIL DISPATCHER...")
    from step05_grail_dispatcher import GrailDispatcher
    
    dispatcher = GrailDispatcher(Path(__file__).parent / "scripts")
    
    add_result = await dispatcher.run("add", {"a": 10, "b": 20})
    print(f"    add(10, 20) = {add_result}")
    
    mul_result = await dispatcher.run("multiply", {"a": 6, "b": 7})
    print(f"    multiply(6, 7) = {mul_result}")
    
    dispatcher.shutdown()
    
    # =========================================================================
    # 4. CHAT AGENT: Continue conversation
    # =========================================================================
    print("\n[4] Back to CHAT AGENT...")
    response = await chat_agent.chat("Now let's analyze some code.")
    print(f"    Chat Agent: {response}")
    
    # =========================================================================
    # 5. CODE AGENT: Generate docstring
    # =========================================================================
    print("\n[5] Switching to CODE AGENT...")
    
    code_tools = [
        ToolSchema(
            name="generate_docstring",
            description="Generate docstring",
            parameters={"properties": {"code": {"type": "string"}}, "required": ["code"]},
            script_path=Path("agents/code_helper/generate_docstring.pym"),
        ),
    ]
    code_backend = GrailBackend(GrailBackendConfig(grail_dir=Path.cwd() / "agents"))
    code_agent = ToolCallingAgent(config, code_tools, code_backend)
    
    sample_code = "def add(a, b): return a + b"
    result = await code_agent.run(f"Generate a docstring for: {sample_code}")
    print(f"    Tool: {result['tool_call']['name']}")
    print(f"    Result: {result.get('result')}")
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    await chat_agent.close()
    await shell_agent.close()
    await code_agent.close()
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Dependency Graph

```
Phase 1: Infrastructure
├── Step 1: vLLM connectivity ──────────────┐
└── Step 2: Basic chat ──────────────────────┘
                                        │
Phase 2: Grail Backend                    │
├── Step 3: Single Grail script ──────────┤
└── Step 4: Custom Grail scripts ─────────┘
                                        │
Phase 3: Simple Agents                     │
├── Step 5: Grail Dispatcher ─────────────┤    (No LLM, just routing)
└── Step 6: Chat Agent ────────────────────┘    (LLM + history, no tools)
                                        │
Phase 4: Tool-Calling Agents               │
├── Step 7: Grammar decoding ─────────────┤    (Foundation)
├── Step 8: Shell agent (1 tool) ─────────┤
├── Step 9: Shell agent (multi-tool) ─────┤
└── Step 10: Code agent ──────────────────┘
                                        │
Phase 5: Orchestration                     │
└── Step 11: Full demo ───────────────────┘    (All combined)
```

---

## Step Summary

| Step | File | Purpose | Complexity |
|------|------|---------|-------------|
| 1 | `step01_verify_vllm.py` | Verify server connectivity | **Trivial** |
| 2 | `step02_basic_chat.py` | Simple chat without tools | **Trivial** |
| 3 | `step03_single_grail.py` | Execute single .pym | **Simple** |
| 4 | `step04_custom_grail.py` | Custom Grail scripts | **Simple** |
| 5 | `step05_grail_dispatcher.py` | Pass-through routing | **Simple** (no LLM) |
| 6 | `step06_chat_agent.py` | Stateful chat | **Simple** (no tools) |
| 7 | `step07_grammar_decoding.py` | Grammar-constrained output | **Medium** |
| 8 | `step08_shell_agent_single.py` | LLM → Tool call flow | **Medium** |
| 9 | `step09_shell_agent_extended.py` | Multiple tools | **Medium** |
| 10 | `step10_code_agent.py` | Code analysis tools | **Medium** |
| 11 | `step11_orchestrated_demo.py` | Combined demo | **Complex** |

---

## Running the Demo Steps

```bash
# Run individual steps in order
cd demo_steps
python step01_verify_vllm.py
python step02_basic_chat.py
python step03_single_grail.py
# ... continue in order

# DO NOT skip steps - each builds on previous validation
```

**Critical:** Run steps in order. Each step validates components needed by subsequent steps.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| vLLM connection refused | Check server is running at `remora-server:8000` |
| Model not found | Verify model name matches what's on server |
| Grail script errors | Check .pym syntax and `grail` import |
| Tool call parsing fails | Check GrammarConfig settings (Step 7) |
| Out of memory | Reduce batch sizes or model size |

---

## Next Steps After Implementation

1. Add observer event logging to show internal kernel events
2. Add concurrent tool execution demonstration
3. Create bundle.yaml files for each agent
4. Add error handling and retry logic
5. Add unit tests for each agent type
