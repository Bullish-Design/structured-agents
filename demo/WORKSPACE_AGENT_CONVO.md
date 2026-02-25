Conversation Summary
Project
structured-agents — a Python library for building LLM-powered agents with tool calling, Grail script execution, grammar-constrained decoding, and vLLM integration.
What Was Done
1. Reviewed the existing demo implementation plan (demo/DEMO_IMPLEMENTATION_PLAN.md) covering 11 steps from vLLM connectivity through full orchestration with Grail tools, chat agents, and tool-calling agents.
2. Created the WorkspaceAgent demo — a new demo showing a stateful agent with inbox/outbox, internal tools, and nested tool calls:
   - Grail scripts at demo/agents/workspace_agent/:
     - add_entry.pym — creates task entries as files in state/
     - update_entry.pym — modifies existing entries
     - list_entries.pym — lists/filters entries
     - summarize_state.pym — summarizes entries and emits a nested tool call
     - format_summary.pym — formats summaries (target of nested call)
   - State directory at demo/agents/workspace_agent/state/ — flat text files with key:value lines (no JSON parsing in Grail)
   - Orchestrator at demo/workspace_agent_demo.py — WorkspaceAgent class with Grail backend, externals factory, and Qwen3 LLM integration
3. Fixed multiple Grail/Monty compatibility issues:
   - Grail's Monty runtime forbids import os, import pathlib, with statements, and dict unpacking ({**data}). All scripts were rewritten to use @external functions (ensure_dir, write_file, read_file, list_dir, file_exists) declared in the .pym files and implemented in the Python orchestrator's build_externals() factory.
   - Fixed type annotation (list[str] → list[dict[str, str]]) in summarize_state.pym.
   - Fixed GrailBackendConfig vs GrailBackend — externals_factory belongs on GrailBackend.__init__(), not on the config dataclass.
   - Fixed build_externals signature to match (agent_id: str, context: dict[str, Any]) -> dict[...] as required by the backend.
   - The context dict must include "agent_id" for externals to be injected (line 240 in grail.py checks if externals_factory and agent_id).
4. Added Qwen3 vLLM integration — WorkspaceAgent.send_to_model() method that:
   - Takes plain text user messages
   - Formats them with QwenPlugin.format_messages() and format_tools()
   - Builds structural-tag grammar constraints via plugin.build_grammar(tools, GrammarConfig(mode="structural_tag"))
   - Sends to vLLM at http://remora-server:8000/v1 with tool_choice="auto"
   - Parses response via plugin.parse_response() to extract tool calls
   - Executes chosen tools via Grail backend
   - Demo now processes natural language queries like "Add a new task 'Review Q3 metrics' with high priority" → model selects add_entry tool automatically
5. Created documentation:
   - demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md — step-by-step plan for the workspace agent
What Is Currently Being Worked On
The user wants a comprehensive WORKSPACE_AGENT_DEMO_IMPROVEMENT.md report that:
1. Studies the full structured-agents library capabilities (including Grail, vLLM, xgrammar component libraries copied into .context/)
2. Audits what the current demo demonstrates vs. what it should demonstrate
3. Provides a step-by-step enhancement plan to make this the "ultimate demo" — a gold-standard reference for the library
Key Capabilities to Audit (from studying the codebase)
The report should cover whether the demo showcases:
- AgentKernel — the main orchestration loop (multi-turn tool calling with automatic re-prompting) — currently NOT used; the demo manually calls client.chat_completion instead
- Observer pattern — event logging/monitoring hooks — NOT demonstrated
- Grammar modes — EBNF, structural_tag, json_schema — only structural_tag is shown
- Concurrent tool execution — ToolExecutionStrategy with concurrent mode — NOT demonstrated
- Multi-turn conversations — tool result fed back to model for follow-up — NOT demonstrated (single-shot only)
- Context providers — .pym scripts that run before main tools to inject context — NOT demonstrated
- Bundle system — bundle.yaml for packaging tools/prompts — NOT demonstrated
- Swappable model plugins — plugin architecture supports different models — NOT demonstrated
- Token usage tracking — TokenUsage / StepResult — NOT captured
- Batched inference — vLLM's batched processing for async throughput — NOT demonstrated (sequential queries only)
- Error handling patterns — graceful tool errors, retry logic — minimal
- Message history management — stateful conversation across turns — NOT demonstrated (each query is independent)
Files Being Modified
- demo/workspace_agent_demo.py — main demo script
- demo/agents/workspace_agent/*.pym — Grail tool scripts
- demo/agents/workspace_agent/state/ — runtime state files
- demo/WORKSPACE_AGENT_DEMO_IMPLEMENTATION_PLAN.md — existing plan doc
- Next: demo/WORKSPACE_AGENT_DEMO_IMPROVEMENT.md — the comprehensive audit/improvement report to be created
Key Technical Constraints
- Grail Monty restrictions: No stdlib imports, no with statements, no dict unpacking, no classes. Only from grail import ... and from typing import .... File I/O must use @external async functions.
- vLLM server: http://remora-server:8000/v1, model Qwen/Qwen3-4B-Instruct-2507-FP8
- All tool functionality must use Grail .pym scripts, not direct Python calls
- State stored as plain text files in state/ subdirectory (Grail has no JSON parser)
Key Source Files to Reference
- src/structured_agents/backends/grail.py — GrailBackend, GrailBackendConfig, _run_grail_script
- src/structured_agents/plugins/qwen.py — QwenPlugin
- src/structured_agents/plugins/qwen_components.py — QwenResponseParser, QwenGrammarProvider
- src/structured_agents/grammar/builders/qwen3.py — Qwen3GrammarBuilder
- src/structured_agents/grammar/config.py — GrammarConfig
- src/structured_agents/client/factory.py — build_client
- src/structured_agents/types.py — KernelConfig, Message, ToolCall, ToolResult, ToolSchema, StepResult
- .context/HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md — definitive Grail script reference