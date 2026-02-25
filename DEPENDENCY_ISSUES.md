# Dependency Issues

## grail library issues

### Issue 1: Input default "None" treated as required

**Severity:** High - blocks demo execution

**Location:** `.context/grail/src/grail/parser.py:246`

**Description:** When a .pym script uses `Input("name", default="None")` (the string "None"), grail incorrectly treats the input as required because:
1. `ast.literal_eval("None")` returns Python's `None`
2. The check `required=default is None` evaluates to `True`

**Affected files:**
- `agents/shellper_demo/echo.pym` - uses `Input("file_name", default="None")`

**Expected behavior:** Any explicit default value (including "None" string) should make the input optional (required=False).

**Suggested fix:** Change the logic to track whether a default was explicitly provided, rather than checking if the default value is Python's None. For example:
```python
# Instead of:
default = None
for keyword in node.value.keywords:
    if keyword.arg == "default":
        default = ast.literal_eval(keyword.value)
        break

# Use a flag:
has_default = False
default = None
for keyword in node.value.keywords:
    if keyword.arg == "default":
        has_default = True
        default = ast.literal_eval(keyword.value)
        break

required = not has_default
```

**Workaround for demo:** Modify echo.pym to use a different default value or no default.

---

### Issue 2: grail library not installed (RESOLVED)

**Status:** RESOLVED - grail is installed via git dependency in pyproject.toml

---

### Issue 3: HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md missing installation instructions

**Severity:** Low - documentation gap

**Location:** `.context/HOW_TO_CREATE_A_GRAIL_PYM_SCRIPT.md`

**Description:** The HOW_TO document explains how to write .pym scripts but doesn't explain how to install or run the grail tool itself (for `grail check` command).

**Suggested fix:** Add an "Installation" or "Setup" section.

---

### Issue 4: shellper_demo .pym files use default="None" causing parser bug

**Severity:** High - blocks shellper_demo tool execution

**Location:** `agents/shellper_demo/*.pym` (multiple files)

**Description:** Several shellper_demo tools use `Input("name", default="None")` which triggers the parser bug described in Issue 1. These files include:
- `echo.pym` - uses `Input("file_name", default="None")`
- Likely others with similar pattern

**Suggested fix:** Either:
1. Fix the grail parser as described in Issue 1
2. Or modify the .pym files to use a different default value (e.g., empty string) instead of "None"
