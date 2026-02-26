# Grammar Pipeline Quick Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up the grammar pipeline so tooling works with vLLM structural tags, fix the demo to the current API, and declare the missing `pydantic` dependency.

**Architecture:** Use a `ConstraintPipeline` that emits vLLM-structured tag constraints via xgrammar and attach it to `ModelAdapter`; the kernel will pass the generated constraint via `extra_body` while `Agent.from_bundle` builds the pipeline automatically. The demo now exercises grammar-aware tool calling without manual pipeline wiring.

**Tech Stack:** Python 3.12+, pytest, vLLM, xgrammar (via `.context/xgrammar-0.1.29`), grail, pydantic.

---

### Task 1: Add ConstraintPipeline and structural-tag builder

**Files:**
- Create: `src/structured_agents/grammar/pipeline.py`
- Update: `src/structured_agents/grammar/__init__.py`
- Create: `tests/test_grammar/test_pipeline.py`

**Step 1: Write the failing test**
- Define tests for `DecodingConstraint` defaults and pipeline returning `None` when no tools.
- Include a helper that ensures the pipeline invokes the builder and returns `None` when the builder yields `None`.

**Step 2: Run the test to confirm it fails**
- `pytest tests/test_grammar/test_pipeline.py -k pipeline -v`
- Expect: Module/class not found.

**Step 3: Implement `ConstraintPipeline` and default builder**
- Implement `ConstraintPipeline` with a builder callable and `constrain()` returning `extra_body`.
- Add a `build_structural_tag()` helper that uses `.context/xgrammar-0.1.29/python/xgrammar/structural_tag.py` (TagFormat, StructuralTag, TriggeredTagsFormat, QwenXMLParameterFormat).
- Export `DecodingConstraint` and `ConstraintPipeline` from `grammar/__init__.py`.

**Step 4: Run the test to verify it passes**
- `pytest tests/test_grammar/test_pipeline.py -k pipeline -v`
- Expect: PASS.

### Task 2: Integrate grammar pipeline into the core stack

**Files:**
- Update: `src/structured_agents/models/adapter.py`
- Update: `src/structured_agents/kernel.py`
- Update: `src/structured_agents/agent.py`
- Update: `tests/test_models/test_adapter.py`
- Update: `tests/test_kernel/test_basic.py`
- Update: `tests/test_integration/test_full_agent.py`

**Step 1: Update adapters**
- Replace `grammar_builder` with `constraint_pipeline: ConstraintPipeline | None` and `grammar_config` semantics in `ModelAdapter`.
- Ensure default formatters remain intact.

**Step 2: Update kernel**
- Change `tools` annotation to `Sequence[Tool]`.
- In `step()`, use `constraint = self.adapter.constraint_pipeline.constrain(resolved_tools)` when pipeline exists.
- Pass `extra_body=constraint` to client.

**Step 3: Update `Agent.from_bundle`**
- Instantiate the default structural-tag builder pipeline when `manifest.grammar_config` is provided (or fallback to default builder with no config).
- Pass `constraint_pipeline` into `ModelAdapter`.

**Step 4: Update tests**
- Adjust adapter tests to assert `constraint_pipeline` instead of `grammar_builder`.
- Update kernel/integration tests to provide pipeline or `None` as needed.

**Step 5: Run relevant test suite**
- `pytest tests/test_models/test_adapter.py tests/test_kernel/test_basic.py tests/test_integration/test_full_agent.py -k pipeline -v`
- Expect: PASS.

### Task 3: Update demo and dependencies

**Files:**
- Update: `demo_v03.py`
- Update: `pyproject.toml`

**Step 1: Update the demo**
- Remove the obsolete `ConstraintPipeline` import if the demo no longer instantiates it directly.
- Use the new adapter/pipeline fields so the demo showcases structural-tag grammar without manual wiring (e.g., rely on default builder or print when constraint emitted).

**Step 2: Declare `pydantic` dependency**
- Add `pydantic>=2.5` (matching `.context`) under `[project.dependencies]` in `pyproject.toml`.

**Step 3: Run linting/tests relevant to these files**
- `pytest demo_v03.py -k` not necessary, but ensure `python -m compileall demo_v03.py` passes.

**Step 4: Confirm dependency tree**
- Mention `pyproject.toml` update ensures `pydantic` installed (no commands beyond edit).

---

Plan complete and saved to `docs/plans/2026-02-26-grammar-pipeline-design.md`. Two execution options:

1. **Subagent-Driven (this session)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** - Open a new session with `executing-plans`, batch execution with checkpoints.

Which approach would you prefer for executing this plan?