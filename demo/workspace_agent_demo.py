import asyncio
import os
import time
from asyncio import run
from pathlib import Path
from typing import Any, Callable

from structured_agents import (
    AgentKernel,
    KernelConfig,
    Message,
    ToolCall,
    ToolExecutionStrategy,
    ToolResult,
)
from structured_agents.bundles import load_bundle
from structured_agents.bundles.loader import AgentBundle
from structured_agents.grammar.config import GrammarConfig
from structured_agents.observer import (
    CompositeObserver,
    KernelEndEvent,
    KernelStartEvent,
    ModelRequestEvent,
    ModelResponseEvent,
    NullObserver,
    ToolCallEvent,
    ToolResultEvent,
    TurnCompleteEvent,
)
from structured_agents.registries.grail import GrailRegistry, GrailRegistryConfig
from structured_agents.backends.grail import GrailBackend, GrailBackendConfig
from structured_agents.tool_sources.registry_backend import RegistryBackendToolSource
from structured_agents.plugins.qwen import QwenPlugin
from structured_agents.plugins.registry import PluginRegistry, get_plugin

AGENT_DIR = Path(__file__).parent / "agents" / "workspace_agent"
STATE_DIR = AGENT_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
AGENT_ID = "workspace_agent"


def build_externals(
    agent_id: str, context: dict[str, Any]
) -> dict[str, Callable[..., Any]]:
    async def ensure_dir(path: str) -> None:
        os.makedirs(path, exist_ok=True)

    async def write_file(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    async def read_file(path: str) -> str:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    async def list_dir(path: str) -> list[str]:
        try:
            return sorted(os.listdir(path))
        except FileNotFoundError:
            return []

    async def file_exists(path: str) -> bool:
        return os.path.exists(path)

    return {
        "ensure_dir": ensure_dir,
        "write_file": write_file,
        "read_file": read_file,
        "list_dir": list_dir,
        "file_exists": file_exists,
    }


class DemoObserver:
    """Observer that logs all kernel events for demo visibility."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def on_kernel_start(self, event: KernelStartEvent) -> None:
        print(
            f"  [KERNEL] Starting: {event.tools_count} tools, max {event.max_turns} turns"
        )
        self.events.append({"type": "kernel_start", "event": event})

    async def on_model_request(self, event: ModelRequestEvent) -> None:
        print(
            f"  [MODEL REQUEST] Turn {event.turn}: {event.messages_count} messages, {event.tools_count} tools"
        )
        self.events.append({"type": "model_request", "event": event})

    async def on_model_response(self, event: ModelResponseEvent) -> None:
        usage_str = ""
        if event.usage:
            usage_str = f" | tokens: {event.usage.prompt_tokens}p/{event.usage.completion_tokens}c"
        print(
            f"  [MODEL RESPONSE] Turn {event.turn}: {event.duration_ms}ms, {event.tool_calls_count} tool calls{usage_str}"
        )
        self.events.append({"type": "model_response", "event": event})

    async def on_tool_call(self, event: ToolCallEvent) -> None:
        args_preview = (
            str(event.arguments)[:60] + "..."
            if len(str(event.arguments)) > 60
            else str(event.arguments)
        )
        print(f"  [TOOL CALL] Turn {event.turn}: {event.tool_name}({args_preview})")
        self.events.append({"type": "tool_call", "event": event})

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        status = "ERROR" if event.is_error else "OK"
        print(
            f"  [TOOL RESULT] Turn {event.turn}: {event.tool_name} [{status}] {event.duration_ms}ms"
        )
        self.events.append({"type": "tool_result", "event": event})

    async def on_turn_complete(self, event: TurnCompleteEvent) -> None:
        print(
            f"  [TURN {event.turn} COMPLETE] {event.tool_calls_count} calls, {event.errors_count} errors"
        )
        self.events.append({"type": "turn_complete", "event": event})

    async def on_kernel_end(self, event: KernelEndEvent) -> None:
        print(
            f"  [KERNEL] Ended: {event.turn_count} turns, reason={event.termination_reason}, {event.total_duration_ms}ms"
        )
        self.events.append({"type": "kernel_end", "event": event})

    async def on_error(self, error: Exception, context: str | None = None) -> None:
        print(f"  [ERROR] {context}: {error}")
        self.events.append({"type": "error", "error": str(error), "context": context})


class MetricsObserver:
    """Observer that collects timing metrics."""

    def __init__(self) -> None:
        self.model_durations: list[int] = []
        self.tool_durations: list[int] = []

    async def on_model_response(self, event: ModelResponseEvent) -> None:
        self.model_durations.append(event.duration_ms)

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        self.tool_durations.append(event.duration_ms)

    async def on_kernel_start(self, event: KernelStartEvent) -> None:
        pass

    async def on_model_request(self, event: ModelRequestEvent) -> None:
        pass

    async def on_tool_call(self, event: ToolCallEvent) -> None:
        pass

    async def on_turn_complete(self, event: TurnCompleteEvent) -> None:
        pass

    async def on_kernel_end(self, event: KernelEndEvent) -> None:
        pass

    async def on_error(self, error: Exception, context: str | None = None) -> None:
        pass

    def summary(self) -> str:
        avg_model = (
            sum(self.model_durations) / len(self.model_durations)
            if self.model_durations
            else 0
        )
        avg_tool = (
            sum(self.tool_durations) / len(self.tool_durations)
            if self.tool_durations
            else 0
        )
        return f"Model avg: {avg_model:.0f}ms, Tool avg: {avg_tool:.0f}ms"


class WorkspaceAgent:
    """Workspace agent using AgentKernel with bundle configuration."""

    def __init__(self, bundle_dir: Path) -> None:
        self.bundle = load_bundle(bundle_dir)

        registry_config = GrailRegistryConfig(
            agents_dir=bundle_dir,
            use_grail_check=False,
            cache_schemas=True,
        )
        self.registry = GrailRegistry(registry_config)

        backend_config = GrailBackendConfig(grail_dir=bundle_dir)
        self.backend = GrailBackend(backend_config, externals_factory=build_externals)

        self.tool_source = RegistryBackendToolSource(
            registry=self.registry, backend=self.backend
        )

        self.demo_observer = DemoObserver()
        self.metrics_observer = MetricsObserver()
        self.observer = CompositeObserver([self.demo_observer, self.metrics_observer])

        self.kernel_config = KernelConfig(
            base_url="http://remora-server:8000/v1",
            model="Qwen/Qwen3-4B-Instruct-2507-FP8",
            temperature=0.0,
            max_tokens=512,
            tool_execution_strategy=ToolExecutionStrategy(mode="concurrent"),
        )

        self.kernel = AgentKernel(
            config=self.kernel_config,
            plugin=self.bundle.get_plugin(),
            tool_source=self.tool_source,
            observer=self.observer,
            grammar_config=self.bundle.get_grammar_config(),
        )

        self.inbox: list[dict[str, Any]] = []
        self.outbox: list[dict[str, Any]] = []

    async def _provide_context(self) -> dict[str, Any]:
        return {"state_dir": str(STATE_DIR), "agent_id": AGENT_ID}

    async def process_message(self, user_input: str, max_turns: int = 10) -> Any:
        """Process a natural language message through the full agent loop."""
        self.inbox.append({"text": user_input, "timestamp": time.time()})

        messages = self.bundle.build_initial_messages({"input": user_input})

        result = await self.kernel.run(
            initial_messages=messages,
            tools=self.bundle.tool_schemas,
            max_turns=max_turns,
            termination=lambda r: r.name == "submit_result",
            context_provider=self._provide_context,
        )

        self.outbox.append(
            {
                "input": user_input,
                "final_message": result.final_message.content
                if result.final_message
                else None,
                "turns": result.turn_count,
                "termination_reason": result.termination_reason,
                "total_usage": result.total_usage,
            }
        )

        return result

    async def close(self) -> None:
        await self.kernel.close()
        self.backend.shutdown()


async def section_1_bundle_loading(bundle_dir: Path) -> AgentBundle:
    """Section 1: Bundle Loading & Configuration."""
    print("\n" + "=" * 70)
    print("Section 1: Bundle Loading & Configuration")
    print("=" * 70)

    bundle = load_bundle(bundle_dir)
    plugin = bundle.get_plugin()
    grammar_config = bundle.get_grammar_config()

    print(f"\n  Loaded bundle: {bundle.manifest.name} v{bundle.manifest.version}")
    print(f"  Plugin: {plugin.name}")
    print(f"  Grammar mode: {grammar_config.mode}")
    print(f"  Tools: {', '.join(t.name for t in bundle.tool_schemas)}")
    print(f"  Max turns: {bundle.manifest.max_turns}")
    print(f"  Termination tool: {bundle.manifest.termination_tool}")

    return bundle


async def section_2_single_turn(agent: WorkspaceAgent) -> None:
    """Section 2: Single-Turn with Observer."""
    print("\n" + "=" * 70)
    print("Section 2: Single-Turn with Observer")
    print("=" * 70)

    query = "Add a task 'Review Q3 metrics' with high priority"
    print(f"\n  Query: {query}")

    result = await agent.process_message(query, max_turns=3)

    print(f"\n  RunResult:")
    print(f"    Turns taken: {result.turn_count}")
    print(f"    Termination reason: {result.termination_reason}")
    print(f"    History messages: {len(result.history)}")


async def section_3_multi_turn(agent: WorkspaceAgent) -> None:
    """Section 3: Multi-Turn Agent Loop."""
    print("\n" + "=" * 70)
    print("Section 3: Multi-Turn Agent Loop")
    print("=" * 70)

    query = "Add 'Design review' task with high priority, then list all tasks and give me a summary"
    print(f"\n  Query: {query}")

    result = await agent.process_message(query, max_turns=8)

    print(f"\n  RunResult:")
    print(f"    Turns taken: {result.turn_count}")
    print(f"    Termination reason: {result.termination_reason}")
    print(f"    History messages: {len(result.history)}")
    if result.total_usage:
        print(f"    Total tokens: {result.total_usage.total_tokens}")
    print(
        f"    Final message: {result.final_message.content[:150] if result.final_message and result.final_message.content else 'N/A'}..."
    )


async def section_4_grammar_modes(agent_dir: Path) -> None:
    """Section 4: Grammar Modes Comparison."""
    print("\n" + "=" * 70)
    print("Section 4: Grammar Modes Comparison")
    print("=" * 70)

    bundle = load_bundle(agent_dir)
    plugin = bundle.get_plugin()
    registry_config = GrailRegistryConfig(agents_dir=agent_dir, use_grail_check=False)
    registry = GrailRegistry(registry_config)
    backend_config = GrailBackendConfig(grail_dir=agent_dir)
    backend = GrailBackend(backend_config, externals_factory=build_externals)
    tool_source = RegistryBackendToolSource(registry=registry, backend=backend)

    tool_schemas = bundle.tool_schemas

    query = "Add a task 'Test grammar' with low priority"
    messages = bundle.build_initial_messages({"input": query})

    modes = [
        ("ebnf", GrammarConfig(mode="ebnf", send_tools_to_api=False)),
        ("structural_tag", GrammarConfig(mode="structural_tag")),
        ("json_schema", GrammarConfig(mode="json_schema")),
    ]

    for mode_name, grammar_config in modes:
        print(f"\n  --- Grammar mode: {mode_name} ---")

        obs = DemoObserver()
        kernel = AgentKernel(
            config=KernelConfig(
                base_url="http://remora-server:8000/v1",
                model="Qwen/Qwen3-4B-Instruct-2507-FP8",
                temperature=0.0,
                max_tokens=512,
            ),
            plugin=plugin,
            tool_source=tool_source,
            observer=obs,
            grammar_config=grammar_config,
        )

        step_result = await kernel.step(
            messages=messages,
            tools=tool_schemas,
            context={"state_dir": str(STATE_DIR), "agent_id": AGENT_ID},
        )

        tool_calls_str = "None"
        if step_result.tool_calls:
            tc = step_result.tool_calls[0]
            tool_calls_str = f"{tc.name}({tc.arguments})"

        print(f"    Tool calls: {tool_calls_str}")
        await kernel.close()

    backend.shutdown()


async def section_5_concurrent_tools(agent: WorkspaceAgent) -> None:
    """Section 5: Concurrent Tool Execution."""
    print("\n" + "=" * 70)
    print("Section 5: Concurrent Tool Execution")
    print("=" * 70)

    print(f"\n  ToolExecutionStrategy: concurrent (max_concurrency=10)")
    print(f"  Grammar config: allow_parallel_calls=True")

    query = "Add three tasks: 'Task A' with high priority, 'Task B' with low priority, 'Task C' with medium priority"
    print(f"\n  Query: {query}")

    result = await agent.process_message(query, max_turns=5)

    tool_call_events = [
        e for e in agent.demo_observer.events if e.get("type") == "tool_call"
    ]
    tool_result_events = [
        e for e in agent.demo_observer.events if e.get("type") == "tool_result"
    ]

    print(f"\n  Result:")
    print(f"    Turns: {result.turn_count}")
    print(f"    Total tool calls: {len(tool_call_events)}")
    print(f"    Total tool results: {len(tool_result_events)}")

    if len(tool_result_events) >= 3:
        timings = [e["event"].duration_ms for e in tool_result_events]
        print(f"    Individual timings: {timings}ms")
        print(f"    If sequential, would take ~{sum(timings)}ms total")
        print(f"    Concurrent execution overlaps these operations")


async def create_kernel_for_query(
    bundle_dir: Path,
    query: str,
    grammar_mode: str = "structural_tag",
) -> tuple[str, Any, float]:
    """Create a kernel and run a single query, return result with timing."""
    bundle = load_bundle(bundle_dir)
    registry_config = GrailRegistryConfig(agents_dir=bundle_dir, use_grail_check=False)
    registry = GrailRegistry(registry_config)
    backend_config = GrailBackendConfig(grail_dir=bundle_dir)
    backend = GrailBackend(backend_config, externals_factory=build_externals)
    tool_source = RegistryBackendToolSource(registry=registry, backend=backend)

    grammar_config = GrammarConfig(
        mode="structural_tag",
        allow_parallel_calls=False,
    )

    kernel = AgentKernel(
        config=KernelConfig(
            base_url="http://remora-server:8000/v1",
            model="Qwen/Qwen3-4B-Instruct-2507-FP8",
            temperature=0.0,
            max_tokens=256,
        ),
        plugin=bundle.get_plugin(),
        tool_source=tool_source,
        observer=NullObserver(),
        grammar_config=grammar_config,
    )

    messages = bundle.build_initial_messages({"input": query})

    start = time.monotonic()
    result = await kernel.step(
        messages=messages,
        tools=bundle.tool_schemas,
        context={"state_dir": str(STATE_DIR), "agent_id": AGENT_ID},
    )
    elapsed = time.monotonic() - start

    await kernel.close()
    backend.shutdown()

    return query, result, elapsed


async def section_6_batched_inference(bundle_dir: Path) -> None:
    """Section 6: Batched Async Inference."""
    print("\n" + "=" * 70)
    print("Section 6: Batched Async Inference")
    print("=" * 70)

    queries = [
        "Add task 'API redesign' with high priority",
        "Add task 'Update docs' with medium priority",
        "Add task 'Fix CI pipeline' with high priority",
    ]

    print(f"\n  Running {len(queries)} independent queries...")

    print(f"\n  [Sequential execution]")
    sequential_start = time.monotonic()
    sequential_results = []
    for q in queries:
        _, result, elapsed = await create_kernel_for_query(bundle_dir, q)
        sequential_results.append((q, result, elapsed))
    sequential_total = time.monotonic() - sequential_start

    for q, result, elapsed in sequential_results:
        tc_count = len(result.tool_calls) if result.tool_calls else 0
        print(f"    {q[:40]}... -> {tc_count} tools, {elapsed:.2f}s")
    print(f"    Total sequential: {sequential_total:.2f}s")

    print(f"\n  [Concurrent execution with asyncio.gather]")
    concurrent_start = time.monotonic()
    tasks = [create_kernel_for_query(bundle_dir, q) for q in queries]
    concurrent_results = await asyncio.gather(*tasks)
    concurrent_total = time.monotonic() - concurrent_start

    for q, result, elapsed in concurrent_results:
        tc_count = len(result.tool_calls) if result.tool_calls else 0
        print(f"    {q[:40]}... -> {tc_count} tools, {elapsed:.2f}s")
    print(f"    Total concurrent: {concurrent_total:.2f}s")

    speedup = sequential_total / concurrent_total if concurrent_total > 0 else 0
    print(f"\n  Speedup: {speedup:.2f}x")


async def section_7_error_handling(agent: WorkspaceAgent) -> None:
    """Section 7: Error Handling."""
    print("\n" + "=" * 70)
    print("Section 7: Error Handling")
    print("=" * 70)

    query = "Update the task 'nonexistent_task' to completed"
    print(f"\n  Query: {query}")

    result = await agent.process_message(query, max_turns=3)

    error_events = [
        e
        for e in agent.demo_observer.events
        if e.get("type") == "tool_result" and e["event"].is_error
    ]
    print(f"\n  Error events captured: {len(error_events)}")
    if error_events:
        print(f"    Error: {error_events[0]['event'].output_preview}")


async def section_8_summary(agent: WorkspaceAgent) -> None:
    """Section 8: Summary & Metrics."""
    print("\n" + "=" * 70)
    print("Section 8: Summary & Metrics")
    print("=" * 70)

    print(f"\n  Plugin: {agent.bundle.get_plugin().name}")
    print(f"  {agent.metrics_observer.summary()}")

    total_usage = agent.outbox[-1]["total_usage"] if agent.outbox else None
    if total_usage:
        print(f"  Total tokens used: {total_usage.total_tokens}")
        print(f"    Prompt tokens: {total_usage.prompt_tokens}")
        print(f"    Completion tokens: {total_usage.completion_tokens}")


async def section_9_plugin_swap(bundle_dir: Path) -> None:
    """Section 9: Swappable Model Plugins."""
    print("\n" + "=" * 70)
    print("Section 9: Swappable Model Plugins")
    print("=" * 70)

    registry = PluginRegistry()
    available_plugins = registry.list_plugins()

    print(f"\n  Available plugins: {available_plugins}")

    bundle = load_bundle(bundle_dir)
    tool_schemas = bundle.tool_schemas

    for plugin_name in available_plugins:
        plugin = registry.get(plugin_name)
        print(f"\n  --- Plugin: {plugin_name} ---")

        formatted_tools = plugin.format_tools(tool_schemas)
        tool_def = formatted_tools[0] if formatted_tools else {}
        print(f"    Tool format type: {tool_def.get('type', 'N/A')}")
        print(f"    Function call style: {str(tool_def.get('function', {}))[:80]}...")


async def section_10_registry_discovery(bundle_dir: Path) -> None:
    """Section 10: GrailRegistry Auto-Discovery."""
    print("\n" + "=" * 70)
    print("Section 10: GrailRegistry Auto-Discovery")
    print("=" * 70)

    print(f"\n  Registry config: agents_dir={bundle_dir}")

    registry_config = GrailRegistryConfig(
        agents_dir=bundle_dir,
        use_grail_check=False,
        cache_schemas=True,
    )
    registry = GrailRegistry(registry_config)

    discovered_tools = registry.list_tools()
    print(f"\n  Discovered tools: {discovered_tools}")

    for tool_name in discovered_tools:
        schema = registry.resolve(tool_name)
        if schema:
            print(f"\n  --- {tool_name} ---")
            print(f"    Description: {schema.description}")
            params = (
                schema.parameters.get("properties", {}) if schema.parameters else {}
            )
            print(f"    Parameters: {list(params.keys())}")


async def section_11_composite_observer(agent: WorkspaceAgent) -> None:
    """Section 11: CompositeObserver Demonstration."""
    print("\n" + "=" * 70)
    print("Section 11: CompositeObserver")
    print("=" * 70)

    print(f"\n  WorkspaceAgent uses CompositeObserver with:")
    print(f"    - DemoObserver: logs all events to console")
    print(f"    - MetricsObserver: collects timing metrics")

    print(f"\n  DemoObserver events captured: {len(agent.demo_observer.events)}")
    event_types = {}
    for e in agent.demo_observer.events:
        t = e.get("type", "unknown")
        event_types[t] = event_types.get(t, 0) + 1
    print(f"    Event breakdown: {event_types}")

    print(f"\n  MetricsObserver:")
    print(f"    {agent.metrics_observer.summary()}")


async def main() -> None:
    print("\n" + "=" * 70)
    print("Workspace Agent Demo: structured-agents Gold Standard")
    print("=" * 70)

    agent = WorkspaceAgent(AGENT_DIR)

    try:
        await section_1_bundle_loading(AGENT_DIR)
        await section_2_single_turn(agent)
        await section_3_multi_turn(agent)
        await section_4_grammar_modes(AGENT_DIR)
        await section_5_concurrent_tools(agent)
        await section_6_batched_inference(AGENT_DIR)
        await section_7_error_handling(agent)
        await section_8_summary(agent)
        await section_9_plugin_swap(AGENT_DIR)
        await section_10_registry_discovery(AGENT_DIR)
        await section_11_composite_observer(agent)

    finally:
        await agent.close()

    print("\n" + "=" * 70)
    print("Demo Complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run(main())
