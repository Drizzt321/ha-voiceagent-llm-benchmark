# Architecture — HA Voice LLM Benchmarking

## Purpose

This framework evaluates how well local LLM models handle Home Assistant voice commands. Instead of testing through the full HA voice pipeline (wake word → STT → LLM → TTS), we isolate the LLM decision-making layer and test it directly: given a voice command and a list of smart home devices, does the model call the right intent tool with the right arguments?

This matters because the LLM is the critical decision point in the voice pipeline. A model that reliably picks the right tool with the right arguments produces a voice assistant that works. One that doesn't — even by a small margin — produces one that's frustrating.

## Why Inspect AI

[Inspect AI](https://inspect.aisi.org.uk/) is an open-source LLM evaluation framework from the UK AI Safety Institute. We use it because:

- **Built for tool-calling evals** — first-class support for `ToolDef`, `use_tools()`, and capturing tool calls without executing them
- **Structured logging** — every run produces a detailed log with per-sample scores, timing, token counts, and model outputs
- **Built-in viewer** — `inspect view` provides a web UI for exploring results
- **Model-agnostic** — works with any OpenAI-compatible API (which llama.cpp provides)
- **Composable** — custom solvers, scorers, and datasets plug into a clean framework

## How It Works

```
Test Case (NDJSON)          Inventory (YAML)
        │                         │
        ▼                         ▼
┌─────────────────────────────────────────┐
│  Dataset Loader                         │
│  (dataset.py)                           │
│  Reads test cases → Inspect Samples     │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Solver                                 │
│  (solver.py + prompt.py + tools.py)     │
│                                         │
│  1. Read inventory from sample metadata │
│  2. Build HA-format system prompt       │
│  3. Register HA intent tools (ToolDefs) │
│  4. Call generate(tool_calls="none")    │
│     → sends to llama.cpp, captures      │
│       tool calls without executing      │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Scorer                                 │
│  (scorers/tool_call.py)                 │
│                                         │
│  Compare actual tool calls vs expected: │
│  - Correct tool name?                   │
│  - Correct arguments?                   │
│  - Right number of calls?               │
│  - No hallucinated tools?               │
│  - Valid structured output?             │
│  - Correct response type?              │
│                                         │
│  Output: multi-dimensional C/I/N score  │
└───────────────────┬─────────────────────┘
                    │
                    ▼
            Inspect Eval Log
            (viewable in inspect view)
```

## Key Design Decisions

### Test against llama.cpp directly, not through HA

We send prompts to llama.cpp's OpenAI-compatible endpoint. We don't go through Home Assistant. This isolates the LLM evaluation from HA's own processing, network latency, and integration quirks. The prompt we send replicates what HA would send, so results are directly applicable.

### Tool calls captured, not executed

`generate(tool_calls="none")` tells Inspect to send tool definitions to the model (so it knows what tools are available) but not to execute the tool handlers when the model calls them. We just capture what the model tried to call and score it. The `_noop` handlers in `tools.py` exist only to satisfy Inspect's API — they're never invoked.

### Cache-friendly prompt ordering

HA's default prompt puts the timestamp first, then instructions, then entities. We reverse this: instructions → entities → timestamp. The rationale is KV cache optimization — when benchmarking the same model across many test cases with the same inventory, the static prefix (instructions + entities) stays cached and only the timestamp + user utterance changes. This is a deliberate divergence from HA's default, documented as a benchmarking optimization. A future A/B test can compare the two orderings.

### Multi-dimensional scoring

Rather than a single pass/fail, the scorer produces scores on multiple dimensions (tool name, arguments, call count, format validity, etc.). This gives much richer diagnostic information — a model that picks the right tool but gets the arguments wrong is qualitatively different from one that calls a nonexistent tool.

### Inventory tiers

Smart homes vary enormously in size. A 500-entity home is a harder problem than a 10-entity one because the model has more context to reason over and more entities to confuse. We test across multiple inventory sizes (Small → Enormous) to understand how model accuracy degrades with scale.

## Components

| Component | File | Responsibility |
|-----------|------|---------------|
| Dataset Loader | `src/ha_voice_bench/dataset.py` | Read NDJSON → Inspect Samples |
| Tool Definitions | `src/ha_voice_bench/tools.py` | HA intent tools as ToolDef objects |
| Prompt Assembly | `src/ha_voice_bench/prompt.py` | Build HA-format system prompt with inventory |
| Solver | `src/ha_voice_bench/solver.py` | Wire prompt + tools + generate() |
| Task | `src/ha_voice_bench/task.py` | Inspect Task entry point |
| Tier 1 Scorer | `src/ha_voice_bench/scorers/tool_call.py` | Tool-call correctness validation |

## Infrastructure

- **LLM Server:** llama.cpp (`llama-server`) on a dedicated inference host, exposed as an OpenAI-compatible API at `http://localhost:8080/v1` (or a LAN address configured in `.env`)
- **Eval Runner:** Inspect AI on the development machine, connected to the inference host
- **Models:** GGUF format, primarily Qwen 2.5 family for tool-calling capability
- **Logs:** Stored in `logs/`, viewable with `inspect view`

## Running Conventions

### Serial execution

Always run with `--max-connections 1`. Concurrent requests skew latency measurements and can
stall llama.cpp under large tool-call prompts (31 tools × many samples). See
`gotchas_learnings.md` §7.

### Display modes

Use `--display plain` for interactive runs (progress lines, no TUI). Use `--display none` for
automated batch runs where log files are the only record. See `gotchas_learnings.md` §8 for the
full table and example commands.

### Interactive run (testing / spot-checking)

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain
```

### Automated run (matrix orchestration, Step 18+)

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
