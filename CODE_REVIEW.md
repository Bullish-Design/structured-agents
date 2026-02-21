# structured-agents Code Review

## Scope
- Reviewed architecture and design docs (`README.md:1`, `ARCHITECTURE.md:1`, `DEV_GUIDE.md:1`).
- Reviewed Grail/agent guides and FunctionGemma/XGrammar docs (`.context/HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md:1`, `.context/HOW_TO_CREATE_AN_AGENT.md:1`, `.context/CUSTOM_XGRAMMAR_GUIDE.md:1`, `.context/FUNCTIONGEMMA_DOCS.md:1`, `.context/FUNCTIONGEMMA_PROMPT_TIPS.md:1`).
- Inspected core runtime, plugin, backend, and bundle code paths (`src/structured_agents/kernel.py:42`, `src/structured_agents/plugins/protocol.py:10`, `src/structured_agents/backends/grail.py:41`, `src/structured_agents/bundles/loader.py:17`).

## Strengths
- Clear separation of concerns between kernel, plugins, and backends gives a clean extension surface (`src/structured_agents/kernel.py:42`, `src/structured_agents/plugins/protocol.py:10`, `src/structured_agents/backends/protocol.py:97`).
- Grail backend isolates tool execution and supports context providers and resource limits, matching the Grail workflow described in the `.pym` guide (`src/structured_agents/backends/grail.py:41`, `.context/HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md:102`).
- Bundle system provides a compact packaging story for prompts and tool schemas (`src/structured_agents/bundles/loader.py:17`, `src/structured_agents/bundles/schema.py:45`).
- Observer system and history strategies are minimal, typed, and easy to integrate (`src/structured_agents/observer/events.py:25`, `src/structured_agents/history.py:48`).

## Gaps vs. EBNF-First + Agent Goals
### Grammar/EBNF Strategy
- Grammar strategy is defined in the bundle schema but never consumed, so there is no runtime switch for EBNF vs JSON or custom grammars (`src/structured_agents/bundles/schema.py:33`).
- `FunctionGemmaPlugin.extra_body` omits the `type: "grammar"` field expected by the vLLM structured outputs payload, and tests assert a different legacy payload (`src/structured_agents/plugins/function_gemma.py:127`, `tests/test_plugins/test_function_gemma.py:75`, `.context/CUSTOM_XGRAMMAR_GUIDE.md:81`).
- The grammar builder does not escape tool names, while the reference grammar builder does (`src/structured_agents/plugins/grammar/function_gemma.py:25`, `.context/CUSTOM_XGRAMMAR_GUIDE.md:746`).
- Grammar supports only a single tool call; FunctionGemma is explicitly trained for parallel calls (`src/structured_agents/plugins/grammar/function_gemma.py:28`, `.context/FUNCTIONGEMMA_DOCS.md:46`).
- The grammar treats arguments as `[^}]` which prevents braces in arguments and blocks JSON-like payloads, making “JSON as secondary” difficult to implement without a new grammar strategy (`src/structured_agents/plugins/grammar/function_gemma.py:31`).

### FunctionGemma Protocol Alignment
- The message model does not support the `developer` role recommended for FunctionGemma prompting (`src/structured_agents/types.py:29`, `.context/FUNCTIONGEMMA_PROMPT_TIPS.md:25`).
- Tool responses are formatted using `tool_call_id`, but FunctionGemma guidance suggests name/response mappings instead of OpenAI’s `tool_call_id` format (`src/structured_agents/types.py:55`, `.context/FUNCTIONGEMMA_PROMPT_TIPS.md:79`).
- Tool call parsing uses `\w+` for tool names and a simplistic `key:value` parser that will break for hyphenated tool names or `<escape>`-wrapped strings (`src/structured_agents/plugins/function_gemma.py:30`, `src/structured_agents/plugins/function_gemma.py:98`, `.context/FUNCTIONGEMMA_DOCS.md:34`).

### Plugin/Backend Extensibility
- Bundle plugin selection is hard-coded to `function_gemma` and `qwen`, which blocks third-party plugins without modifying core code (`src/structured_agents/bundles/loader.py:39`).
- There is no first-class helper to derive tool schemas from Grail `.pym` `inputs.json`, even though the guides emphasize `grail check` as the schema source of truth (`src/structured_agents/bundles/loader.py:56`, `.context/HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md:84`).

### Test/Implementation Drift
- The FunctionGemma plugin test expects a `guided_grammar` payload that no longer matches the actual plugin implementation (`src/structured_agents/plugins/function_gemma.py:127`, `tests/test_plugins/test_function_gemma.py:75`).

## Recommendations (Expanded)
### 1) Implement a Grammar Strategy Abstraction
- **Option A: Bundle-level `grammar_strategy` + plugin hook**
  - **Implementation**: Extend `ModelPlugin.build_grammar()` to accept a `GrammarConfig` object (strategy enum + optional EBNF + JSON schema). Wire bundle loader to pass `manifest.model.grammar_strategy` into kernel/plugin (`src/structured_agents/plugins/protocol.py:53`, `src/structured_agents/bundles/schema.py:33`).
  - **Pros**: Keeps model-specific grammar logic in plugins; clean layering.
  - **Cons**: Requires API changes to plugin interface and kernel wiring.
  - **Implications**: Update tests and bundle schema docs; minor refactor cost.
- **Option B: Kernel-level grammar builder registry**
  - **Implementation**: Add a `GrammarBuilder` callable registry to `AgentKernel` or `KernelConfig`. Kernel picks builder based on config and passes it to plugin `extra_body()` (`src/structured_agents/kernel.py:42`, `src/structured_agents/plugins/protocol.py:80`).
  - **Pros**: Keeps plugin interface stable; enables app-level overrides.
  - **Cons**: More logic in kernel; weaker encapsulation.
  - **Implications**: Easier runtime swapping; less model-specific encapsulation.
- **Option C: Bundle computes grammar**
  - **Implementation**: Bundle loader computes grammar and stores it alongside bundle; kernel reads from bundle (`src/structured_agents/bundles/loader.py:17`).
  - **Pros**: Bundle is a self-contained deployment artifact.
  - **Cons**: Grammar tied to bundle; harder to swap per run.
  - **Implications**: Aligns with “bundle as product,” but less flexible.

### 2) Align Structured Outputs Payload with vLLM
- **Option A: Use vLLM’s documented `structured_outputs` payload**
  - **Implementation**: Emit `{"structured_outputs": {"type": "grammar", "grammar": grammar}}` and update tests (`src/structured_agents/plugins/function_gemma.py:127`, `tests/test_plugins/test_function_gemma.py:75`, `.context/CUSTOM_XGRAMMAR_GUIDE.md:81`).
  - **Pros**: Matches `.context` guidance; lowest integration risk.
  - **Cons**: Requires test updates for the new payload shape.
  - **Implications**: Improves correctness and clarity with vLLM.
- **Option B: Temporary dual payload (legacy + new)**
  - **Implementation**: Support a feature flag to emit both legacy `guided_grammar` and structured outputs.
  - **Pros**: Safer migration for existing users.
  - **Cons**: Adds complexity and ambiguous behavior.
  - **Implications**: Deprecate legacy once consumers update.

### 3) Expand FunctionGemma Grammar + Parser
- **Tool name escaping**
  - **Option A**: Escape tool names in grammar builder (`src/structured_agents/plugins/grammar/function_gemma.py:25`, `.context/CUSTOM_XGRAMMAR_GUIDE.md:746`).
    - **Pros**: Prevents invalid grammar for tool names with quotes/backslashes.
    - **Cons**: Slightly more logic.
    - **Implications**: Low-risk, improves robustness.
- **Multi-call grammar**
  - **Option A**: `root ::= function_call+` to allow multiple tool calls (`src/structured_agents/plugins/grammar/function_gemma.py:28`, `.context/FUNCTIONGEMMA_DOCS.md:46`).
    - **Pros**: Matches FunctionGemma parallel tool call capability.
    - **Cons**: Parser must support multiple calls reliably.
    - **Implications**: Update parsing logic and tests.
  - **Option B**: Feature flag (single vs multi call).
    - **Pros**: Safer for small models.
    - **Cons**: Adds config surface.
    - **Implications**: Optional default for stability.
- **Argument parsing + `<escape>` support**
  - **Option A**: Decode `<escape>...<escape>` and parse values accordingly.
    - **Pros**: Aligns with FunctionGemma spec; handles strings safely.
    - **Cons**: Adds custom parsing complexity.
    - **Implications**: Needed for correctness with string arguments.
  - **Option B**: Enforce JSON-like args with a stricter grammar.
    - **Pros**: Enables JSON as a secondary structured use case.
    - **Cons**: Grammar complexity can hurt small models.
    - **Implications**: Best as a selectable grammar strategy.

### 4) Add FunctionGemma-Compatible Message Roles
- **Option A: Add `developer` role to `Message`**
  - **Implementation**: Extend `Message.role` and allow it in formatting (`src/structured_agents/types.py:29`, `.context/FUNCTIONGEMMA_PROMPT_TIPS.md:25`).
  - **Pros**: Aligns with FunctionGemma prompt guidance; explicit.
  - **Cons**: Backward compatibility risk for consumers that assume current role set.
  - **Implications**: Update tests/examples; clarifies prompt semantics.
- **Option B: Plugin injects developer message**
  - **Implementation**: `FunctionGemmaPlugin.format_messages()` adds a default developer message when missing.
  - **Pros**: No core type changes.
  - **Cons**: Hidden behavior; harder to reason about message history.
  - **Implications**: Quick compatibility win, but less explicit.

### 5) Decouple Bundle Plugin Selection
- **Option A: Registry-based plugin loader**
  - **Implementation**: Add a `PluginRegistry` mapping names to classes and use it in bundle loader (`src/structured_agents/bundles/loader.py:39`).
  - **Pros**: Extensible without core edits.
  - **Cons**: Global registry lifecycle must be managed.
  - **Implications**: Lightweight path to third-party plugins.
- **Option B: Entry-point discovery**
  - **Implementation**: Discover plugins via package entry points.
  - **Pros**: Best for external ecosystem.
  - **Cons**: More complexity and packaging overhead.
  - **Implications**: Good long-term, heavier engineering upfront.
- **Option C: Bundle-specified plugin class path**
  - **Implementation**: Manifest includes `model.plugin_path`; loader dynamically imports.
  - **Pros**: No registry needed.
  - **Cons**: Dynamic import brittleness; weaker validation.
  - **Implications**: Flexibility at the cost of safety.

### 6) Introduce Grail Schema Ingestion
- **Option A: Add `GrailToolSchemaLoader` for `.grail/.../inputs.json`**
  - **Implementation**: Map `inputs.json` into `ToolSchema`, filtering system-injected inputs as in the guide (`src/structured_agents/bundles/loader.py:56`, `.context/HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md:84`).
  - **Pros**: Eliminates schema duplication; aligns with Grail workflow.
  - **Cons**: Requires `grail check` to have been run.
  - **Implications**: Add CI/dev tooling to generate `.grail` artifacts.
- **Option B: Load schemas directly via `grail.load()` at runtime**
  - **Pros**: No pre-generated files.
  - **Cons**: Adds runtime `grail` dependency and overhead.
  - **Implications**: Good for dev mode, optional for prod.
- **Option C: Keep manifest-owned schemas (current)**
  - **Pros**: Simpler loader.
  - **Cons**: Drift risk between `.pym` and schema.
  - **Implications**: Conflicts with Grail-first goals; not ideal long-term.

## Additional Architecture Updates (Post-Review)
Upon further review it was determined that the library was missing a key functionality provided by the xgrammar library - Structural Tags. This should be implemented in the library as core functionality. Also, the Grail scripts could be implemented in a more integrated manner as grail agents.
- **Grammar builder layer + structural tags opt-in**: introduce a `grammar/` module with `GrammarArtifact` + `GrammarStrategy` and allow structural-tag outputs for models that support them (fallback to EBNF when needed). This provides composable, model-specific grammar constraints without polluting the kernel.
- **Tool registry abstraction**: move Grail schema extraction into a dedicated `ToolRegistry` implementation and keep bundles as pure configuration; this decouples Grail from bundle parsing and enables additional registries later.
- **Minimal FunctionGemma demo**: add a small SHELLper-inspired Grail demo (pwd/ls/cd/cat/submit) with a short system prompt and no extra defaults, matching the distil-SHELLper tool format for easier evaluation (`.context/functiongemma_examples/distil-SHELLper-main/functions.md:1`).
- **Bundle config updates**: include explicit grammar strategy and registry bindings in bundle manifests to support structural tags and registry selection.

## Suggested Next Steps
- Implement the grammar builder layer and migrate plugins to the artifact interface.
- Add `ToolRegistry` + Grail registry and update bundle loading to resolve tools via registries.
- Add the minimal SHELLper-style Grail demo bundle as a sanity check for FunctionGemma behavior.
- Update FunctionGemma parsing and vLLM payload formatting to match structured outputs guidance.
