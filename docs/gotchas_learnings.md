# Gotchas & Learnings — Inspect AI Implementation

Unexpected findings, API surprises, and non-obvious behaviour encountered while
building this project. Intended to save future-us from re-discovering the same things.

---

## 1. `ToolDef.parameters` must be `ToolParams`, not a plain dict

**Affected file:** `src/ha_voice_bench/tools.py`

### What the docs/intuition suggest

`ToolDef` accepts a `parameters` argument typed as `dict[str, str] | ToolParams | None`.
The dict form looks like it should be the easy path — just describe your parameters inline.

### What actually happens

`ToolDef.__init__` branches on `isinstance(parameters, ToolParams)`. If `parameters` is
anything other than a `ToolParams` instance (including a plain dict, `{}`, or `None`), it
always calls `parse_tool_info(tool)` to introspect the callable's signature and docstring.

For a dummy handler like `async def _noop(**kwargs)` this goes wrong in two ways:

- **Non-empty dict** → `apply_description_overrides()` checks that every key in your dict
  exists as a named parameter in the introspected signature. `**kwargs` produces no named
  parameters, so every key fails: `ValueError: 'name' is not a valid parameter for the
  target function`.

- **`{}` or `None`** (falsy) → skips `apply_description_overrides`, falls through to
  `self.parameters = tool_info.parameters` — the result of introspecting `_noop`. Because
  `**kwargs` is itself a parameter in Python's signature model, it leaks into the schema as
  a property named `kwargs`. The model receives a spurious `kwargs` parameter in every tool
  definition, silently, with no error.

### The fix

Pass a `ToolParams` instance. When `name`, `description`, **and** a `ToolParams` are all
provided, `ToolDef.__init__` short-circuits entirely — no introspection, no leakage:

```python
from inspect_ai.tool import ToolDef
from inspect_ai.tool._tool_params import ToolParams
from inspect_ai.util._json import JSONSchema

# Tools with parameters:
HASS_TURN_ON = ToolDef(
    tool=_noop,
    name="HassTurnOn",
    description="Turns on/opens a device or entity",
    parameters=ToolParams(
        properties={
            "name": JSONSchema(type="string", description="Name of the entity"),
            ...
        }
    ),
)

# Zero-parameter tools — ToolParams(), NOT {}:
HASS_NEVERMIND = ToolDef(
    tool=_noop,
    name="HassNevermind",
    description="Cancels the current request",
    parameters=ToolParams(),
)
```

### Why `ToolParams()` and not `{}`

`{}` is falsy in Python, so it takes the same introspection path as `None` and produces
the `kwargs` leak. `ToolParams()` is always truthy (Pydantic `BaseModel` doesn't define
`__bool__`), so it satisfies the `isinstance` check and hits the short-circuit path.

### Rule of thumb

Whenever using `ToolDef` with a dummy handler (`**kwargs`-style), always pass `ToolParams`
— populated or empty — alongside explicit `name` and `description`. Never pass a dict.

---

## 2. `tool.parameters` reads back as `ToolParams`, not a dict

**Affected file:** `tests/test_tools.py`

Once a `ToolDef` is constructed, reading `tool.parameters` back gives a `ToolParams` object,
not a plain dict. Any code that treats it like a dict will fail:

```python
# These all fail:
"brightness" in tool.parameters          # AttributeError
tool.parameters.keys()                   # AttributeError
tool.parameters["brightness"]            # TypeError
```

Access the underlying parameter dict via `.properties`:

```python
# Correct:
"brightness" in tool.parameters.properties
set(tool.parameters.properties.keys())
tool.parameters.properties["brightness"]  # returns a JSONSchema object
```

This affects both application code that inspects tool schemas at runtime and any unit tests
that verify parameter presence.

---

## 3. `ToolCall` field names and import location

**Affected file:** `src/ha_voice_bench/scorers/tool_call.py`

### Import location

`ToolCall` moved modules. Importing from `inspect_ai.model` still works but emits a
deprecation warning as of 0.3.18:

```
DEPRECATED: the 'ToolCall' class has been moved to 'inspect_ai.tool'.
Will be removed in 0.4.
```

Correct import:

```python
from inspect_ai.tool import ToolCall  # not inspect_ai.model
```

### Field names

The actual `ToolCall` dataclass fields (confirmed via `dataclasses.fields()`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | Unique call ID |
| `function` | `str` | The tool name (not `.name`) |
| `arguments` | `dict` | Already parsed — not a JSON string |
| `parse_error` | `str \| None` | Set when arguments couldn't be parsed as JSON |
| `type` | `str` | Always `"function"` |

Key points:
- The tool name is `tc.function`, not `tc.name`.
- `tc.arguments` is already a `dict` — no `json.loads()` needed in the normal case.
- `tc.parse_error` is the signal for malformed arguments; when set, `tc.arguments` may be
  empty or partially populated.

These are accessed from `state.messages[-1].tool_calls` (list of `ToolCall`) after
`generate(tool_calls="none")`.

---

## 4. All `ToolDef` objects must use distinct handler functions

**Affected file:** `src/ha_voice_bench/tools.py`

### What happens

Inspect's tool registry keys each tool by its **handler function object**. If multiple `ToolDef`
objects share the same handler (e.g., a single module-level `_noop`), each registration
overwrites the previous one. The last tool defined wins — every call to `use_tools()` sends 11
copies of that last tool to the model instead of 11 distinct tools.

In our case, `HassNevermind` was defined last, so the model received 11 identical
`HassNevermind` entries and had no knowledge of `HassTurnOn`, `HassLightSet`, etc.

### Symptom

The model responds with plain text (e.g., `HassTurnOn(light.kitchen_ceiling)`) instead of a
structured tool call, because it never saw the correct tools in the API request. The scorer
receives zero tool calls and marks everything I or N.

### The fix

Create a **new closure per tool** using a factory function:

```python
def _make_noop():
    async def _noop(**kwargs):
        return "OK"
    return _noop

HASS_TURN_ON = ToolDef(tool=_make_noop(), name="HassTurnOn", ...)
HASS_TURN_OFF = ToolDef(tool=_make_noop(), name="HassTurnOff", ...)
# etc. — each call to _make_noop() returns a distinct function object
```

### Rule of thumb

Never share a single dummy handler across multiple `ToolDef` objects. Each `ToolDef` must
receive its own function instance, even if the implementations are identical.

---
