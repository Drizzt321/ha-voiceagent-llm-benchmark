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

### llama-server startup command

```bash
llama-server \
  -hf bartowski/Qwen2.5-7B-Instruct-GGUF \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size 8192 \
  --jinja \
  -ngl 99
```

Key flags:
- `--jinja` — **required** for tool calling; enables Jinja2 chat-template rendering
- `-ngl 99` — offload all layers to GPU (set lower if you hit VRAM limits)
- `--ctx-size 8192` — sufficient for the HA system prompt + a full test case

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

Verify the full pipeline end-to-end with a single sample and verbose tracing:

```bash
uv run inspect eval src/ha_voice_bench/task.py --model openai/local -T base_dir=. --limit 1 --display=conversation
```

> **Note:** `inspect` is installed inside the `uv`-managed virtualenv. Prefix commands with
> `uv run` or activate the venv first (`source .venv/bin/activate`).

**What to check in the trace output:**
- System message contains entity inventory text
- Tools array lists all 11 HA intent tools (distinct names, not 11 copies of one tool)
- Model response contains `tool_calls` (not plain text only)
- `accuracy` summary shows a real number, no `WARNING Unable to convert value to float`
- `usage` shows non-zero `prompt_tokens` and `completion_tokens`

> **Display note:** `--display=conversation` renders message content in fixed-width terminal
> boxes. The YAML entity inventory will appear as one wrapped line — the actual prompt sent to
> the model has full newlines and indentation. To inspect the real prompt, read the `.eval` log
> (see `docs/gotchas_learnings.md` §8).

---

## 5. Run the full benchmark

Once the smoke test passes, run against the full 25-case test set:

```bash
uv run inspect eval src/ha_voice_bench/task.py --model openai/local -T base_dir=. --max-connections 1
```

> **Important:** Always use `--max-connections 1` for benchmarking. Inspect runs samples
> concurrently by default, which skews per-call latency measurements and can overwhelm a local
> inference server. Serial execution gives clean, comparable timing numbers across models.
> See `docs/gotchas_learnings.md` §7 for details.

Browse results in the Inspect viewer:

```bash
uv run inspect view
```
