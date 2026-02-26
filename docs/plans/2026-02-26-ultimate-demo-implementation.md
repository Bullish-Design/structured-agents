# Ultimate Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-module ultimate demo under `demo/ultimate_demo/` that showcases structured-agents in a project coordinator scenario with real vLLM + xgrammar structured output usage.

**Architecture:** The demo package is organized into small modules (state, tools, subagents, observer, coordinator, runner). The runner feeds inbox messages to a coordinator agent built with `AgentKernel`, `ModelAdapter`, and `ConstraintPipeline` using `build_structural_tag_constraint` against the Qwen3 vLLM server. Tools and subagent tools mutate a shared state object and record outputs for a final summary.

**Tech Stack:** Python 3.13, structured-agents core APIs, vLLM OpenAI-compatible API, XGrammar structural tags.

---

### Task 1: Create demo package skeleton

**Files:**
- Create: `demo/ultimate_demo/__init__.py`
- Create: `demo/ultimate_demo/config.py`
- Create: `demo/ultimate_demo/state.py`
- Create: `demo/ultimate_demo/tools.py`
- Create: `demo/ultimate_demo/subagents.py`
- Create: `demo/ultimate_demo/observer.py`
- Create: `demo/ultimate_demo/coordinator.py`
- Create: `demo/ultimate_demo/runner.py`

**Step 1: Write a minimal import check test**

Create `tests/test_demo/test_ultimate_demo_imports.py`:

```python
from demo.ultimate_demo import coordinator, runner

def test_demo_imports():
    assert coordinator is not None
    assert runner is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo/test_ultimate_demo_imports.py::test_demo_imports -v`
Expected: FAIL with import errors because the package doesn’t exist.

**Step 3: Create empty module files**

```python
# demo/ultimate_demo/__init__.py
```

```python
# demo/ultimate_demo/config.py
```

```python
# demo/ultimate_demo/state.py
```

```python
# demo/ultimate_demo/tools.py
```

```python
# demo/ultimate_demo/subagents.py
```

```python
# demo/ultimate_demo/observer.py
```

```python
# demo/ultimate_demo/coordinator.py
```

```python
# demo/ultimate_demo/runner.py
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo/test_ultimate_demo_imports.py::test_demo_imports -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add demo/ultimate_demo tests/test_demo/test_ultimate_demo_imports.py
git commit -m "test: add ultimate demo import scaffold"
```

---

### Task 2: Define demo configuration and state

**Files:**
- Modify: `demo/ultimate_demo/config.py`
- Modify: `demo/ultimate_demo/state.py`
- Test: `tests/test_demo/test_ultimate_demo_state.py`

**Step 1: Write the failing test**

Create `tests/test_demo/test_ultimate_demo_state.py`:

```python
from demo.ultimate_demo.state import DemoState, TaskItem


def test_state_tracks_tasks():
    state = DemoState.initial()
    state.tasks.append(TaskItem(title="Kickoff", status="open"))
    assert state.tasks[0].title == "Kickoff"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo/test_ultimate_demo_state.py::test_state_tracks_tasks -v`
Expected: FAIL with missing symbols.

**Step 3: Implement config and state**

```python
# demo/ultimate_demo/config.py
from structured_agents.grammar.config import DecodingConstraint

BASE_URL = "http://remora-server:8000/v1"
MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507-FP8"
API_KEY = "EMPTY"

GRAMMAR_CONFIG = DecodingConstraint(
    strategy="structural_tag",
    allow_parallel_calls=True,
    send_tools_to_api=False,
)
```

```python
# demo/ultimate_demo/state.py
from dataclasses import dataclass, field
from typing import Literal


Status = Literal["open", "in_progress", "blocked", "done"]


@dataclass
class TaskItem:
    title: str
    status: Status
    owner: str | None = None


@dataclass
class RiskItem:
    description: str
    mitigation: str


@dataclass
class DemoState:
    inbox: list[str] = field(default_factory=list)
    outbox: list[str] = field(default_factory=list)
    tasks: list[TaskItem] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    updates: list[str] = field(default_factory=list)
    tool_log: list[str] = field(default_factory=list)

    @classmethod
    def initial(cls) -> "DemoState":
        return cls()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo/test_ultimate_demo_state.py::test_state_tracks_tasks -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add demo/ultimate_demo/config.py demo/ultimate_demo/state.py tests/test_demo/test_ultimate_demo_state.py
git commit -m "feat: add ultimate demo state and config"
```

---

### Task 3: Implement demo tools and observer

**Files:**
- Modify: `demo/ultimate_demo/tools.py`
- Modify: `demo/ultimate_demo/observer.py`
- Test: `tests/test_demo/test_ultimate_demo_tools.py`

**Step 1: Write the failing test**

Create `tests/test_demo/test_ultimate_demo_tools.py`:

```python
import asyncio
from demo.ultimate_demo.state import DemoState
from demo.ultimate_demo.tools import LogUpdateTool


def test_log_update_tool_updates_state():
    state = DemoState.initial()
    tool = LogUpdateTool(state)
    result = asyncio.run(tool.execute({"update": "Kickoff done"}, None))
    assert "Kickoff done" in state.updates
    assert result.is_error is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo/test_ultimate_demo_tools.py::test_log_update_tool_updates_state -v`
Expected: FAIL with missing symbols.

**Step 3: Implement tools + observer**

```python
# demo/ultimate_demo/tools.py
from dataclasses import dataclass
from structured_agents.tools.protocol import Tool
from structured_agents.types import ToolCall, ToolResult, ToolSchema
from demo.ultimate_demo.state import DemoState, TaskItem, RiskItem


@dataclass
class LogUpdateTool(Tool):
    state: DemoState

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="log_update",
            description="Log a stakeholder update",
            parameters={
                "type": "object",
                "properties": {"update": {"type": "string"}},
                "required": ["update"],
            },
        )

    async def execute(self, args: dict, context: ToolCall | None) -> ToolResult:
        update = str(args.get("update", ""))
        self.state.updates.append(update)
        self.state.tool_log.append("log_update")
        return ToolResult(call_id=context.id if context else "", name=self.schema.name, output=update, is_error=False)
```

```python
# demo/ultimate_demo/observer.py
from structured_agents.events.observer import Observer
from structured_agents.events.types import Event


class DemoObserver(Observer):
    async def emit(self, event: Event) -> None:
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo/test_ultimate_demo_tools.py::test_log_update_tool_updates_state -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add demo/ultimate_demo/tools.py demo/ultimate_demo/observer.py tests/test_demo/test_ultimate_demo_tools.py
git commit -m "feat: add ultimate demo tools and observer"
```

---

### Task 4: Add subagent tool wrappers

**Files:**
- Modify: `demo/ultimate_demo/subagents.py`
- Test: `tests/test_demo/test_ultimate_demo_subagents.py`

**Step 1: Write the failing test**

Create `tests/test_demo/test_ultimate_demo_subagents.py`:

```python
from demo.ultimate_demo.subagents import SubagentSpec


def test_subagent_spec_structures():
    spec = SubagentSpec(name="risk", purpose="Assess risk")
    assert spec.name == "risk"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo/test_ultimate_demo_subagents.py::test_subagent_spec_structures -v`
Expected: FAIL.

**Step 3: Implement subagent specs and tool wrapper (skeleton)**

```python
# demo/ultimate_demo/subagents.py
from dataclasses import dataclass
from structured_agents.tools.protocol import Tool
from structured_agents.types import ToolCall, ToolResult, ToolSchema
from demo.ultimate_demo.state import DemoState


@dataclass
class SubagentSpec:
    name: str
    purpose: str


@dataclass
class SubagentTool(Tool):
    state: DemoState
    spec: SubagentSpec

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.spec.name,
            description=self.spec.purpose,
            parameters={"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]},
        )

    async def execute(self, args: dict, context: ToolCall | None) -> ToolResult:
        output = f"Subagent {self.spec.name} received: {args.get('input', '')}"
        self.state.tool_log.append(self.spec.name)
        return ToolResult(call_id=context.id if context else "", name=self.spec.name, output=output, is_error=False)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo/test_ultimate_demo_subagents.py::test_subagent_spec_structures -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add demo/ultimate_demo/subagents.py tests/test_demo/test_ultimate_demo_subagents.py
git commit -m "feat: add demo subagent scaffolding"
```

---

### Task 5: Build coordinator + runner

**Files:**
- Modify: `demo/ultimate_demo/coordinator.py`
- Modify: `demo/ultimate_demo/runner.py`
- Modify: `demo/ultimate_demo/tools.py`
- Modify: `demo/ultimate_demo/subagents.py`
- Test: `tests/test_demo/test_ultimate_demo_runner.py`

**Step 1: Write the failing test**

Create `tests/test_demo/test_ultimate_demo_runner.py`:

```python
from demo.ultimate_demo.runner import build_demo_state


def test_runner_builds_state():
    state = build_demo_state()
    assert state.inbox == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo/test_ultimate_demo_runner.py::test_runner_builds_state -v`
Expected: FAIL.

**Step 3: Implement coordinator + runner**

- Add real `AgentKernel` build with `ConstraintPipeline` and `DecodingConstraint`.
- Wire tools and subagent tools into `AgentKernel`.
- Implement runner to seed inbox/outbox and trigger `Agent.run` for each inbox message.
- Ensure the final summary prints state and outbox transcript.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo/test_ultimate_demo_runner.py::test_runner_builds_state -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add demo/ultimate_demo/coordinator.py demo/ultimate_demo/runner.py demo/ultimate_demo/tools.py demo/ultimate_demo/subagents.py tests/test_demo/test_ultimate_demo_runner.py
git commit -m "feat: add ultimate demo coordinator and runner"
```

---

### Task 6: Polish demo flow and documentation

**Files:**
- Modify: `demo/ultimate_demo/runner.py`
- Modify: `demo/ultimate_demo/__init__.py`

**Step 1: Add a final summary output**

Include state summary + tool log + risks in runner output.

**Step 2: Run demo manually**

Run: `python -m demo.ultimate_demo.runner`
Expected: printed inbox/outbox progression and final summary.

**Step 3: Commit**

```bash
git add demo/ultimate_demo/runner.py demo/ultimate_demo/__init__.py
git commit -m "feat: finalize ultimate demo output"
```
