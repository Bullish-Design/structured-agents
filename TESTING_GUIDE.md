# Testing Guide

This guide maps the refactor plan phases to **actual tests in the repo** and calls out **missing tests** that must be added. It also describes **real vLLM integration tests** that should run against a live vLLM server (not mocks).

## Prerequisites

- Python environment with `structured-agents` dependencies installed.
- vLLM server reachable (local or remote) with `xgrammar` enabled.
- Models available for FunctionGemma and Qwen (or compatible substitutes).
- `pytest` installed.

> **Important:** Real vLLM tests require a live vLLM endpoint. These should not be mocked.

## Environment Setup (Real vLLM)

```bash
export VLLM_BASE_URL="http://localhost:8000/v1"
export FUNCTION_GEMMA_MODEL="google/functiongemma-270m-it"
export QWEN_MODEL="Qwen/Qwen2.5-7B-Instruct"
```

Example local server:

```bash
vllm serve $FUNCTION_GEMMA_MODEL --host 0.0.0.0 --port 8000
```

## Current Test Inventory (Existing)

- Core APIs: `tests/test_public_api.py`
- Types: `tests/test_types.py`
- History strategies: `tests/test_history.py`
- Observer: `tests/test_observer/test_observer.py`
- Bundle loader: `tests/test_bundles/test_bundle_loader.py`
- Plugins: `tests/test_plugins/test_function_gemma.py`
- Backends: `tests/test_backends/test_python_backend.py`, `tests/test_backends/test_grail_backend.py`
- Kernel + integration (non‑vLLM): `tests/test_kernel.py`, `tests/test_integration.py`

## Phase 1: Core Grammar System

### Existing Coverage
- No dedicated grammar tests yet.

### Required Additions
Create **unit tests** for grammar artifacts and builders:
- `tests/test_grammar/test_artifacts.py`
- `tests/test_grammar/test_function_gemma_builder.py`

### Real vLLM Test (Required)
Add an integration test that exercises grammar constraints in a live vLLM server:
- `tests/test_vllm/test_grammar_acceptance.py`

Run (once added):
```bash
pytest tests/test_vllm/test_grammar_acceptance.py
```

## Phase 2: Tool Registry System

### Existing Coverage
- No registry tests yet.

### Required Additions
- `tests/test_registries/test_grail_registry.py`
- `tests/test_registries/test_python_registry.py`
- `tests/test_registries/test_composite_registry.py`

Run (once added):
```bash
pytest tests/test_registries
```

## Phase 3: Plugin System Update

### Existing Coverage
- `tests/test_plugins/test_function_gemma.py`

### Missing Coverage
- Qwen capability flags + `to_extra_body()` payloads.
- Structural tag handling end‑to‑end.

### Required Additions
- `tests/test_plugins/test_qwen_plugin.py`
- `tests/test_plugins/test_plugin_capabilities.py`

### Real vLLM Test (Required)
Add a live FunctionGemma call that verifies tool call parsing and constrained output:
- `tests/test_vllm/test_function_gemma_plugin.py`

Run (once added):
```bash
pytest tests/test_vllm/test_function_gemma_plugin.py
```

## Phase 4: Backend System Update

### Existing Coverage
- Python backend: `tests/test_backends/test_python_backend.py`
- Grail backend: `tests/test_backends/test_grail_backend.py`

### Missing Coverage
- Composite backend routing and snapshot passthrough.

### Required Additions
- `tests/test_backends/test_composite_backend.py`

Run:
```bash
pytest tests/test_backends
```

## Phase 5: Bundle System Update

### Existing Coverage
- `tests/test_bundles/test_bundle_loader.py`

### Missing Coverage
- Bundle grammar settings → `GrammarConfig` wiring.
- Registry resolution error paths (unknown registry/tool).

### Required Additions
- `tests/test_bundles/test_bundle_grammar_settings.py`
- Extend `tests/test_bundles/test_bundle_loader.py` for registry errors.

Run:
```bash
pytest tests/test_bundles
```

## Phase 6: Kernel Integration

### Existing Coverage
- Kernel flow: `tests/test_kernel.py`
- Non‑vLLM integration: `tests/test_integration.py`

### Missing Coverage
- Tool name resolution via registry in the kernel.
- Grammar config propagation from bundle → kernel.

### Required Additions
- `tests/test_kernel/test_kernel_registry_resolution.py`
- `tests/test_kernel/test_kernel_grammar_config.py`

### Real vLLM Test (Required)
Add an end‑to‑end live vLLM test to ensure structured outputs and tool execution:
- `tests/test_vllm/test_end_to_end.py`

Run (once added):
```bash
pytest tests/test_vllm/test_end_to_end.py
```

## Phase 7: MCP Registry (Optional)

### Existing Coverage
- None (not implemented).

### Future Tests (when MCP lands)
- `tests/test_mcp/test_mcp_registry.py`
- `tests/test_mcp/test_mcp_backend.py`

## Real vLLM Testing Notes

- These tests should always use a **live vLLM endpoint**.
- Avoid mocks for structured outputs or grammar constraints.
- For CI: run a vLLM service container and set `VLLM_BASE_URL`.
- Prefer smaller models for CI runtime constraints.
