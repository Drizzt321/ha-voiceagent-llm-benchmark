# Running Evaluations and Analyzing Output

A practical guide for running the HA Voice LLM Benchmark and having an LLM agent (or a human)
analyze the resulting `.eval` log files. Usable from the project repo root.

---

## Prerequisites

- Python 3.13+, `uv` installed
- A running llama.cpp server (or any OpenAI-compatible endpoint with tool-call support)
- `.env` configured with `OPENAI_BASE_URL` pointing at your server
- Dependencies installed: `uv sync --extra dev`

See `docs/user-setup.md` for full setup instructions.

---

## Running the Benchmark

### Standard interactive run

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain
```

**Key flags (non-negotiable):**
- `--max-connections 1` — always required; prevents concurrent requests from skewing latency and
  stalling the inference server under large tool-call prompts
- `--display plain` — suppresses TUI, emits flat progress lines readable in any terminal or
  script; use `--display none` in fully automated contexts

### Quick smoke test (single sample)

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain \
  --limit 1
```

### Re-run a specific failing sample

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain \
  --sample-id small-HassTurnOn-light-kitchen_ceiling-001
```

### Automated / matrix orchestration run

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display none \
  --no-fail-on-error \
  --log-dir logs/qwen2.5-7b-q4km-gpu \
  --tags qwen2.5-7b q4_k_m gpu \
  --metadata model=qwen2.5-7b quant=q4_k_m hw=gpu \
  --seed 42
```

Flags for automated runs:
- `--display none` — no terminal output; log files are the only record
- `--no-fail-on-error` — a single bad sample does not abort a matrix run
- `--log-dir` — one directory per model/quant/hardware configuration
- `--tags` / `--metadata` — structured labels attached to the log for reporting
- `--seed 42` — reproducibility; use the same seed across all configurations being compared

### Viewing results interactively

```bash
uv run inspect view
```

Opens a web UI on `http://localhost:7575` showing all logs in `./logs/`. Each sample displays
the utterance, expected vs. actual tool calls, and the per-dimension score breakdown in the
`explanation` field.

---

## Log File Format

Every run produces a `.eval` file in `./logs/`. These are zip archives containing:

```
header.json                         ← Run metadata, config, overall results
summaries.json                      ← One entry per sample: input, target, score, metadata
reductions.json                     ← Aggregated metrics per scorer
samples/<sample-id>_epoch_1.json    ← Full sample: messages, output, tool calls, timing
_journal/start.json                 ← Run plan
_journal/summaries/N.json           ← Incremental summaries written during the run
```

### Reading logs programmatically

```python
import zipfile
import json

with zipfile.ZipFile("logs/my-run.eval") as z:
    header = json.loads(z.read("header.json"))
    summaries = json.loads(z.read("summaries.json"))   # list of sample summaries
    reductions = json.loads(z.read("reductions.json")) # aggregated metrics
```

### `header.json` — key fields

```
header["eval"]["task_args"]          # which test data, tool tier, base_dir
header["eval"]["dataset"]["samples"] # total sample count
header["eval"]["model"]              # model identifier used
header["eval"]["revision"]["commit"] # git commit of the repo when run
header["results"]                    # overall accuracy metrics
header["stats"]                      # token counts, timing
```

### `summaries.json` — per-sample structure

Each element:

```json
{
  "id": "small-HassTurnOn-light-kitchen_ceiling-001",
  "epoch": 1,
  "input": "turn on the kitchen light",
  "target": "[{\"name\": \"HassTurnOn\", \"arguments\": {...}}]",
  "metadata": {
    "inventory_tier": "small",
    "inventory_file": "sample_test_data/small.yaml",
    "expected_response_type": "action_done",
    "meta/intent_type": "device_control",
    "meta/difficulty": "basic",
    "meta/description": "Basic light on by name, single light in area"
  },
  "scores": {
    "tool_call_scorer": {
      "value": "C",
      "answer": "[{\"name\": \"HassTurnOn\", \"arguments\": {...}}]",
      "explanation": "MATCH_QUALITY: optimal\nExpected 1 call(s):\n  ...\nGot 1 call(s):\n  ...\n\nChecks:\n  C response_type: C\n  C format_valid: C\n  C call_count: C\n  C tool_name: C\n  C args: C\n  C no_hallucinated_tools: C"
    }
  }
}
```

**`value`** — `"C"` (Correct) or `"I"` (Incorrect); the scalar used by `accuracy()`.

**`answer`** — JSON string of the actual tool calls the model made.

**`explanation`** — human-readable multi-line string. Always starts with `MATCH_QUALITY: <tier>`
(`optimal`, `equivalent`, `acceptable`, `degraded`), then shows expected vs. actual calls,
then a per-dimension breakdown.

### Score dimensions (in `explanation`)

| Dimension | What it checks |
|-----------|---------------|
| `response_type` | Did the model call/not-call tools as expected for this response type? |
| `format_valid` | Are tool call arguments well-formed JSON (no `parse_error`)? |
| `call_count` | Right number of tool calls? |
| `tool_name` | Correct intent tool(s) named? |
| `args` | Arguments match expected values (case-insensitive, `_any_of`, numeric ±0.01)? |
| `no_hallucinated_tools` | Only real HA tools called (none invented)? |

All dimensions must be `C` for `value` to be `"C"`.

---

## Analyzing Output with an LLM Agent

The following workflow is for an LLM agent (e.g. a Claude Code session, or an agent script)
running from the repo root. Humans can follow the same steps manually.

### Step 1 — Find the log to analyze

List available logs:

```bash
ls -lt logs/*.eval | head -20
```

Or find the most recent:

```bash
ls -t logs/*.eval | head -1
```

### Step 2 — Extract the summary data

```python
import zipfile
import json

log_path = "logs/<chosen>.eval"
with zipfile.ZipFile(log_path) as z:
    header = json.loads(z.read("header.json"))
    summaries = json.loads(z.read("summaries.json"))

# Overall accuracy
results = header.get("results", {})
stats = header.get("stats", {})
eval_info = header.get("eval", {})
```

### Step 3 — Compute per-dimension failure counts

Parse the `explanation` field to extract per-dimension C/I values:

```python
import re

dimension_keys = ["response_type", "format_valid", "call_count", "tool_name", "args", "no_hallucinated_tools"]
failures = {k: [] for k in dimension_keys}
quality_counts = {}

for s in summaries:
    score = s["scores"]["tool_call_scorer"]
    value = score["value"]
    explanation = score.get("explanation", "")

    # Extract MATCH_QUALITY
    mq = re.search(r"^MATCH_QUALITY: (\S+)", explanation, re.MULTILINE)
    quality = mq.group(1) if mq else "unknown"
    quality_counts[quality] = quality_counts.get(quality, 0) + 1

    if value == "I":
        for dim in dimension_keys:
            pattern = rf"(\w+)\s+{dim}:\s*(\w+)"
            m = re.search(pattern, explanation)
            if m and m.group(2) == "I":
                failures[dim].append({
                    "id": s["id"],
                    "input": s["input"],
                    "answer": score.get("answer"),
                    "target": s["target"],
                })
```

### Step 4 — Identify failure patterns

Cross-reference failures against `docs/failure-patterns.md` taxonomy:

| Pattern ID | Signal to look for |
|------------|-------------------|
| F1 — Entity ID instead of friendly name | `args: I`; actual `name` arg looks like `snake_case_id` |
| F2 — Wrong tool for similar intent | `tool_name: I`; actual tool is semantically related (e.g. `HassGetState` vs `HassClimateGetTemperature`) |
| F3 — Hallucinated tool | `no_hallucinated_tools: I` |
| F4 — Missing required argument | `args: I`; actual arguments dict is missing a key present in expected |
| F5 — Extra/spurious arguments | `args: I`; actual has keys not in expected |
| F6 — Wrong call count | `call_count: I` |
| F7 — Plain text instead of tool call | `format_valid: I` or `call_count: I`; `answer` is `[]` when expected calls > 0 |
| F8 — Wrong domain filter | `args: I`; `domain` arg is wrong |

### Step 5 — Summarize findings

A useful summary for an agent to produce (or a human to fill in):

```
Run: <log filename>
Date: <eval created timestamp from header["eval"]["created"]>
Model: <header["eval"]["model"]>
Dataset: <header["eval"]["dataset"]["name"]>, N=<samples>
Task args: <header["eval"]["task_args"]>

Overall accuracy: <header["results"]...>
Token usage: I:<input_tokens> O:<output_tokens>
Total time: <stats>

Failures by dimension:
  tool_name:              X / N
  args:                   X / N
  call_count:             X / N
  no_hallucinated_tools:  X / N
  format_valid:           X / N
  response_type:          X / N

Match quality distribution (of C samples):
  optimal:     N
  equivalent:  N
  acceptable:  N
  degraded:    N

Failure details:
  [list each failing sample: id, utterance, expected, actual, which dimensions failed, pattern ID if known]

Patterns observed:
  [F1/F2/etc with count and representative examples]

Recommendations:
  [prompt tweaks, test case updates, or model notes]
```

### Step 6 — Update `docs/failure-patterns.md`

For each newly observed failure pattern:
1. Check if it matches an existing entry (F1–F8 or beyond). If so, add the new case to
   the "Observed in" table.
2. If it's a new pattern, add a new section following the existing format.
3. Update the "Observations by model / run" table at the bottom with the run summary row.

### Step 7 — Cross-run comparison (optional)

To compare two runs (e.g. before and after a prompt change, or two models):

```python
def load_summaries(log_path):
    with zipfile.ZipFile(log_path) as z:
        return json.loads(z.read("summaries.json"))

def accuracy(summaries):
    scores = [s["scores"]["tool_call_scorer"]["value"] for s in summaries]
    return scores.count("C") / len(scores)

before = load_summaries("logs/run-A.eval")
after  = load_summaries("logs/run-B.eval")

print(f"Before: {accuracy(before):.1%}")
print(f"After:  {accuracy(after):.1%}")

# Find regressions: C → I
before_by_id = {s["id"]: s["scores"]["tool_call_scorer"]["value"] for s in before}
after_by_id  = {s["id"]: s["scores"]["tool_call_scorer"]["value"] for s in after}

regressions = [id for id in before_by_id if before_by_id[id] == "C" and after_by_id.get(id) == "I"]
improvements = [id for id in before_by_id if before_by_id[id] == "I" and after_by_id.get(id) == "C"]

print(f"Regressions: {regressions}")
print(f"Improvements: {improvements}")
```

---

## What to Look For

### High-value failure signals

- **`tool_name: I` with `args: I`** — model is fundamentally confused about which tool to use;
  not a prompt-fixable argument issue, likely a capability gap or poor tool description.
- **`args: I` with `tool_name: C`** — right intent, wrong entity or argument value; usually
  F1 (entity ID vs friendly name) or ambiguous phrasing in the inventory.
- **`format_valid: I`** — model produced malformed structured output; may indicate weak
  tool-calling fine-tuning, or a prompt that's too long for the model's context window.
- **`no_hallucinated_tools: I`** — model invented a tool name; prompt is not constraining the
  model to the provided tool set.
- **`response_type: I`** — model called tools when it should have refused (or vice versa);
  look at `error` and `clarification` type cases specifically.
- **`MATCH_QUALITY: degraded`** — model passed, but only on a fallback that the scorer considers
  significantly worse than the primary expected answer; worth reviewing even if it scored C.

### Inventory size sensitivity

When comparing runs across tiers (small → medium → large → enormous), look for:
- Does `args: I` rate rise faster than `tool_name: I` as inventory grows? (Entity confusion
  worsens with more entities — expected.)
- Does `call_count: I` increase with inventory size? (Model may start calling multiple tools
  when only one is needed, or vice versa, under larger context.)
- Does `format_valid: I` appear under large inventories where it didn't under small? (Context
  length pressure may degrade structured output quality.)

### Latency

Per-sample timing is in the full sample JSON (`samples/<id>.json`), in the `total_time` and
`working_time` fields. `header["stats"]` has aggregate timing. Latency comparisons across
model configurations only make sense when `--max-connections 1` was used (serial execution).

---

## Debugging a Specific Failure

1. Run with `--display conversation` at an interactive terminal to see the raw prompt and
   model response turn-by-turn.
2. Or extract the full sample from the archive:

```python
with zipfile.ZipFile("logs/my-run.eval") as z:
    sample = json.loads(z.read("samples/small-HassTurnOn-light-kitchen_ceiling-001_epoch_1.json"))

# Full conversation
for msg in sample["messages"]:
    print(f"[{msg['role']}]")
    if isinstance(msg.get("content"), str):
        print(msg["content"][:500])
    elif isinstance(msg.get("content"), list):
        for part in msg["content"]:
            print(str(part)[:500])
    print()

# What the model actually produced
print("Output:", sample["output"])
```

3. The `attachments` key in a sample contains the rendered system prompt as sent to the model.
   Compare it against `docs/ha-prompt-reference.md` to verify the prompt was built correctly.

---

## Limitations and Known Issues

- **Tool tier must match the test data**: if `tool_tier=full` (31 tools) was used to run but
  only MVP tools are expected in the test cases, hallucination scores will be wrong.
- **Alternative expected calls**: if the primary expected answer is strict but a reasonable
  alternative wasn't added, F2-type failures can look like real errors when they're actually
  correct behavior. When a C score shows `MATCH_QUALITY: degraded`, review whether the primary
  should be relaxed or the alternative promoted.
- **Serial execution is assumed for latency analysis**: any run without `--max-connections 1`
  produces skewed per-call timing numbers that should not be used for inference speed comparison.
- **The `.eval` format is internal to Inspect AI** and may change across minor versions. The
  code above targets `inspect_ai>=0.3.184`. If fields are missing, check the inspect version
  in `header["eval"]["packages"]["inspect_ai"]`.
