# Documentation Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove legacy documentation and update the remaining docs so the library’s public docs are current, minimal, and production quality.

**Architecture:** Retain a small set of authoritative docs, delete stale planning/review artifacts, and update the retained docs to accurately describe the current API and grammar integration defaults (native tool calling by default, optional structured outputs via `ConstraintPipeline`).

**Tech Stack:** Markdown docs, vLLM OpenAI-compatible API semantics.

---

### Task 1: Inventory and delete legacy documentation

**Files:**
- Delete: `docs/plans/**` (except this plan), `.analysis/**`, `.refactor/**`, `FINAL_REVIEW*.md`, `CODE_REVIEW.md`, `V031_*`, `demo/overview.md`, `demo/WORKSPACE_AGENT_DEMO_IMPROVEMENT.md`

**Step 1: List files to delete**

Run: `git ls-files | rg "^(docs/plans/|\.analysis/|\.refactor/|FINAL_REVIEW|CODE_REVIEW|V031_|demo/overview.md|demo/WORKSPACE_AGENT_DEMO_IMPROVEMENT.md)"`
Expected: A list of legacy files that will be removed.

**Step 2: Remove legacy docs**

Run: `git rm <listed files>`
Expected: Files removed from the repo except `docs/plans/2026-02-26-docs-cleanup-plan.md`.

**Step 3: Verify remaining docs**

Run: `git status -sb`
Expected: Only intended deletions are staged.

**Step 4: Commit**

Run: `git add -u && git commit -m "docs: remove legacy documentation"`
Expected: Commit contains doc deletions only.

### Task 2: Update README for production accuracy

**Files:**
- Modify: `README.md`

**Step 1: Align high-level description**

Replace the outdated plugin/bundle references with the current API: `AgentKernel`, `ModelAdapter`, `DecodingConstraint`, `ConstraintPipeline`, native tool calling by default.

**Step 2: Update quickstart**

Provide a minimal example that uses the current `AgentKernel` + `ModelAdapter` + `build_client` flow, not deprecated plugin classes.

**Step 3: Update grammar section**

Document that grammar constraints are optional; `structured_outputs` are only sent when a `ConstraintPipeline` exists.

**Step 4: Run formatting check**

Manually review to keep examples concise and accurate.

**Step 5: Commit**

Run: `git add README.md && git commit -m "docs: refresh README for current API"`

### Task 3: Update ARCHITECTURE for current modules

**Files:**
- Modify: `ARCHITECTURE.md`

**Step 1: Update core modules**

Ensure the module list reflects `AgentKernel`, `ModelAdapter`, `LLMClient`, `ConstraintPipeline`, and `Tool` protocols.

**Step 2: Update data flow**

Reflect the new pipeline: formatted messages → client → tool calls → tool execution → history/events.

**Step 3: Update grammar section**

Document optional constraints and the `StructuredOutputModel` Pydantic baseclass.

**Step 4: Commit**

Run: `git add ARCHITECTURE.md && git commit -m "docs: align architecture guide"`

### Task 4: Update demo docs

**Files:**
- Modify: `demo/ultimate_demo/README.md`

**Step 1: Update grammar notes**

Explain the demo now defaults to native tool calling and only uses grammar constraints if configured.

**Step 2: Commit**

Run: `git add demo/ultimate_demo/README.md && git commit -m "docs: update ultimate demo README"`

### Task 5: Final review

**Step 1: Full doc scan**

Run: `rg "plugin|GrammarConfig|AgentBundle" README.md ARCHITECTURE.md demo/ultimate_demo/README.md`
Expected: No stale references.

**Step 2: Verify tests not required**

No tests required for doc-only updates.

**Step 3: Final commit**

Run: `git add -u && git commit -m "docs: cleanup and modernize"`

