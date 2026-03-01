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

## 5. `task.py` must use absolute imports and anchor paths to `__file__`

**Affected file:** `src/ha_voice_bench/task.py`

### Relative imports break

When `inspect eval src/ha_voice_bench/task.py` is run, Inspect loads the file by path using
`importlib`, not as part of the `ha_voice_bench` package. Relative imports (`from .dataset
import ...`) fail with `ModuleNotFoundError` because the module has no package context.

**Fix:** use absolute imports (`from ha_voice_bench.dataset import ...`). The package is
installed in editable mode so absolute imports work fine.

### CWD is changed to the task file's directory

Inspect changes the working directory to `src/ha_voice_bench/` when loading the task module.
Any path resolved relative to CWD (e.g. `Path(".") / "sample_test_data/..."`) will fail
because that path doesn't exist under `src/ha_voice_bench/`.

**Fix:** anchor all relative paths to the repo root via `__file__`:

```python
_REPO_ROOT = Path(__file__).resolve().parents[2]  # src/ha_voice_bench/task.py → repo root

def _resolve(base_dir: str, rel_path: str) -> Path:
    base = Path(base_dir) if Path(base_dir).is_absolute() else _REPO_ROOT / base_dir
    return base / rel_path
```

This is stable regardless of CWD at invocation time.

---

## 6. `Score.value` must be a scalar for `accuracy()` to aggregate correctly

**Affected file:** `src/ha_voice_bench/scorers/tool_call.py`

`accuracy()` expects `Score.value` to be a `"C"`/`"I"`/`"N"` string or a `0`/`1` float.
Returning a dict (e.g. `{"tool_name": "C", "args": "I", ...}`) causes a silent float-conversion
failure: the `accuracy` summary line shows `0.000` regardless of actual results, and a
`WARNING Unable to convert value to float` is emitted for every sample.

The per-dimension breakdown is not lost — it belongs in `Score.explanation`, where the Inspect
viewer shows it per-sample. `Score.value` should carry only the scalar overall verdict:

```python
return Score(
    value=overall,          # "C" or "I" — used by accuracy() for aggregation
    explanation=explanation, # per-dimension breakdown shown in inspect view
    ...
)
```

---

## 7. Always run evaluations serially (`--max-connections 1`)

**Context:** benchmark methodology

By default, Inspect evaluates samples concurrently — multiple model API requests are in
flight simultaneously. This is efficient for throughput but wrong for benchmarking:

- **Latency measurements are skewed** — requests queue behind each other on the server,
  so measured latency reflects queue depth rather than actual single-call inference time.
- **The llama.cpp server can be overwhelmed** — with many concurrent long-context requests
  (e.g. 31 tools in the prompt), the server may stall or time out.

Always pass `--max-connections 1` to enforce serial execution:

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain
```

This ensures each sample completes before the next one starts, giving clean per-call
latency numbers and keeping the inference server healthy.

---

## 8. Choosing a `--display` mode

The `--display` flag controls what Inspect renders to the terminal during a run. The default
(`full`) uses a rich TUI that requires an interactive terminal. Choose based on context:

| Mode | Use when |
|------|----------|
| `plain` | **Default for most use.** Flat progress lines; works in any terminal and in non-interactive environments (scripts, CI, piped output). |
| `none` | Automated batch scripts where log files are the only record. Suppresses all terminal output. |
| `full` | Default if `--display` is omitted. Rich live-updating TUI. Only use in a real interactive terminal. |
| `conversation` | Debugging prompt content at an interactive terminal — renders each message turn as a text box. |

### Standard interactive run

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain
```

### Automated / orchestration run (Step 18+)

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display none \
  --no-fail-on-error \
  --log-dir logs/<config-id> \
  --tags <model> <quant> <hw> \
  --metadata model=<model> quant=<quant> hw=<hw> \
  --seed 42
```

Key flags for automated runs:
- `--display none` — no terminal output; log files are the record
- `--no-fail-on-error` — a single bad sample doesn't abort the matrix run
- `--log-dir logs/<config-id>` — one directory per model/quant/hardware configuration
- `--tags` / `--metadata` — attach structured labels to each run for the report generator
- `--seed` — pin the random seed for reproducibility across configurations

### Debugging prompt content

When you need to inspect the exact system prompt, tool list, or model response, use
`--display conversation` at a real terminal, or read the `.eval` log directly (it's a zip):

```python
import zipfile, json
with zipfile.ZipFile("logs/my-run.eval") as z:
    sample = json.loads(z.read("samples/<sample-id>.json"))
print(list(sample["attachments"].values())[0])  # system prompt
```

Note: `--display conversation` renders message content in fixed-width terminal boxes. Multi-line
content (e.g. the YAML entity inventory) appears as one wrapped line — the actual prompt sent to
the model retains all newlines. The `.eval` log shows the real content.

---
