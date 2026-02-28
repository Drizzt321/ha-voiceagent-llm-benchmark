# HA Voice LLM Benchmark

A benchmarking framework that evaluates local LLM models for Home Assistant voice control using [Inspect AI](https://inspect.aisi.org.uk/).

## What It Does

Given a voice command and a smart home entity inventory, does the model call the right HA intent tool with the right arguments? The framework sends HA-formatted prompts to a local llama.cpp server and scores the model's tool-call responses against expected results — without going through the full HA pipeline.

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Lint
ruff check .

# Run a benchmark eval (after darkllama is configured)
cp .env.example .env
# Edit .env with your server details
inspect eval src/ha_voice_bench/task.py --model openai/local
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full design.

```
Test Cases (NDJSON) + Inventory (YAML)
        ↓
  Dataset Loader       →  Inspect Samples
  Solver               →  HA system prompt + tool defs + generate()
  Tier 1 Scorer        →  multi-dimensional C/I/N scores
        ↓
  inspect view         →  browse results in browser
```

## Project Layout

```
src/ha_voice_bench/
├── dataset.py          # NDJSON loader → Inspect Samples
├── tools.py            # HA intent ToolDef objects (11 MVP tools)
├── prompt.py           # System prompt assembly with entity inventory
├── solver.py           # Inspect Solver: wires prompt + tools + generate()
├── task.py             # Inspect Task entry point
└── scorers/
    └── tool_call.py    # Tier 1: tool-call correctness (multi-dimensional)

sample_test_data/
├── small.yaml               # 10-entity, 6-area inventory
├── small_test_cases.ndjson  # 25 test cases
├── sample_inventory.yaml    # 2-entity fixture for unit tests
└── sample_test_cases.ndjson # 5-case fixture for unit tests

tests/
├── conftest.py              # Shared fixtures (sample data paths)
├── test_dataset.py          # Dataset loader tests
├── test_tools.py            # Tool definition tests
├── test_prompt.py           # Prompt assembly tests
└── test_scorers.py          # Tier 1 scorer tests

docs/                        # Architecture, specs, implementation plan
logs/                        # Inspect eval logs (gitignored)
configs/                     # Per-host server configs
```

## Infrastructure

- **LLM Server:** llama.cpp (`llama-server`) on darkllama VM, OpenAI-compatible API at `http://darkllama.lan:8080/v1`
- **Models:** GGUF format, Qwen 2.5 family recommended for tool-calling capability
- **Inspect AI:** `>=0.3.184,<0.4`

## Docs

| File | Contents |
|------|----------|
| [`docs/architecture.md`](docs/architecture.md) | System design and key decisions |
| [`docs/ha-prompt-reference.md`](docs/ha-prompt-reference.md) | HA prompt and tool schema format |
| [`docs/test-data-format.md`](docs/test-data-format.md) | NDJSON and YAML schemas |
| [`docs/scoring-design.md`](docs/scoring-design.md) | Multi-dimensional scoring explained |
| [`docs/implementation-plan-m1.md`](docs/implementation-plan-m1.md) | M1 step-by-step implementation plan |
| [`docs/gotchas_learnings.md`](docs/gotchas_learnings.md) | Inspect AI gotchas and implementation learnings |

## License

Apache-2.0
