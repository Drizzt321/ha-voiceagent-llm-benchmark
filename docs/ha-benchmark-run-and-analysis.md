# Running Evaluations and Analyzing Output

A practical guide for running the HA Voice LLM Benchmark and having an LLM agent (or a human)
analyze the resulting `.eval` log files. Usable from the project repo root.

---

## Prerequisites

- Python 3.13+, `uv` installed
- Dependencies installed: `uv sync --extra dev`

**For manual / interactive runs:** a running llama.cpp server (or any OpenAI-compatible endpoint
with tool-call support) and `.env` configured with `OPENAI_BASE_URL` pointing at your server.

**For orchestration runs:** SSH access to the llama.cpp host (key-based auth); the script
manages server start/stop automatically and does not need `.env`.

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

### Automated matrix run — orchestration script

The orchestration script handles the full benchmark matrix: SSH-ing to the llama.cpp host,
cycling through models / hardware modes / context sizes, and running all tiers for each
configuration automatically.

**First-time SSH setup** (required once):
```bash
ssh-copy-id <your-user>@<your-llama-host>
```

**Configure your run** — copy the example config and edit for your environment:
```bash
cp configs/benchmark.example.yaml configs/my-run.yaml
# Edit: server.llama_cpp_dir, models list, tiers, hardware_modes
```

**Run the matrix:**
```bash
uv run scripts/run_benchmark.py configs/my-run.yaml

# Preview without running anything:
uv run scripts/run_benchmark.py configs/my-run.yaml --dry-run

# Resume after an interruption — point at the existing run directory:
uv run scripts/run_benchmark.py --resume logs/my-run/2026-03-04T15-30-00

# Skip warmup (e.g. server was already warm from a previous run):
uv run scripts/run_benchmark.py configs/my-run.yaml --no-warmup

# Limit warmup to first N samples instead of all of sample_test_data/:
uv run scripts/run_benchmark.py configs/my-run.yaml --warmup-samples 5
```

**Output structure** — each invocation creates a timestamped directory under `logs/<config-stem>/`:

```
logs/
  my-run/                                     ← config file stem
    2026-03-04T15-30-00/                      ← this run (local timestamp)
      my-run.yaml                             ← copy of config as used (audit trail)
      orchestration.log                       ← full SSH/server/eval debug log
      warmup/                                 ← warmup evals (excluded from analysis)
        qwen2.5-7b-Q4_K_M-gpu-ctx32768/
          *.eval
      qwen2.5-7b-Q4_K_M-gpu-ctx32768/        ← one subdir per server config
        2026-03-04T...ha-voice-benchmark.eval
      qwen2.5-7b-Q4_K_M-cpu-ctx32768/
        2026-03-04T...ha-voice-benchmark.eval
    2026-03-05T10-00-00/                      ← a later run of the same config
      my-run.yaml                             ← may differ — detectable by diff
      ...
```

Runs of the same config are grouped together for easy comparison. The config copy inside
each run dir means you can always tell exactly what was run, even if you later edit the file.

**Warmup** — after each server start, the script runs a short eval against
`sample_test_data/` to prime GPU kernels and KV cache before benchmark timing begins.
This ensures the first benchmark sample isn't an outlier. Warmup runs ~80 samples by
default (~2 min); set `warmup_samples: 5` in config for a faster warmup if your hardware
warms up quickly. Warmup `.eval` logs are saved under `warmup/` and excluded from analysis.

Config options (all optional — defaults shown):
```yaml
# warmup_samples: 5    # limit warmup to first N samples; omit for all (~80, ~2min)
```

CLI overrides:
```
--no-warmup           skip warmup entirely
--warmup-samples N    override warmup sample count
```

**End-of-run summary** prints operational stats: total wall time, per-model timing, avg
latency per sample. Accuracy and failure analysis is left to the analysis step (see below).

---

### AI-assisted analysis

Once a run completes, hand the run directory to a Claude Code session. The session reads the
`.eval` zip files directly — each contains per-sample JSON with scores, explanations,
metadata, timing, and token counts.

**Finding the run directory** — the orchestrator prints it at startup:
```
Run dir:      logs/my-run/2026-03-04T15-30-00/
```

Or list recent runs:
```bash
ls -lt logs/my-run/        # most recent at top
```

**Prompt to start a single-run analysis:**
```
I've just completed a benchmark run. The run directory is:
  logs/my-run/2026-03-04T15-30-00/

It contains:
- my-run.yaml           the config used
- orchestration.log     server/SSH event log
- One subdirectory per model/hw/ctx config, each with a .eval log file

See docs/ha-benchmark-run-and-analysis.md for how to read .eval files and what to look for.

Please analyze this run:

Accuracy:
- Read my-run.yaml to understand which models, tiers, and hardware modes were tested
- For each .eval file, extract overall accuracy and per-dimension failure counts
- Identify dominant failure patterns (F1–F9 from docs/failure-patterns.md)
- Summarize findings in the format described in Step 5 of the analysis guide
- Update docs/failure-patterns.md with any new observations

Latency and throughput:
- From header["stats"], extract total_time, model_usage (input/output tokens)
- From each sample in samples/*.json, extract total_time and model_usage.input_tokens
- Compute: min/mean/max per-sample latency, and tokens-per-second (output tokens / time)
- Plot or tabulate: input token count vs latency to show the scaling relationship
- If multiple configs are present (gpu vs cpu, different ctx sizes), compare latency across them
- Flag any samples with unusually high latency (outliers) and note what was different about them
  (e.g. longer utterance, more complex tool call, retry)
```

**Prompt to compare two runs** (e.g. before/after a prompt change):
```
I have two benchmark runs to compare:
  Run A (baseline):     logs/my-run/2026-03-04T15-30-00/
  Run B (after change): logs/my-run/2026-03-05T10-00-00/

Both ran the same config (my-run.yaml). Compare them:

Accuracy:
- Accuracy delta per tier and model
- Which samples flipped C→I (regressions) and I→C (improvements)
- Whether the failure pattern distribution shifted
- Your assessment of whether the change was net positive

Latency:
- Mean per-sample latency for each run (from samples/*.json total_time)
- Did the change affect throughput? (tokens/sec from model_usage)
- Any new latency outliers introduced or resolved?
```

Claude Code reads the `.eval` zip files directly. See the Log File Format section for structure.

### Manual / single-tier run (legacy)

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

Every eval run produces a `.eval` file. Orchestration runs place them at
`logs/<cfg-stem>/<timestamp>/<model>-<quant>-<hw>-ctx<N>/<timestamp>.eval`.
Manual runs place them directly in whatever `--log-dir` was specified.
These are zip archives containing:

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

List runs for a given config, most recent first:
```bash
ls -lt logs/my-run/
```

List all `.eval` files across all runs, most recent first:
```bash
find logs -name "*.eval" -printf "%T@ %p\n" | sort -rn | head -20 | awk '{print $2}'
```

List `.eval` files within a specific run:
```bash
find logs/my-run/2026-03-04T15-30-00 -name "*.eval"
```

### Step 2 — Extract the summary data

```python
import zipfile
import json

# Orchestration: logs/<cfg-stem>/<timestamp>/<model>-<quant>-<hw>-ctx<N>/<timestamp>.eval
# Manual:        logs/<timestamp>.eval  (or whatever --log-dir was set to)
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

before = load_summaries("logs/my-run/2026-03-04T15-30-00/qwen2.5-7b-Q4_K_M-gpu-ctx32768/<timestamp>.eval")
after  = load_summaries("logs/my-run/2026-03-05T10-00-00/qwen2.5-7b-Q4_K_M-gpu-ctx32768/<timestamp>.eval")

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

Key fields:
- `header["stats"]["total_time"]` — wall time for the full eval
- `header["stats"]["model_usage"]` — aggregate input/output token counts
- `samples/<id>.json["total_time"]` — per-sample wall time in seconds
- `samples/<id>.json["model_usage"]["input_tokens"]` — per-sample input token count

Useful derived metrics:
- **Tokens/sec** = output tokens / total_time (throughput, comparable across hw modes)
- **Latency vs input tokens** — plot or bin samples by input token count; slope reveals
  prefill cost scaling (larger inventory → more tokens → higher latency)
- **Outliers** — samples with latency > 2× mean; often caused by retries or unusually
  long responses

Latency comparisons across model configurations only make sense when `--max-connections 1`
was used (serial execution). Concurrent runs skew per-call timing.

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

## Prompt Reference

### Default instructions

The benchmark uses HA's `DEFAULT_INSTRUCTIONS_PROMPT` verbatim as the system prompt
instructions. This is the same text the real Home Assistant conversation agent sends to the
model. It is defined in `src/ha_voice_bench/prompt.py`:

```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
When controlling a device, prefer passing just name and domain.
When controlling an area, prefer passing just area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
```

The entity inventory and a fixed timestamp are appended after these instructions to form the
complete system prompt.

### Custom prompt experiments

To try a prompt variation, create a plain-text file containing your replacement instructions
and point the config at it:

```yaml
# configs/my-experiment.yaml
instructions_file: configs/prompts/f1-mitigation.txt
```

```
# configs/prompts/f1-mitigation.txt
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
When controlling a device, prefer passing just name and domain.
When controlling an area, prefer passing just area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
Always use the friendly name from the `names:` field — never use the entity ID as a name.
```

The path is repo-relative. Omit `instructions_file` entirely to use the default HA prompt.

Each prompt variant should get its own config file so runs are self-contained and
reproducible. The config is copied into the run directory, so the exact prompt file path
used is recorded alongside the `.eval` logs.

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

---

## Config Reference

Full annotated example: `configs/benchmark.example.yaml`. All keys below are optional unless
marked **required**.

### `server` (required)

| Key | Type | Description |
|-----|------|-------------|
| `host` | string | **Required.** Hostname or IP of the machine running llama-server. |
| `ssh_user` | string | **Required.** SSH username. Key auth must be set up (`ssh-copy-id`). |
| `llama_cpp_dir` | string | **Required.** Directory on the remote host containing `bin/llama-server`. |
| `port` | int | **Required.** Port llama-server listens on (typically `8080`). |
| `startup_timeout` | int | **Required.** Seconds to wait for the server to respond after starting. Allow extra time on first run — llama-server downloads the model if not cached. |

### `tiers` (required)

List of tier names to benchmark. Each must have a corresponding
`{tier}-ha-entities.yaml` and `{tier}-test-cases.ndjson` in `base_dir`
(generated by `scripts/assemble_tier.py` when `assemble_tiers: true`).

```yaml
tiers:
  - small      # ~34 entities, ~80 cases
  - medium     # ~88 entities, ~104 cases
  # - large    # ~185 entities, ~126 cases
  # - enormous # ~453 entities, ~146 cases  (needs ctx_size >= 32768)
```

### `hardware_modes` (required)

List of hardware configurations. Each entry restarts the server with different GPU layer
settings (`ngl`). Label is used for directory naming and log tags.

```yaml
hardware_modes:
  - label: gpu
    ngl: 99    # all layers on GPU — fast, VRAM-limited
  - label: cpu
    ngl: 0     # CPU-only — slow, no VRAM limit
```

### `models` (required)

List of models to benchmark. Each entry is one row in the run matrix.

| Key | Type | Description |
|-----|------|-------------|
| `hf_repo` | string | **Required.** HuggingFace repo (`owner/repo`). llama-server downloads on first use via `-hf`. |
| `name` | string | **Required.** Short label used in directory names and log tags (no spaces). |
| `quant` | string | **Required.** Quantization to load (e.g. `Q4_K_M`, `Q8_0`, `F16`). Passed to llama-server as `-hfq`. Also used in directory naming. |
| `ctx_sizes` | list[int] | **Required.** Context window sizes to test. Each is a separate matrix cell — the server restarts for each. Use `32768` for the enormous tier (~26K token prompts); `8192` covers small/medium. |
| `extra_flags` | list[string] | Additional llama-server CLI flags (e.g. `["--override-kv", "tokenizer.ggml.add_bos_token=bool:false"]`). |

Prefer `bartowski/*` repos over official model org repos — bartowski uses imatrix-guided
quantization which gives measurably better accuracy at the same quant level.

### Run settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `assemble_tiers` | bool | `true` | Run `scripts/assemble_tier.py` for each tier before starting evals. Set `false` if tiers are already assembled. |
| `warmup_samples` | int | all (~80) | Limit warmup to the first N samples. `5` is usually enough to prime GPU kernels. Can also be set via `--warmup-samples N` CLI flag. |
| `timeout` | int | `30` | Total seconds allowed for a single LLM request including all retries. |
| `attempt_timeout` | int | `15` | Seconds allowed for one attempt before retrying. Catches stalled generations at 100% GPU. |
| `max_retries` | int | `1` | Number of retry attempts after a failed/timed-out attempt. |
| `instructions_file` | string | — | Repo-relative path to a plain-text file containing custom system prompt instructions. Omit to use the default HA prompt. |
| `base_dir` | string | `test_data` | Directory containing assembled tier files. |
| `log_dir` | string | `logs` | Root directory for all `.eval` log files. |

### CLI flags

These override or extend the config at runtime:

| Flag | Description |
|------|-------------|
| `--dry-run` | Print the run plan and exit — no servers started, no evals run. |
| `--resume <run-dir>` | Resume a previous run: skips any tier that already has a `.eval` file. Config is read from inside the run dir. |
| `--no-warmup` | Skip the warmup eval after each server start. |
| `--warmup-samples N` | Limit warmup to the first N samples (overrides `warmup_samples` in config). |
