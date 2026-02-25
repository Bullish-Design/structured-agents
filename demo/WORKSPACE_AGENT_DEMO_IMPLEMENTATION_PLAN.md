# Workspace Agent Demo Implementation Plan

## Goal
Create a Grail-driven `WorkspaceAgent` demo that exposes an inbox, an outbox, and an internal metadata state map (tasks/notes/priorities). The agent will coordinate dedicated Grail tools that mutate the metadata and optionally invoke other structured agent tools themselves, then summarize activity in the outbox.

## Scope
1. Build a standalone workspace-agent tool set under `demo/agents/workspace_agent` containing Grail `.pym` scripts (no direct Python helpers). These scripts will:
   - Add, update, and list metadata entries.
   - Manage simple priorities/status for tasks.
   - Perform nested tool calls (e.g., a summarizer that invokes another structured agent tool).
2. Implement a Python orchestration harness (`demo/workspace_agent_demo.py`) that uses `structured_agents` primitives to:
   - Maintain `inbox`/`outbox` structures.
   - Call Grail scripts via the Grail backend to manipulate internal metadata state.
   - Route responses back through the outbox, including tool-call logs.
3. Provide a small scenario demonstrating:
   - Ingesting multiple inbox messages.
   - Updating state via tools, including an example where a Grail script triggers another tool call (e.g., summarizer calling a nested doc tool).
   - Emitting structured outbox entries that show the updated metadata and tool call results.
4. Document the expected flow and verification steps inside this plan for future maintenance.

## Step-by-step Plan
1. **Set up workspace agent Grail scripts**
   - Create `demo/agents/workspace_agent/` directory and within it a `state/` subdirectory for storing plain text or basic JSON state files (Grail has no JSON parser).
   - Add scripts: `add_entry.pym`, `update_entry.pym`, `list_entries.pym`, `summarize_state.pym`, and optionally `format_summary.pym` to support nested calls.
   - Ensure scripts read inputs via `grail.Input`, load or persist state by reading/writing the files in `state/`, and one script shows calling another tool (e.g., `summarize_state` collects entries then triggers a nested Grail tool `agents/workspace_agent/format_summary.pym`).
2. **Verify Grail schemas**
   - Define `ToolSchema` objects for each script in the demo harness, matching the JSON schema expected by the scripts.
   - Write helper functions to load the schemas (using `structured_agents.ToolSchema`).
3. **Implement Python orchestrator (`workspace_agent_demo.py`)**
   - Initialize `KernelConfig`, `GrailBackend`, and maintain `inbox`/`outbox` (maybe simple dictionaries/lists).
   - Create a simple input loop that reads predefined inbox messages (e.g., add task, prioritize note, request summary).
   - For each message, select the Grail tool (via schema) and execute a `ToolCall`, capturing the result and updating the workspace metadata files under `state/` (e.g., writing updated task files or a shared state file from the Grail scripts).
   - Log each execution to the outbox, including nested tool call details when they occur.
4. **Demonstrate internal state updates**
   - After each tool invocation, ensure the Grail script has updated the workspace state files (e.g., task entries with status/priority/note) and report the relevant changes.
   - Provide a final outbox entry summarizing the entire workspace state.
5. **Document expected outputs**
   - Within the plan, list sample inbox entries and the intended outbox summary (e.g., `Task "Write plan" priority high; note recorded`).
6. **Add verification instructions**
   - State how to run the demo harness and what to expect in console output, emphasizing the nested tool-call example.
   - Mention Grail tooling requirements (Grail backend config) to ensure this is reproducible.

## Dependencies
- Existing `structured_agents` tooling.
- Grail backend pointing at `demo/agents/workspace_agent/` scripts.

## Next Steps (After Plan Approval)
- Implement Grail scripts, test schemas.
- Build orchestrator Python harness using the plan’s scenario.
- Validate nested tool-call behavior and state updates.
- Document outputs or troubleshooting notes if any issues arise.
