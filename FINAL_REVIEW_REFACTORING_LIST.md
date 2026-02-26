# structured-agents v0.3.1 Final Review Refactoring List

Generated from `FINAL_REVIEW.md` (2026-02-26) to track the remaining work required to fully realize the v0.3.0 concept and ensure v0.3.1 is production quality.

## Priority P0: Blocking Production

1. **Wire the grammar pipeline or defer the dependency**
   - `ModelAdapter` currently receives `grammar_builder=None` and `kernel.step()` bypasses grammar when the builder is absent. Without the grammar pipeline, the library cannot guarantee schema-constrained tool calls, defeating v0.3.0's core differentiation. Either implement `ConstraintPipeline` (or equivalent) and pass an actual builder through `Agent.from_bundle()`, or drop the `xgrammar` extra and document the missing feature.

2. **Fix `demo_v03.py` to match the current API**
   - The demo still imports `ConstraintPipeline`, which does not exist, leaving the script broken. Update the demo to consume the real `Agent`/`ModelAdapter` API (remove the phantom import) and demonstrate the grammar-aware workflow once wired.

3. **Declare missing dependencies**
   - `pydantic` is heavily used for config and dataclass validation but not listed in `pyproject.toml`. Add it to `[project.dependencies]` so installs succeed and typing remains accurate.

## Priority P1: Pre-Release Hardening

4. **Add negative and edge-case tests**
   - Cover: tool execution failures, malformed API responses, max-turn exhaustion, invalid argument schemas, and other failure modes so regressions surface quickly.

5. **Test the XML tool-call parser**
   - `QwenResponseParser._parse_xml_tool_calls()` currently has zero test coverage. Flesh out tests for nested tags, escaping, and malformed XML so the parser regression-free.

6. **Create a real integration test suite**
   - Use `tests/fixtures/sample_bundle/` (and fix `load_manifest()` to read `initial_context.system_prompt`) to exercise actual bundle loading, manifest parsing, and kernel execution instead of only mocks.

7. **Strengthen assertions in existing tests**
   - Replace `assert is not None` with behavioral checks (events emitted, tool execution results, parsed tool calls) so tests fail when functionality breaks.

8. **Raise and handle custom exceptions**
   - The exception hierarchy in `src/structured_agents/exceptions.py` is defined but unused. Start raising `StructuredAgentsError`, `KernelError`, `ToolExecutionError`, etc., to add observability and consistent error-handling, especially around kernel steps and tool invocations.

## Priority P2: Quality Improvements

9. **Update documentation for v0.3.1**
   - `README.md`, `ARCHITECTURE.md`, and `demo_v03.py` still describe v0.3.0 features (`ConstraintPipeline`, `ComposedModelPlugin`, `AgentBundle`, etc.). Refresh prose to match the current 5-concept architecture, remove references to removed symbols, and highlight the grammar/system design actually implemented in v0.3.1.

10. **Clean up obsolete artifacts**
   - Archive `.analysis/` files, consolidate or remove `.refactor/` docs, and delete planning materials that no longer apply so the repo only contains active guidance.

11. **Address typing concerns**
   - Change `kernel.py:41` to accept `Sequence[Tool]` (or a covariant alternative) so `list[GrailTool]` passes type-checking. Once the grammar pipeline exists, replace `grammar_builder: Any` with a concrete constraint-builder protocol.

12. **Utilize existing fixtures**
   - Activate the unused fixtures in `tests/conftest.py` and `tests/fixtures/` (e.g., `sample_bundle/`, `grail_tools/`) or remove them to avoid dead code and provide real-world coverage.

13. **Trim redundant decorators in tests**
   - Remove redundant `@pytest.mark.asyncio` decorators where `asyncio_mode = "auto"` already handles async tests to reduce noise.
