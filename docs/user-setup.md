# User Setup & Configuration

How to get from a fresh clone to a running benchmark eval.

---

## Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) (package manager)
- A running llama.cpp server (or any OpenAI-compatible LLM endpoint)

---

## 1. Install Python dependencies

```bash
uv sync --extra dev
```

> **Note:** Plain `uv sync` installs only runtime dependencies. `--extra dev` is required to
> also install pytest, ruff, and other dev tools.

---

## 2. Set up an LLM server

The benchmark requires an OpenAI-compatible HTTP endpoint that supports tool calling.
[llama.cpp](https://github.com/ggerganov/llama.cpp) (`llama-server`) is the reference backend.

### Model recommendation

Qwen 2.5 7B Instruct (Q4_K_M) is a good starting point — strong tool-calling capability,
fits comfortably in 8 GB VRAM:

```
bartowski/Qwen2.5-7B-Instruct-GGUF  →  Qwen2.5-7B-Instruct-Q4_K_M.gguf  (~4.4 GB)
```

**Prefer bartowski's builds over the official Qwen repo.** bartowski uses imatrix-guided
quantization, which calibrates the quantization using a representative dataset to minimise
accuracy loss. The official `Qwen/Qwen2.5-7B-Instruct-GGUF` uses standard quantization and
shows measurably lower benchmark accuracy at the same quant level (Q4_K_M). This difference
likely applies across other model families too — prefer imatrix-quantized GGUFs where
available.

### llama-server startup command

```bash
llama-server \
  -hf bartowski/Qwen2.5-7B-Instruct-GGUF \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size 32768 \
  --jinja \
  -ngl 99
```

Key flags:
- `--jinja` — **required** for tool calling; enables Jinja2 chat-template rendering
- `-ngl 99` — offload all layers to GPU (set lower if you hit VRAM limits)
- `--ctx-size 32768` — recommended; 8192 only covers the small tier (~6K tokens). Medium needs
  ~9K, large ~13K, enormous ~26K. Use 32768 for full tier coverage on hardware that supports it.

The server exposes an OpenAI-compatible API at `http://localhost:8080/v1` by default.

---

## 3. Configure the environment

Copy the example env file to the repo root and edit it for your setup:

```bash
cp docs/env.example .env
# then edit .env — at minimum set OPENAI_BASE_URL to your server address
```

The `.env` file is gitignored; never commit it.

---

## 4. Run the smoke test

Verify the full pipeline end-to-end with a single sample:

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain \
  --limit 1
```

> **Note:** `inspect` is installed inside the `uv`-managed virtualenv. Prefix commands with
> `uv run` or activate the venv first (`source .venv/bin/activate`).

**What to check in the output:**
- Progress line completes without error
- `accuracy` summary shows a real number
- Token counts (`I:` / `O:`) are non-zero
- Log path is printed at the end

To inspect the conversation in detail (system prompt, tool list, model response), open the log
in the Inspect viewer or read the `.eval` log file directly
(see `docs/gotchas_learnings.md` §8).

---

## 5. Run the full benchmark

Once the smoke test passes, run against the full test set:

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain
```

> **Important:** Always use `--max-connections 1` for benchmarking. Inspect runs samples
> concurrently by default, which skews per-call latency measurements and can overwhelm a local
> inference server. Serial execution gives clean, comparable timing numbers across models.
> See `docs/gotchas_learnings.md` §7 for details.

Browse results in the Inspect viewer:

```bash
uv run inspect view
```

---

## Display options

The `--display` flag controls what Inspect renders to the terminal during a run:

| Value | When to use |
|-------|-------------|
| `plain` | **Default for most use.** Flat progress lines, no rich rendering. Works in any terminal and in scripts/automation. |
| `full` | Default if `--display` is omitted. Rich TUI with live updating panels. Use only in an interactive terminal. |
| `conversation` | Shows each message turn rendered as text boxes. Useful for debugging prompt content at a real terminal. |
| `none` | Suppresses all terminal output. Use in automated batch scripts where log files are the only record. |

For **automated/scripted runs** (e.g. via the orchestration script `scripts/run_benchmark.py`), use `--display plain`
combined with `--no-fail-on-error` and a run-specific `--log-dir`:

```bash
uv run inspect eval src/ha_voice_bench/task.py \
  --model openai/local \
  --max-connections 1 \
  --display plain \
  --no-fail-on-error \
  --log-dir logs/my-run \
  --tags qwen2.5-7b q4_k_m gpu \
  --seed 42
```

---

## 6. Multi-model matrix runs (orchestration)

For running a matrix of models × tiers × hardware modes automatically, use the orchestration
script. It SSH-es to the llama.cpp host, starts/stops the server for each configuration, and
collects `.eval` logs in structured subdirectories.

```bash
# Copy the example config and edit for your environment
cp configs/benchmark.example.yaml configs/my-run.yaml

# Preview what would run
uv run scripts/run_benchmark.py configs/my-run.yaml --dry-run

# Run the matrix
uv run scripts/run_benchmark.py configs/my-run.yaml

# Resume an interrupted run (reads config from inside the run dir)
uv run scripts/run_benchmark.py --resume logs/my-run/2026-03-04T14-30-00
```

Requires key-based SSH access to the llama.cpp host (set up with `ssh-copy-id` if needed).

### Warmup

After each server start, the orchestrator runs a short eval against `sample_test_data/` to
prime GPU kernels and the KV cache before benchmark timing begins. This is enabled by default.

**Config option** (in your `my-run.yaml`):
```yaml
# warmup_samples: 5   # limit warmup to first N samples; omit to run all (~80 cases, ~2 min)
```

**CLI flags** (override config):
```bash
--no-warmup              # disable warmup entirely
--warmup-samples N       # limit warmup to first N samples (e.g. 5 is usually sufficient)
```

Warmup logs land in `logs/<cfg-name>/<timestamp>/warmup/<server-config>/`.

See `docs/ha-benchmark-run-and-analysis.md` for the full orchestration workflow and how to
analyze the resulting `.eval` logs.
