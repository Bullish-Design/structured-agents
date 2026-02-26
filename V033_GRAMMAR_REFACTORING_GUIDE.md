# V0.3.3 Grammar Refactoring Guide

This guide provides a detailed, junior-friendly, step-by-step plan to refactor `structured-agents` grammar integration in line with the v0.3.x ethos: **native tool calling by default**, **explicit opt-in constraints**, **minimal complexity**, and **deterministic behavior**. Each phase includes explicit files to touch, example snippets, expected outcomes, and validation guidance. An appendix covers the `ultimate_demo` refactor.

The guidance is aligned to vLLM’s documented structured outputs and OpenAI-compatible server usage: `structured_outputs` must be passed via `extra_body`, with JSON schema constraints placed under `structured_outputs.json`.

## Pre-Flight Checklist

1. Read `GRAMMAR_INTEGRATION_REPORT.md` to understand the architectural direction and failure analysis.
2. Review vLLM structured output docs:
   - `docs/features/structured_outputs.md` for `structured_outputs` usage and JSON schema examples.
   - `docs/serving/openai_compatible_server.md` for `extra_body` usage and tool calling expectations.
3. Skim current grammar code:
   - `src/structured_agents/grammar/config.py`
   - `src/structured_agents/grammar/pipeline.py`
   - `src/structured_agents/agent.py`
   - `src/structured_agents/kernel.py`

## Phase 1: Core API Semantics (Make Grammar Optional)

### Goal
Ensure native tool calling is the default path. Grammar constraints must be explicit and optional.

### Steps

1. **Audit current defaults**
   - **File(s):** `src/structured_agents/grammar/config.py`
   - **What to check:** The `DecodingConstraint` dataclass currently defaults `strategy="ebnf"`.
   - **Desired outcome:** No default implies grammar usage. The presence of a `DecodingConstraint` should be the *only* signal to enable constraints.

2. **Make grammar optional in manifests**
   - **File(s):** `src/structured_agents/agent.py`
   - **What to edit:** Ensure `load_manifest()` only creates `DecodingConstraint` when a `grammar` section exists in `bundle.yaml`.
   - **Example check:** If `grammar` is missing, `grammar_config` should remain `None`.
   - **Expected outcome:** Bundles without grammar config run with native tool calling only.

3. **Keep pipeline wiring explicit**
   - **File(s):** `src/structured_agents/agent.py`
   - **What to edit:** In `Agent.from_bundle`, only create `ConstraintPipeline` when `manifest.grammar_config` is not `None`.
   - **Expected outcome:** `constraint_pipeline` is `None` by default.

### Validation (General)
- Add a unit test verifying `grammar_config` defaults to `None` when `grammar` is absent in a bundle.
- Add a unit test confirming `constraint_pipeline` remains `None` when no grammar config is provided.

## Phase 2: Constraint Pipeline Refactor (Pydantic JSON Schema Only, Explicit)

### Goal
Make the pipeline produce `structured_outputs` only for explicitly requested constraint strategies. Prefer JSON schema constraints derived from a Pydantic base model over structural tags.

### vLLM Alignment Notes
- vLLM expects structured outputs via `extra_body={"structured_outputs": {...}}`.
- JSON schema constraints use the `json` key: `{"structured_outputs": {"json": <schema>}}`.
- This matches `docs/features/structured_outputs.md` in the vLLM sources.

### Steps

1. **Introduce a Pydantic baseclass for JSON schema constraints**
   - **File(s):** add `src/structured_agents/grammar/models.py` (or similar)
   - **What to add:**
     ```python
     from pydantic import BaseModel

     class StructuredOutputModel(BaseModel):
         """Baseclass for JSON schema structured outputs."""
     ```
   - **Expected outcome:** JSON schema constraints are derived from a single, consistent baseclass.

2. **Define how JSON schema constraints are supplied**
   - **Decision:** choose a consistent API for attaching a `StructuredOutputModel` to a tool or request.
   - **Typical pattern:** store a model class on `DecodingConstraint` or pass it to the pipeline builder.
   - **Example approach:** add `schema_model: type[StructuredOutputModel] | None` to `DecodingConstraint`.

3. **Add a JSON schema constraint builder**
   - **File(s):** `src/structured_agents/grammar/pipeline.py`
   - **What to add:** `build_json_schema_constraint()`
   - **Core logic:**
     ```python
     schema = schema_model.model_json_schema()
     return {"structured_outputs": {"json": schema}}
     ```
   - **Expected outcome:** JSON schema constraints map directly to vLLM’s `structured_outputs.json`.

4. **Gate structural tags explicitly**
   - **File(s):** `src/structured_agents/grammar/pipeline.py`
   - **What to edit:** ensure `build_structural_tag_constraint` runs **only** if `strategy == "structural_tag"`.
   - **Expected outcome:** no structural tag payloads unless explicitly requested.

5. **Reject unsupported schema features**
   - **File(s):** `src/structured_agents/grammar/pipeline.py` (or new `validation.py`)
   - **What to add:** schema validation before returning the payload.
   - **Behavior:** if unsupported features are detected, raise a clear exception (no fallback).
   - **Expected outcome:** deterministic failure when schema can’t be compiled by xgrammar/vLLM.

6. **Update pipeline wiring**
   - **File(s):** any builder selection logic (pipeline, agent, adapters)
   - **What to edit:** choose the correct builder based on `DecodingConstraint.strategy`.
   - **Expected outcome:** `json_schema` uses the JSON schema builder, `structural_tag` uses the structural tag builder, others return `None`.

### Validation (General)
- Unit test: `StructuredOutputModel.model_json_schema()` returns the expected JSON structure.
- Unit test: `build_json_schema_constraint` returns `{"structured_outputs": {"json": ...}}`.
- Unit test: invalid schema features raise a deterministic error.

## Phase 3: Adapter + Response Parsing Alignment

### Goal
Ensure the runtime path prefers vLLM tool calling (`tool_calls`) and only uses grammar constraints when explicitly enabled.

### Steps

1. **Confirm tool calls are primary**
   - **File(s):** `src/structured_agents/models/parsers.py`
   - **What to check:** `QwenResponseParser.parse` should parse `tool_calls` first.
   - **Expected outcome:** content-based parsing is fallback only.

2. **Confirm kernel uses extra_body only when needed**
   - **File(s):** `src/structured_agents/kernel.py`
   - **What to check:** `extra_body` should be `None` unless `constraint_pipeline` exists and returns a payload.
   - **Expected outcome:** native tool calling remains the default.

3. **Confirm tool schemas are still sent**
   - **File(s):** `src/structured_agents/kernel.py`, `src/structured_agents/models/adapter.py`
   - **What to check:** `tools` are sent whenever available, regardless of grammar config.
   - **Expected outcome:** vLLM can use its tool parser without grammar constraints.

### Validation (General)
- Unit test: parser handles `tool_calls` properly and skips XML parsing when `tool_calls` exist.
- Unit test: `extra_body` is `None` when `constraint_pipeline` is missing.

## Phase 4: Test and Validation Pass

### Goal
Provide a robust suite that verifies behavior and prevents regressions.

### Steps

1. **Core defaults**
   - Tests confirm the default run path uses no grammar constraints.

2. **Constraint builders**
   - Tests confirm JSON schema builder output shape.
   - Tests confirm structural tags are gated by explicit config.

3. **vLLM API compatibility**
   - Tests verify `structured_outputs` payload keys match vLLM docs (`json`, `structural_tag`).
   - Tests ensure JSON schema payloads are **not** nested under deprecated keys.

### Validation (General)
- Run the updated unit test suite and ensure all new tests pass.

## Phase 5: Documentation Update Notes

### Goal
Keep project documentation aligned with the new semantics.

### Steps

1. **Update library docs (if present)**
   - Document that native tool calling is the default.
   - Mark grammar constraints as explicit opt-in.

2. **Reference vLLM behavior explicitly**
   - Note that `structured_outputs` must be sent via `extra_body` in OpenAI-compatible calls.
   - Document JSON schema format expectations consistent with vLLM’s `structured_outputs.json` API.

### Validation (General)
- Manual review to ensure the docs match vLLM’s terminology and parameters.

## Appendix: Ultimate Demo Refactor Steps

### Goal
Align the demo with the new default path (native tool calling).

### Steps

1. **Config updates**
   - **File(s):** `demo/ultimate_demo/config.py`
   - **What to change:** set `GRAMMAR_CONFIG = None` by default.
   - **Expected outcome:** native tool calling is used by default.

2. **Coordinator kernel**
   - **File(s):** `demo/ultimate_demo/coordinator.py`
   - **What to change:** remove `DISABLE_GRAMMAR` branching, and only create a `ConstraintPipeline` if `GRAMMAR_CONFIG` is not `None`.
   - **Expected outcome:** demo uses `constraint_pipeline=None` by default.

3. **Subagent kernels**
   - **File(s):** `demo/ultimate_demo/subagents.py`
   - **What to change:** same pattern as the coordinator. Only use grammar when explicitly provided.
   - **Expected outcome:** subagents run with native tool calling by default.

4. **Optional experimental grammar path**
   - If you want to keep a demo toggle for grammar, expose it as an explicit opt-in with warnings in the README.

### Validation (General)
- Run the demo and confirm tool calls are extracted via vLLM tool parsing.
- Confirm no `structured_outputs` payload is sent unless `GRAMMAR_CONFIG` is set.
