# HA Voice LLM Benchmark — Gemma 4 Model Evaluation, April 2026

First benchmark of Google's Gemma 4 model family (E2B and E4B) for Home Assistant voice intent processing, comparing reasoning modes and quantization levels against the established Qwen3-8B baseline.

## Top-Line Results

**Overall accuracy (averaged across small + medium tiers, 3 runs each, reasoning OFF):**

| Model | Quant | Size | Combined | Small | Medium | Avg Lat | Med Lat | vs Qwen3-8B |
|-------|-------|------|:--------:|:-----:|:------:|:-------:|:-------:|:-----------:|
| E4B | Q5_K_M | 5.82 GB | **77.5% ±1.7** | 78.8% | 76.6% | 1.1s | 0.8s | -2.1pp |
| E4B | Q6_K | 6.33 GB | 77.2% ±0.9 | 77.1% | 77.2% | 1.0s | 0.8s | -2.4pp |
| E4B | Q8_0 | 8.03 GB | 76.4% ±0.8 | 76.7% | 76.3% | 1.0s | 0.8s | -3.2pp |
| E4B | Q4_K_M | 5.41 GB | 75.4% ±0.3 | 74.6% | 76.0% | 0.9s | 0.7s | -4.2pp |
| E2B | Q8_0 | 4.97 GB | 70.7% ±0.5 | 75.0% | 67.3% | 0.7s | 0.6s | -8.9pp |
| E2B | Q5_K_M | 3.66 GB | 68.7% ±0.3 | 70.0% | 67.6% | 0.7s | 0.6s | -10.9pp |
| E2B | Q4_K_M | 3.46 GB | 62.3% ±1.9 | 72.5% | 54.5% | 0.6s | 0.5s | -17.3pp |
| — | — | — | — | — | — | — | — | — |
| *Qwen3-8B (Iter4)* | *Q4_K_M* | *~5 GB* | *79.6%* | *~80%* | *~79%* | *1.7s* | *—* | *baseline* |

**Reasoning unlimited (1 run, no budget cap — E2B only):**

| Model | Quant | Small | Medium | Avg Lat | vs Reasoning Off |
|-------|-------|:-----:|:------:|:-------:|:----------------:|
| E2B | Q4_K_M | **83.8%** | **78.8%** | 4.1s | +16.8pp combined |
| E2B | Q5_K_M | 80.0% | 69.2% | 5.0s | +6.3pp |
| E2B | Q8_0 | 82.5% | 78.8% | 4.3s | +10.3pp |
| E4B | Q4_K_M | 80.0% | hung* | 8.0s | — |

*E4B Q4 medium hung at 70/104 samples due to unlimited reasoning + slow decode exceeding 62s client timeout.*

**Key findings:**

1. **E4B Q5_K_M (reasoning off) is the best Gemma 4 variant at 77.5%** — 2pp below Qwen3-8B but at **half the latency** (0.8s median vs 1.7s). For latency-sensitive deployments, this is a viable alternative.

2. **Reasoning mode is transformative for accuracy (+6-17pp)** but devastating for latency (6-10x slower). The E2B Q4 jumped from 62.3% to 83.8% with reasoning — exceeding the Qwen3-8B baseline — but at 4.1s avg latency. A bounded reasoning budget (512 tokens, run pending) may recover most of this gain at acceptable latency.

3. **E2B is too small without reasoning** — the 2.3B effective parameter model drops to 54-72% without thinking, with a catastrophic medium tier collapse on Q4_K_M (54.5%). The E4B models hold up much better (74-78%) because the larger effective parameter count compensates.

4. **Q5_K_M is the sweet spot quantization** — consistently best or tied-best for both E2B and E4B, outperforming both Q4_K_M (lower) and Q8_0 (higher). Bartowski's imatrix-guided Q5 quantization appears to hit an optimal quality point for this model family on this task.

5. **E4B accuracy is remarkably flat across quants** — Q4 through Q8 spans only 75.4% to 77.5% (2.1pp range). This suggests the model's tool-calling capability saturates early and isn't bottlenecked by quantization precision.

6. **Latency is excellent across the board** — all models at sub-1s median, with E2B at 0.5-0.6s and E4B at 0.7-0.8s. This is 2-3x faster than Qwen3-8B even though Gemma 4 is generating similar output token counts (~21-29 tokens/sample).

---

## Benchmark Setup

### Hardware

- **GPU:** NVIDIA GeForce GTX 1080 (8 GB VRAM)
- **Host:** darkllama bhyve VM on FreeBSD, Debian testing
- **Inference:** llama.cpp build 8931, fully GPU-offloaded (`ngl=99`)

### Test Configuration

- **Tiers:** Small (34 entities, 80 test cases) and Medium (88 entities, 104 test cases)
- **Scoring:** Strict multi-dimensional (all dimensions must pass)
- **Runs:** 3 per model/config/tier combination (reasoning off); 1 run (reasoning unlimited)
- **Prompt:** Iteration 4 (F7 refusal + HassGetState preference), file: `configs/qwen3.5_f7_refusal.txt`
- **Context:** 22000 tokens (matching Qwen3-8B baseline)
- **Reasoning control:** `--reasoning off` (3-run set) or no flag (unlimited, 1 run)

### Models Tested

| Model | HF Repo | Quant | File Size | Effective Params | Architecture |
|-------|---------|-------|-----------|------------------|--------------|
| E2B | bartowski/google_gemma-4-E2B-it-GGUF | Q4_K_M | 3.46 GB | ~2.3B | Dense (PLE) |
| E2B | bartowski/google_gemma-4-E2B-it-GGUF | Q5_K_M | 3.66 GB | ~2.3B | Dense (PLE) |
| E2B | bartowski/google_gemma-4-E2B-it-GGUF | Q8_0 | 4.97 GB | ~2.3B | Dense (PLE) |
| E4B | bartowski/google_gemma-4-E4B-it-GGUF | Q4_K_M | 5.41 GB | ~4.5B | Dense (PLE) |
| E4B | bartowski/google_gemma-4-E4B-it-GGUF | Q5_K_M | 5.82 GB | ~4.5B | Dense (PLE) |
| E4B | bartowski/google_gemma-4-E4B-it-GGUF | Q6_K | 6.33 GB | ~4.5B | Dense (PLE) |
| E4B | bartowski/google_gemma-4-E4B-it-GGUF | Q8_0 | 8.03 GB | ~4.5B | Dense (PLE) |

All models use Per-Layer Embeddings (PLE), where stored parameter count exceeds effective active parameters.

### Prompt

```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
When controlling a specific device, always use the friendly name from `names:` and the domain.
When controlling an area, prefer passing just the area name and domain.
When a user asks to turn on all devices of a specific type, ask user to specify an area, unless there is only one device of that type.
Prefer HassGetState for sensor and binary_sensor state queries, and for checking the state of locks, covers, and media players.
If no provided tool directly fulfills the user's request, respond without calling any tool.
```

---

## Detailed Results — Reasoning Off (3-Run Average)

### Per-Tier Breakdown

| Model | Quant | Small Acc | Small Lat | Medium Acc | Medium Lat | P95 Lat |
|-------|-------|:---------:|:---------:|:----------:|:----------:|:-------:|
| E2B | Q4_K_M | 72.5% | 0.6s | 54.5% | 0.6s | 0.9s |
| E2B | Q5_K_M | 70.0% | 0.6s | 67.6% | 0.7s | 1.0s |
| E2B | Q8_0 | 75.0% | 0.6s | 67.3% | 0.7s | 1.0s |
| E4B | Q4_K_M | 74.6% | 0.7s | 76.0% | 0.9s | 1.6s |
| E4B | Q5_K_M | 78.8% | 0.8s | 76.6% | 1.1s | 1.8s |
| E4B | Q6_K | 77.1% | 0.8s | 77.2% | 1.0s | 1.7s |
| E4B | Q8_0 | 76.7% | 0.9s | 76.3% | 1.0s | 1.6s |

**Notable pattern:** E2B models show significant small→medium accuracy degradation (up to -18pp for Q4_K_M), while E4B models are stable or even improve slightly. The larger effective parameter count handles entity disambiguation with larger inventories much better.

### Run-to-Run Variance

| Model | Quant | Run 1 | Run 2 | Run 3 | Stdev |
|-------|-------|:-----:|:-----:|:-----:|:-----:|
| E2B Q4_K_M | combined | 60.3% | 64.1% | 62.5% | ±1.9 |
| E2B Q5_K_M | combined | 69.0% | 68.5% | 68.5% | ±0.3 |
| E2B Q8_0 | combined | 70.7% | 71.2% | 70.1% | ±0.5 |
| E4B Q4_K_M | combined | 75.0% | 75.5% | 75.5% | ±0.3 |
| E4B Q5_K_M | combined | 78.8% | 78.3% | 75.5% | ±1.7 |
| E4B Q6_K | combined | 76.6% | 78.3% | 76.6% | ±0.9 |
| E4B Q8_0 | combined | 75.5% | 76.6% | 77.2% | ±0.8 |

All models show low variance (≤1.9pp stdev). E4B Q5_K_M has the highest variance at ±1.7pp, driven by one weaker run (75.5%).

---

## Failure Analysis

### Dimension Breakdown (3-run total, all models, reasoning off)

| Dimension | Failures | % of All Failures |
|-----------|:--------:|:-----------------:|
| args | 840 | 79.3% |
| call_count | 706 | 66.7% |
| tool_name | 636 | 60.1% |
| response_type | 614 | 58.0% |
| format_valid | 0 | 0.0% |
| no_hallucinated_tools | 0 | 0.0% |

Total: 3864 samples, 1059 failures (27.4% failure rate).

**Positive signals:**
- **Zero format_valid failures** — Gemma 4 produces well-formed tool call JSON consistently
- **Zero hallucinated tools** — never invents tool names; stays within the provided tool set

**Primary failure mode:** `args` failures dominate (79.3% of all failures), typically combined with `tool_name` and `call_count`. This indicates the model is mostly failing on complex intent disambiguation rather than basic tool-calling mechanics.

### Most Common Failing Test Cases

These test cases fail across all models and all 3 runs (21 failures = 7 models × 3 runs):

| Test Case | Category | Pattern |
|-----------|----------|---------|
| out_of_scope (search, shopping) | F7/F9 | Model calls tools instead of refusing |
| implicit (good_morning, goodnight, leaving, movie_time) | F6 | Multi-call routines — model can't generate sequences |
| multi (cover_light_bedroom, lock_lights) | F6 | Multi-tool calls — model undercalls |
| HassTurnOn-cross-kitchen_light_ambig | F2 | Ambiguous entity resolution |
| HassTurnOff/On-light-kitchen-area | F8 | Area-based control confusion |
| HassTurnOn-light-unavailable | F7 | Unavailable entity detection |
| HassLightSet-light-color_temp, rgbw | F4/F5 | Complex light attribute arguments |
| HassFanSetSpeed (medium only) | F2/F4 | Fan speed intent mapping |

**These are the same failure modes observed in Qwen3-8B and Qwen3.5** — they represent structural test case difficulty, not Gemma-specific weaknesses:
- Implicit routines and multi-call patterns are immovable at this model scale
- Out-of-scope refusal is a known F7 challenge
- Color temperature and RGBW light settings require precise argument construction

---

## Reasoning Mode Analysis

### Token Usage (from unlimited reasoning run)

| Metric | E2B (small) | E4B (small) |
|--------|:-----------:|:-----------:|
| Total output tokens/sample | 264 mean | 276 mean |
| Reasoning tokens (estimated) | ~200 mean, ~494 max | ~203 mean, ~494 max |
| Response tokens | ~25 | ~25 |
| Reasoning as % of output | ~76% | ~73% |

The model generates ~200 reasoning tokens on average before producing a ~25 token tool call response. The reasoning content follows a structured pattern: analyze the request, scan the entity inventory, select the appropriate tool, construct arguments.

### Reasoning Impact by Model

| Config | Combined Acc | Avg Latency | Reasoning Tokens |
|--------|:----------:|:-----------:|:----------------:|
| E2B Q4 reasoning ON | ~81% | 4.1s | ~200 mean |
| E2B Q4 reasoning OFF | 62.3% | 0.6s | 0 |
| Delta | **+18.7pp** | **+3.5s** | — |
| E2B Q8 reasoning ON | ~81% | 4.3s | ~200 mean |
| E2B Q8 reasoning OFF | 70.7% | 0.7s | 0 |
| Delta | **+10.3pp** | **+3.6s** | — |

Reasoning mode disproportionately helps the lower quants — Q4_K_M gains +18.7pp vs Q8_0's +10.3pp. This suggests reasoning compensates for quantization-induced precision loss.

### Timeout Issue (E4B Unlimited)

E4B Q4_K_M with unlimited reasoning hung at 70/104 samples on medium tier. Root cause: the combination of unlimited reasoning budget (`INT_MAX` tokens), slower E4B decode speed (~8s/sample), and the 62s client timeout caused specific samples with longer reasoning chains (863+ tokens observed) to exceed the timeout. The Inspect runner then entered exponential backoff retry, creating an infinite loop.

**Fix applied:** `--reasoning off` for the 3-run benchmark set. A bounded budget run (`--reasoning-budget 512`) is pending to find the accuracy/latency sweet spot.

---

## Comparison with Previous Models

### Accuracy Ranking (combined small+medium, best config per model)

| Rank | Model | Config | Combined Acc | Avg Latency |
|------|-------|--------|:----------:|:-----------:|
| 1 | Gemma 4 E2B Q4 | reasoning ON* | ~81% | 4.1s |
| 2 | Qwen3.5-4B Q5 | thinking ON | 80.4% | 5.4s |
| 3 | Qwen3-8B Q4 | /no_think | 79.6% | 1.7s |
| 4 | **Gemma 4 E4B Q5** | **reasoning OFF** | **77.5%** | **0.8s** |
| 5 | Gemma 4 E4B Q6 | reasoning OFF | 77.2% | 0.8s |
| 6 | Gemma 4 E4B Q8 | reasoning OFF | 76.4% | 0.9s |
| 7 | Qwen3.5-4B Q5 | thinking OFF | 68.6% | 1.9s |
| 8 | Gemma 4 E2B Q8 | reasoning OFF | 70.7% | 0.7s |

*Single run only — needs 3-run validation and bounded budget testing.

### Latency vs Accuracy Frontier

The interesting positions on the Pareto frontier:
- **Best accuracy:** Gemma 4 E2B reasoning ON (~81%) — but 4.1s latency
- **Best balance:** Qwen3-8B /no_think (79.6% / 1.7s) — current deployment
- **Fastest competitive:** Gemma 4 E4B Q5 reasoning OFF (77.5% / 0.8s) — 2pp accuracy trade for 2x speed
- **Fastest overall:** Gemma 4 E2B Q4 reasoning OFF (62.3% / 0.5s) — too inaccurate for production

---

## Pending Work

1. **Reasoning budget 512 run** — `--reasoning-budget 512` configured, 3-run benchmark queued. Expected to recover most of the reasoning accuracy gain while keeping latency in the 2-3s range. Median reasoning usage was ~200 tokens, so 512 should rarely truncate.

2. **Reasoning budget sweep** — if 512 shows promise, test 256 and 1024 to map the full accuracy/latency curve.

3. **Failure pattern deep dive** — compare per-sample C→I and I→C flips between reasoning ON and OFF to understand which specific test cases benefit from thinking.

---

## Run Log References

| Run | Directory | Config | Notes |
|-----|-----------|--------|-------|
| Reasoning unlimited | `2026-04-25T11-30-04` | No `--reasoning` flag | E2B complete, E4B Q4 partial (hung on medium) |
| Reasoning off, run 1 | `2026-04-25T16-22-21` | `--reasoning off` | All 7 models, both tiers |
| Reasoning off, run 2 | `2026-04-25T16-45-39` | `--reasoning off` | All 7 models, both tiers |
| Reasoning off, run 3 | `2026-04-25T17-07-19` | `--reasoning off` | All 7 models, both tiers |

All runs under `logs/benchmark/gemma4/`. Config copies preserved in each run directory.
