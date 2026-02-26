# Project Configuration Analysis

**Date:** 2026-02-26
**Version:** 0.3.1

---

## 1. pyproject.toml Analysis

### Current Dependencies
```toml
[project]
name = "structured-agents"
version = "0.3.1"
requires-python = ">=3.13"
dependencies = [
    "openai>=1.0",
    "pyyaml>=6.0",
    "grail",
]

[project.optional-dependencies]
grammar = ["xgrammar==0.1.29"]
vllm = ["vllm>=0.15.1"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

### Issues Found

#### 1.1 Version Mismatch
- **pyproject.toml claims:** `version = "0.3.1"`
- **README/ARCHITECTURE reference:** v0.3.0
- **demo_v03.py header:** "structured-agents v0.3.0 Demo"
- **Impact:** Documentation and code are inconsistent about the current version

#### 1.2 Missing Required Dependencies
The following are imported/used but not declared:
- **pydantic** - Used extensively for config classes (KernelConfig, etc.)
- **dataclasses** (stdlib, OK)
- **typing** extensions - Uses `Literal`, `Protocol`, etc.

#### 1.3 vLLM Optional Dependency Issue
- vLLM is listed as optional (`[vllm]` extra)
- However, the library is designed to work with vLLM/xgrammar
- The `[grammar]` extra pins `xgrammar==0.1.29` which may conflict with vLLM's internal xgrammar version
- **Recommendation:** Document version compatibility matrix

#### 1.4 Dead Dependencies
No dead dependencies detected in pyproject.toml itself, but:
- `grail` is sourced from Git (not PyPI) which could be fragile
- No version pinning for `grail` - could break on upstream changes

---

## 2. py.typed Marker

### Status: ✅ EXISTS

**Location:** `/home/andrew/Documents/Projects/structured-agents/src/structured_agents/py.typed`

The py.typed marker is present, indicating the package is typed and should be treated as such by type checkers.

**Verification:**
```bash
$ find /home/andrew/Documents/Projects/structured-agents -name "py.typed"
/home/andrew/Documents/Projects/structured-agents/src/structured_agents/py.typed
```

---

## 3. README.md and ARCHITECTURE.md Accuracy

### Version References

| File | Version Claimed | Actual Package Version | Status |
|------|----------------|----------------------|--------|
| README.md | v0.3.0 (implied) | 0.3.1 | ❌ Outdated |
| ARCHITECTURE.md | v0.3.0 (implied) | 0.3.1 | ❌ Outdated |
| demo_v03.py | v0.3.0 | 0.3.1 | ❌ Outdated |

### README.md Issues

#### 3.1 API Inconsistencies
The README documents APIs that may not exist or have changed:

**Documented but potentially incorrect:**
- `FunctionGemmaPlugin` - Not found in current exports
- `KernelConfig` - Referenced but verify location
- `ToolExecutionStrategy` - Referenced in docs
- `AgentBundle` / `load_bundle` - Referenced but verify

**Current exports (from `__init__.py`):**
```python
__all__ = [
    # Types
    "Message", "ToolCall", "ToolResult", "ToolSchema", "TokenUsage", "StepResult", "RunResult",
    # Tools
    "Tool", "GrailTool", "discover_tools",
    # Models
    "ModelAdapter", "ResponseParser", "QwenResponseParser",
    # Grammar
    "DecodingConstraint",
    # Events
    "Observer", "NullObserver", "Event",
    "KernelStartEvent", "KernelEndEvent", "ModelRequestEvent", "ModelResponseEvent",
    "ToolCallEvent", "ToolResultEvent", "TurnCompleteEvent",
    # Core
    "AgentKernel", "Agent", "AgentManifest", "load_manifest",
    # Client
    "LLMClient", "OpenAICompatibleClient", "build_client",
    # Exceptions
    "StructuredAgentsError", "KernelError", "ToolExecutionError", "BundleError", "AdapterError",
]
```

#### 3.2 Missing from README
- `ConstraintPipeline` - Mentioned in demo but doesn't exist in codebase
- `StepResult` - Exported but not documented
- `ResponseParser` - Exported but not documented

### ARCHITECTURE.md Issues

#### 3.3 Documented Features Not Implemented

**Grammar Pipeline:**
- ARCHITECTURE.md documents `ConstraintPipeline` extensively
- **Reality:** `ConstraintPipeline` does not exist in the codebase
- Only `DecodingConstraint` dataclass exists in `grammar/config.py`

**Plugin System:**
- Documents `ComposedModelPlugin`, `FunctionGemmaPlugin`, `QwenPlugin`
- **Reality:** Current architecture uses `ModelAdapter` dataclass, not plugin composition

**Bundles:**
- Documents `AgentBundle` and bundle system
- **Reality:** Only `AgentManifest` and `load_manifest` exist

#### 3.4 Outdated Architecture References

The ARCHITECTURE.md describes a 6-layer plugin system that has been flattened:
- Old: `MessageFormatter`, `ToolFormatter`, `ResponseParser`, `GrammarProvider`
- New: `ModelAdapter` dataclass with simpler interface

---

## 4. Demo Scripts Analysis

### demo_v03.py

**Status:** ❌ BROKEN

#### Critical Import Error
```python
from structured_agents import (
    # ...
    ConstraintPipeline,  # ❌ DOES NOT EXIST
    # ...
)
```

**Error:**
```
ImportError: cannot import name 'ConstraintPipeline' from 'structured_agents'
```

#### Other Import Issues
The demo imports these successfully:
- ✅ All types (Message, ToolCall, ToolResult, etc.)
- ✅ Tool classes (Tool, GrailTool)
- ✅ Model classes (ModelAdapter, QwenResponseParser)
- ✅ Events (all event types)
- ✅ Core classes (AgentKernel, Agent, AgentManifest)
- ✅ Client classes (LLMClient, OpenAICompatibleClient, build_client)

**Missing from demo that exists:**
- `discover_tools` - Exported but not used in demo
- `ResponseParser` - Exported but demo uses concrete `QwenResponseParser`
- `load_manifest` - Exported but not demonstrated

#### Demo Structure Issues
1. **Line 42:** Imports `ConstraintPipeline` which doesn't exist
2. **Lines 386-432:** `demo_grammar_pipeline()` function uses `ConstraintPipeline` 
3. **Lines 410:** Creates `ConstraintPipeline` instance

#### Fix Required
Either:
1. **Remove ConstraintPipeline** from demo and use `DecodingConstraint` directly
2. **Implement ConstraintPipeline** in the grammar module
3. **Update demo** to reflect actual v0.3.1 API

---

## 5. Stale Files to Clean

### 5.1 Cache Files
```
tests/__pycache__/          # Should be gitignored
src/structured_agents/grammar/__pycache__/  # Should be gitignored
```

### 5.2 Analysis/Review Files (Potentially Stale)
Located in `.analysis/`:
- `config_review.md` (13KB)
- `docs_demo_analysis.md` (19KB)
- `source_analysis.md` (30KB)
- `source_review.md` (21KB)
- `subsystems_analysis.md` (21KB)
- `test_config_analysis.md` (18KB)
- `test_review.md` (25KB)

**Recommendation:** Archive or remove if outdated

### 5.3 Refactoring Documentation (Likely Stale)
Located in `.refactor/`:
- `V031_DEVELOPER_GUIDE-STEP_1.md` through `STEP_7.md`
- `V031_DEVELOPER_GUIDE-STEP_1_rev1.md` through `STEP_7_rev1.md`

**Status:** These appear to be iterative drafts of refactoring guides
**Recommendation:** Consolidate into single document or archive

### 5.4 Root-level Planning Documents
- `V031_REFACTORING_GUIDE.md` (25KB)
- `V031_REFACTORING_PLAN.md` (9KB)
- `CODE_REVIEW.md` (17KB)

**Status:** May be outdated post-refactor
**Recommendation:** Review and archive if superseded

### 5.5 Hidden/Worktree Directories
```
.hidden/                    # Contains old development branches
.worktrees/                 # Git worktrees
```

### 5.6 Demo Tools Directory
```
demo_tools/                 # Contains .pym files for demo
```
**Status:** Active (used by demo_v03.py)

---

## 6. Summary of Critical Issues

### 🔴 High Priority
1. **demo_v03.py is broken** - Imports non-existent `ConstraintPipeline`
2. **Version inconsistency** - Documentation says 0.3.0, package is 0.3.1
3. **ARCHITECTURE.md documents non-existent features** - ConstraintPipeline, old plugin system

### 🟡 Medium Priority
4. **README.md API examples may be outdated** - References classes that may not exist
5. **Stale analysis files** - Taking up space, may confuse new developers
6. **Missing pydantic dependency** - Used but not declared in pyproject.toml

### 🟢 Low Priority
7. **Cache files not gitignored** - Minor cleanup
8. **Refactoring docs** - Archive after confirming completion

---

## 7. Recommendations

### Immediate Actions
1. Fix `demo_v03.py` - Remove `ConstraintPipeline` imports and usage
2. Update version references in README.md and ARCHITECTURE.md to 0.3.1
3. Add `pydantic` to dependencies in pyproject.toml

### Short-term
4. Audit README.md code examples against actual exports
5. Update ARCHITECTURE.md to reflect current (flattened) architecture
6. Archive or remove stale analysis files in `.analysis/`

### Long-term
7. Consider consolidating refactoring documentation
8. Add integration test for demo scripts to catch breakage
9. Document vLLM/xgrammar version compatibility matrix
