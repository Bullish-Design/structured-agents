# Demo Concept: Multi-Agent Orchestration with structured-agents

## Overview

Create a comprehensive demo that showcases the full capabilities of the `structured-agents` library through a multi-agent orchestration scenario. The demo will use:
- **Model**: Qwen3-4B at `remora-server:8000`
- **Backend**: Grail (real `.pym` tool execution)
- **Agents**: Shell/File, Data Wrangling, Code Analysis

---

## Option 1: Sequential Agent Pipeline (Recommended)

A scripted sequence where each agent handles a specific task domain, with clear handoffs between them.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Demo Orchestrator                        │
├─────────────────────────────────────────────────────────────┤
│  Task 1: Shell Agent (list files, create structure)        │
│     ↓                                                        │
│  Task 2: Data Agent (generate/sample data, transform)       │
│     ↓                                                        │
│  Task 3: Code Agent (analyze generated code)               │
│     ↓                                                        │
│  Task 4: Shell Agent (verify files, show results)           │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

1. **Shell Agent** (`QwenPlugin` + `shellper_demo` tools):
   - Tools: `ls`, `mkdir`, `cat`, `echo`, `grep`
   - Task: Create project directory structure

2. **Data Agent** (custom Grail tools):
   - Tools: `generate_sample_data`, `transform_json_to_csv`, `validate_data`
   - Task: Create and transform sample data files

3. **Code Agent** (`code_helper` tools):
   - Tools: `generate_docstring`, `summarize_code`
   - Task: Analyze generated Python code

### Pros
- Clear demonstration of agent switching
- Each agent has distinct, well-defined tools
- Shows grammar-constrained decoding in action
- Easy to follow and understand

### Cons
- More code to write (3 separate kernels)
- Need to manage state between agents

---

## Option 2: Intelligent Router Pattern

A single kernel with all tools available, using an LLM to intelligently route to the right tool.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Single Kernel + All Tools                │
├─────────────────────────────────────────────────────────────┤
│  Tools: [shell tools + data tools + code tools]             │
│                                                              │
│  User Request → Router (LLM) → Execute Tool → Response      │
│         ↓                                                    │
│    If complex, can delegate to sub-kernels                  │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

1. Single `AgentKernel` with combined tool source
2. All tools from all agents registered
3. Qwen model picks the right tool based on request

### Pros
- Simpler code structure
- Shows tool selection/routing
- More "intelligent" feel

### Cons
- Less clear demonstration of agent switching
- Tool namespace collisions possible
- Harder to debug what's happening

---

## Option 3: Bundle-Based Agent System

Use the `AgentBundle` system to package agents as directories with `bundle.yaml`.

### Architecture

```
agents/
├── shell_agent/
│   ├── bundle.yaml (tools, prompt, model config)
│   └── tools/
│       ├── ls.pym
│       ├── cat.pym
│       └── ...
├── data_agent/
│   └── ...
└── code_agent/
    └── ...
```

### Implementation

1. Create bundle.yaml files for each agent
2. Use `load_bundle()` to load each agent
3. Switch agents by loading different bundles

### Pros
- Most "production-like" pattern
- Shows the bundle system
- Clean separation of concerns

### Cons
- Requires creating bundle.yaml files
- More setup overhead
- Bundle system might need more work

---

## Recommended Approach: Option 1 with Refinements

**Option 1** is recommended because it most clearly demonstrates:
1. How to create multiple agents with different plugins
2. How to use the Grail backend for real tool execution
3. How grammar-constrained decoding works
4. How to switch between agents programmatically
5. How to compose the observer system

### Key Features to Showcase

| Feature | How to Demonstrate |
|---------|-------------------|
| **Grammar-constrained decoding** | Use `GrammarConfig` with each agent, show EBNF generation |
| **Grail backend** | Real `.pym` tool execution (not mocks) |
| **Observer events** | Log kernel events (model_request, tool_call, etc.) |
| **Plugin system** | Use `QwenPlugin` for model interaction |
| **Tool sources** | Show `RegistryBackendToolSource` pattern |
| **Bundle system** | Optional: show `load_bundle()` loading |

### Demo Script Flow

```
1. Initialize all 3 agents (Shell, Data, Code)
2. Shell Agent: "Create a new project directory called 'demo_project'"
3. Data Agent: "Generate sample JSON data and save to demo_project/data.json"
4. Code Agent: "Generate a Python function that processes the data and save to demo_project/processor.py"
5. Code Agent: "Generate a docstring for processor.py"
6. Shell Agent: "Show me all files in demo_project and their contents"
7. Print summary of what each agent did
```

### Required Grail Tools

Need to ensure these `.pym` tools exist or create them:
- `mkdir` - existing in shellper_demo
- `ls` - existing in shellper_demo  
- `echo` - existing in shellper_demo
- `generate_sample_data` - need to create
- `transform_data` - need to create
- `generate_docstring` - existing in code_helper
- `summarize_code` - existing in code_helper

---

## Expanded Agent Types (v2)

The user has requested two additional agent patterns:

### Type 4: Grail Pass-Through Agent (Multi-Script Dispatcher)

A lightweight agent that wraps multiple Grail scripts, triggered by passing a command name and input data. The agent routes to the appropriate script based on the command.

**Use case**: Turn a collection of Grail scripts into an "agent" that can be invoked with specific commands.

**Pattern**:
```
User: "Run 'add' with a=5, b=3"
→ Agent: command="add", data={"a": 5, "b": 3}
→ Executes add.pym, returns 8

User: "Run 'transform' with data={...}"
→ Agent: command="transform", data={...}
→ Executes transform.pym, returns result
```

**Bundle structure**:
```yaml
# grail_tool_agent/bundle.yaml
name: grail_tool_agent
type: pass_through
scripts:
  - add.pym
  - multiply.pym
  - transform.pym
```

### Type 5: LLM Chat Agent (Stateful)

A simple agent that maintains a chat message chain and makes calls to vLLM. The command specifies the text to send. Conversation history is preserved between turns.

**Use case**: Conversational agent without tools, just pure LLM chat with memory.

**Pattern**:
```
User: "Hello, who are you?"
→ [LLM call with system + user message]
→ Agent: "I am a helpful AI assistant!"

User: "What's 2+2?"
→ [LLM call with system + history + user message]
→ Agent: "2+2 equals 4."
```

**Bundle structure**:
```yaml
# chat_agent/bundle.yaml
name: chat_agent
type: chat
model: Qwen/Qwen3-4B-Instruct-2507-FP8
system_prompt: "You are a helpful, concise assistant."
max_tokens: 256
temperature: 0.7
```

---

## Final Design: Single Orchestrated Flow

### The 5 Agent Types

| Type | Description | Tools/Approach |
|------|-------------|----------------|
| **Shell Agent** | Filesystem operations | `ls`, `mkdir`, `cat`, `echo`, `grep` from shellper_demo |
| **Data Agent** | Data generation/transformation | Custom Grail scripts: `generate_data`, `transform_data` |
| **Code Agent** | Code analysis | `generate_docstring`, `summarize_code` from code_helper |
| **Grail Dispatcher** | Pass-through script execution | Multi-script dispatcher: `add`, `multiply`, etc. |
| **Chat Agent** | Stateful LLM conversation | Pure vLLM calls with message history |

### Demo Flow (Single Script)

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATED DEMO FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. CHAT AGENT: "Hello! Let's build a project."                │
│     → Establishes context, explains plan                        │
│                                                                  │
│  2. SHELL AGENT: "Create directory 'demo_project'"             │
│     → mkdir demo_project                                        │
│                                                                  │
│  3. DATA AGENT: "Generate sample user data"                    │
│     → generate_data.pym → save to demo_project/users.json      │
│                                                                  │
│  4. CHAT AGENT: "Now let's do some math"                       │
│     → Pure conversation                                         │
│                                                                  │
│  5. GRAIL DISPATCHER: "Run 'add' with 5 and 3"                │
│     → Executes add.pym → returns 8                             │
│                                                                  │
│  6. GRAIL DISPATCHER: "Run 'multiply' with 4 and 7"            │
│     → Executes multiply.pym → returns 28                       │
│                                                                  │
│  7. CODE AGENT: "Generate a function to process users.json"   │
│     → Creates processor.py                                      │
│                                                                  │
│  8. CODE AGENT: "Generate docstring for processor.py"          │
│     → generate_docstring.pym                                    │
│                                                                  │
│  9. SHELL AGENT: "List all files in demo_project"             │
│     → ls demo_project                                           │
│                                                                  │
│ 10. CHAT AGENT: "Summarize what we built today"               │
│     → Conversational summary with full context                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Bundle Structure

```
agents/
├── shell_agent/           # Full tool-calling agent
│   ├── bundle.yaml
│   └── tools/
├── data_agent/           # Full tool-calling agent  
│   ├── bundle.yaml
│   └── tools/
├── code_agent/           # Full tool-calling agent
│   ├── bundle.yaml
│   └── tools/
├── grail_dispatcher/     # Pass-through agent
│   ├── bundle.yaml
│   └── scripts/
│       ├── add.pym
│       └── multiply.pym
└── chat_agent/           # Chat-only agent
    └── bundle.yaml
```

### Key Implementation Points

1. **Agent Switching**: Create separate `AgentKernel` instances for each agent type, or use agent routing
2. **Grail Backend**: All tool execution uses real `.pym` scripts via `GrailBackend`
3. **Grammar**: Each tool-calling agent uses `GrammarConfig` for constrained decoding
4. **Observers**: Log events from each agent to show internal behavior
5. **Message Passing**: Results from one agent feed into the next

### What's Needed

- [ ] Create bundle.yaml files for 5 agents
- [ ] Create grail_dispatcher scripts (add.pym, multiply.pym)
- [ ] Create data_agent tools (generate_data.pym, transform_data.pym)
- [ ] Main orchestrator script that runs the flow
- [ ] Observer logging to show what's happening
