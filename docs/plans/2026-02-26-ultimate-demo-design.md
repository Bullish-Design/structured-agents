# Ultimate Demo Package Design

## Summary

Create a multi-module demo package under `demo/ultimate_demo/` that showcases structured-agents in a real-world project-coordinator scenario. The demo uses a genuine vLLM-backed LLM call with structural-tag grammar constraints, maintains inbox/outbox state, routes work through subagents, and produces a final state summary.

## Goals

- Demonstrate end-to-end agent execution with real vLLM calls.
- Use grammar-constrained decoding via XGrammar structural tags.
- Show an inbox/outbox workflow driven by natural language inputs.
- Include subagents as tools with their own toolsets.
- Maintain and summarize internal state across multiple turns.
- Provide clean, readable, modular code for reference usage.

## Non-Goals

- Not a reusable framework or library abstraction.
- No new production APIs or changes to core library.
- No test suite additions for the demo (unless required by existing patterns).

## Architecture

### Module Layout

- `demo/ultimate_demo/__init__.py`: package marker + helpful exports.
- `demo/ultimate_demo/config.py`: constants for model/server settings and grammar config.
- `demo/ultimate_demo/state.py`: typed agent state dataclasses (inbox, outbox, tasks, risks, logs).
- `demo/ultimate_demo/tools.py`: concrete tools (e.g., task tracking, risk logging, status updates).
- `demo/ultimate_demo/subagents.py`: subagent tool wrappers; each subagent runs its own kernel.
- `demo/ultimate_demo/observer.py`: observer that prints or captures events for the demo.
- `demo/ultimate_demo/coordinator.py`: project-coordinator agent assembly and orchestration.
- `demo/ultimate_demo/runner.py`: runnable demo entrypoint that feeds inbox messages.

### Agent Flow

1. Runner seeds inbox with natural language requests.
2. Coordinator builds AgentKernel + ModelAdapter with ConstraintPipeline and QwenResponseParser.
3. Agent processes inbox, triggers tools/subagents, writes state updates, and emits events.
4. Outbox receives user-facing responses and final summary.

### Grammar-Constrained Decoding

- Use `DecodingConstraint(strategy="structural_tag", allow_parallel_calls=True, send_tools_to_api=False)`.
- Build constraint payload via `ConstraintPipeline(build_structural_tag_constraint, config)`.
- Pass `extra_body` to vLLM via the standard client (already supported by kernel).

### Subagents

- Implement subagents as Tool classes that execute their own mini AgentKernel.
- Subagents have their own tool schemas (e.g., schedule analysis, risk reviewer).
- The coordinator invokes subagent tools to fill gaps: schedule impact, risk assessment, or status drafting.

### State Management

- Maintain a dataclass state containing:
  - `inbox`: list of user messages.
  - `outbox`: list of responses.
  - `tasks`: structured list of project tasks with status.
  - `risks`: list of identified risks + mitigations.
  - `updates`: stakeholder updates and decisions.
  - `tool_log`: record of tool usage for final summary.
- Tools update state deterministically with clear outputs.

### Demo Script Outline

- Initialize state with a project kickoff summary.
- Feed 3-4 inbox messages: scope change, timeline pressure, and stakeholder check-in.
- Agent processes each message via `AgentKernel.run` (multi-turn).
- After final message, print the internal state summary and outbox transcript.

## Error Handling

- Use existing error handling in `AgentKernel` (KernelError for model failures).
- Tool errors are surfaced in `ToolResult.is_error` and logged to state.

## Validation

- Manual run: `python -m demo.ultimate_demo.runner`.
- vLLM server must be running at `http://remora-server:8000/v1` with the specified Qwen3 model.

## Open Questions

- None. Configuration is fixed to the provided server and model.