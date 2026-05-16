# HA Voice LLM Benchmark — Gemma 4 Reasoning Budget 512, April 2026

Follow-up benchmark of Google's Gemma 4 model family (E2B and E4B) with `--reasoning-budget 512` — a bounded thinking mode that caps reasoning tokens at 512. This run bridges the gap between the two extremes tested previously: reasoning off (fast, lower accuracy) and unlimited reasoning (accurate, too slow).

## Top-Line Results

**Overall accuracy (averaged across small + medium tiers, 3 runs each, `--reasoning-budget 512`):**

| Model | Quant | Size | Combined | Small | Medium | Avg Lat | P95 Lat | vs Qwen3-8B | vs Reasoning Off |
|-------|-------|------|:--------:|:-----:|:------:|:-------:|:-------:|:-----------:|:----------------:|
| **E4B** | **Q6_K** | **6.33 GB** | **81.0% +/-1.6** | 80.4% | 81.4% | 8.7s | 15.0s | **+1.4pp** | **+3.8pp** |
| E4B | Q8_0 | 8.03 GB | 79.9% +/-1.1 | 80.8% | 79.2% | 9.1s | 16.0s | +0.3pp | +3.5pp |
| E4B | Q5_K_M | 5.82 GB | 79.7% +/-0.8 | 78.8% | 80.4% | 6.6s | 13.7s | +0.1pp | +2.2pp |
| E4B | Q4_K_M | 5.41 GB | 79.3% +/-2.7 | 79.2% | 79.5% | 6.4s | 12.8s | -0.3pp | +3.9pp |
| E2B | Q4_K_M | 3.46 GB | 80.1% +/-2.3 | 82.1% | 78.5% | 4.3s | 8.2s | +0.5pp | +17.8pp |
| E2B | Q8_0 | 4.97 GB | 78.6% +/-1.1 | 82.1% | 76.0% | 4.6s | 9.3s | -1.0pp | +7.9pp |
| E2B | Q5_K_M | 3.66 GB | 76.3% +/-2.3 | 79.6% | 73.7% | 4.8s | 9.2s | -3.3pp | +7.6pp |
| -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| *Qwen3-8B (Iter4)* | *Q4_K_M* | *~5 GB* | *79.6%* | *~80%* | *~79%* | *1.7s* | *--* | *baseline* | *--* |

**Key findings:**

1. **E4B Q6_K with budget-512 is the first Gemma 4 config to meaningfully beat the Qwen3-8B baseline** at 81.0% combined (+1.4pp). However, it does so at 8.7s average latency (5.1x slower than Qwen3-8B). For a voice assistant, this is too slow to be practical on current hardware.

2. **Budget-512 recovers the reasoning accuracy gains without timeouts.** All 3 runs completed cleanly with zero hangs (contrast: unlimited reasoning hung on E4B medium). The 512-token cap is well-calibrated — prior unlimited runs showed median ~200 tokens and max ~494.

3. **Reasoning transforms E2B from unusable to competitive.** E2B Q4_K_M jumps from 62.3% (off) to 80.1% (budget-512) — an 18pp gain. At 4.3s latency, it's the fastest Gemma 4 config that matches Qwen3-8B, but still 2.5x slower.

4. **E4B accuracy is flat across quants with reasoning too** — Q4 through Q8 spans 79.3% to 81.0% (1.7pp), same pattern as reasoning-off. The Q6_K sweet spot is slightly higher here than Q5_K_M was with reasoning off.

5. **Latency cost of reasoning is 4-9x** vs reasoning-off:
   - E2B: 0.6s (off) -> 4.3-4.8s (budget-512) = ~7x
   - E4B: 0.8s (off) -> 6.4-9.1s (budget-512) = ~8-11x

6. **No Gemma 4 configuration is worth deploying over Qwen3-8B on this hardware.** The only configs that beat Qwen3-8B accuracy (E4B Q6_K, E2B Q4) do so at 3-5x the latency. Reasoning-off configs are faster but 2-4pp less accurate.

---

## Benchmark Setup

### Hardware

- **GPU:** NVIDIA GeForce GTX 1080 (8 GB VRAM)
- **Host:** darkllama bhyve VM on FreeBSD, Debian testing
- **CPU:** AMD Ryzen 7 3800X 8-Core Processor (4 cores allocated)
- **RAM:** 7.8 GiB
- **Inference:** llama.cpp build 8931, fully GPU-offloaded (`ngl=99`)

### Test Configuration

- **Tiers:** Small (34 entities, 80 test cases) and Medium (88 entities, 104 test cases)
- **Scoring:** Strict multi-dimensional (all 6 dimensions must pass)
- **Runs:** 3 per model/tier combination
- **Prompt:** Iteration 4 (F7 refusal + HassGetState preference), file: `configs/qwen3.5_f7_refusal.txt`
- **Context:** 22000 tokens (matching Qwen3-8B baseline)
- **Reasoning:** `--reasoning-budget 512` (llama.cpp state-machine sampler, caps thinking tokens at 512)

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

## Detailed Results

### Per-Tier Breakdown (3-Run Average)

| Model | Quant | Small Acc | Small Lat | Medium Acc | Medium Lat | Sm P95 | Md P95 |
|-------|-------|:---------:|:---------:|:----------:|:----------:|:------:|:------:|
| E2B | Q4_K_M | 82.1% | 4.1s | 78.5% | 4.5s | 8.2s | 8.2s |
| E2B | Q5_K_M | 79.6% | 4.7s | 73.7% | 5.0s | 9.2s | 9.2s |
| E2B | Q8_0 | 82.1% | 4.6s | 76.0% | 4.6s | 9.3s | 9.4s |
| E4B | Q4_K_M | 79.2% | 6.2s | 79.5% | 6.6s | 12.8s | 12.8s |
| E4B | Q5_K_M | 78.8% | 6.2s | 80.4% | 7.0s | 13.7s | 13.7s |
| E4B | Q6_K | 80.4% | 7.5s | 81.4% | 9.8s | 14.8s | 15.1s |
| E4B | Q8_0 | 80.8% | 8.1s | 79.2% | 10.0s | 15.8s | 16.2s |

**Notable patterns:**
- **E2B still degrades small->medium** (82.1% -> 76.0% for Q8_0), though the gap is much smaller with reasoning than without (was 75% -> 67.3% reasoning-off). Reasoning partially compensates for the 2.3B model's difficulty with larger inventories.
- **E4B is stable or improves small->medium** — Q5_K_M goes from 78.8% to 80.4%, Q6_K from 80.4% to 81.4%. The reasoning + larger parameter count combination handles entity-dense contexts well.
- **P95 latency is concerning** — at 13-16s for E4B, the tail of the distribution would feel very slow for voice interaction. E2B is better at 8-9s P95.

### Run-to-Run Variance

| Model | Quant | Run 1 | Run 2 | Run 3 | Stdev |
|-------|-------|:-----:|:-----:|:-----:|:-----:|
| E2B Q4_K_M | combined | 82.6% | 78.3% | 79.3% | +/-2.3 |
| E2B Q5_K_M | combined | 74.5% | 78.8% | 75.5% | +/-2.3 |
| E2B Q8_0 | combined | 78.3% | 77.7% | 79.9% | +/-1.1 |
| E4B Q4_K_M | combined | 79.3% | 76.6% | 82.1% | +/-2.7 |
| E4B Q5_K_M | combined | 80.4% | 78.8% | 79.9% | +/-0.8 |
| E4B Q6_K | combined | 81.0% | 79.3% | 82.6% | +/-1.6 |
| E4B Q8_0 | combined | 78.8% | 79.9% | 81.0% | +/-1.1 |

Variance is slightly higher than reasoning-off runs (typical +/-1.5 vs +/-1.0). E4B Q4_K_M has the widest spread at +/-2.7pp. This is expected — reasoning introduces stochastic thinking chains that add run-to-run variability.

### Latency Breakdown

| Model | Quant | Min | Mean | Median | P95 | Max |
|-------|-------|:---:|:----:|:------:|:---:|:---:|
| E2B | Q4_K_M | 0.41s | 4.3s | 4.0s | 8.2s | 13.3s |
| E2B | Q5_K_M | 0.45s | 4.8s | 4.7s | 9.1s | 15.6s |
| E2B | Q8_0 | 0.36s | 4.5s | 4.6s | 9.2s | 15.7s |
| E4B | Q4_K_M | 0.26s | 6.5s | 6.3s | 12.7s | 50.3s |
| E4B | Q5_K_M | 0.45s | 6.9s | 6.9s | 13.8s | 55.6s |
| E4B | Q6_K | 0.64s | 7.8s | 8.2s | 15.0s | 18.9s |
| E4B | Q8_0 | 0.46s | 9.8s | 8.3s | 15.9s | 334.7s |

**Outlier note:** E4B Q8_0 has a 334.7s max in one medium sample (run 3) — a single sample that likely hit a reasoning chain near or at the 512-token cap combined with slow decode at Q8 precision. E4B Q4 and Q5 also have 50s+ outliers. These are rare but indicate that even budget-512 can produce unexpectedly long generation times on complex prompts with the larger E4B model. The E2B models have clean latency distributions with no extreme outliers.

### Per-Model Wall Time (Run 3)

| Model | Wall Time (both tiers) |
|-------|:---------------------:|
| E2B Q4_K_M | 13m |
| E2B Q5_K_M | 15m |
| E2B Q8_0 | 14m |
| E4B Q4_K_M | 20m |
| E4B Q5_K_M | 21m |
| E4B Q6_K | 24m |
| E4B Q8_0 | 31m |
| **Total (all 7 models)** | **~2h 26m** |

---

## Failure Analysis

### Dimension Breakdown (3-run total, all models, budget-512)

| Dimension | Failures | % of All Failures |
|-----------|:--------:|:-----------------:|
| args | 657 | 82.0% |
| call_count | 474 | 59.2% |
| tool_name | 489 | 61.0% |
| response_type | 347 | 43.3% |
| format_valid | 0 | 0.0% |
| no_hallucinated_tools | 0 | 0.0% |

Total: 3864 samples, 801 failures (20.7% failure rate).

**Comparison with reasoning-off:** The failure rate dropped from 27.4% (reasoning off) to 20.7% (budget-512), a 24% relative reduction. The `response_type` dimension saw the largest improvement — from 58.0% to 43.3% of failures — indicating reasoning helps the model correctly distinguish between tool-call and text-only responses.

**Positive signals (unchanged):**
- **Zero format_valid failures** — Gemma 4 produces well-formed tool call JSON in all reasoning modes
- **Zero hallucinated tools** — never invents tool names, even while reasoning

### Match Quality Distribution

| Quality | Count | % |
|---------|:-----:|:-:|
| optimal | 3236 | 83.7% |
| acceptable | 519 | 13.4% |
| equivalent | 108 | 2.8% |
| degraded | 1 | <0.1% |

The high optimal rate (83.7%) indicates that correct answers are strongly correct — not scraping by on fallback matches.

### Most Consistently Failing Test Cases

These test cases fail in 18+ of 21 model-runs (7 models x 3 runs):

| Test Case | Fails | Category | Pattern |
|-----------|:-----:|----------|---------|
| HassLightSet-light-color_temp (both) | 21/21 | F4/F5 | Uses `temperature` key instead of `color_temp` |
| HassTurnOn-light-unavailable (both) | 21/21 | F7 | Calls tool on unavailable entity instead of refusing |
| text-edge-unavailable_light (both) | 21/21 | F7 | Same unavailable entity detection failure |
| implicit-good_morning (both) | 21/21 | F6 | Cannot generate multi-call routine |
| limit-weather_forecast (both) | 21/21 | F7 | Calls tool instead of text-only response |
| implicit-goodnight (medium) | 21/21 | F6 | Cannot generate multi-call routine |
| implicit-leaving (medium) | 21/21 | F6 | Cannot generate multi-call routine |
| implicit-movie_time (medium) | 21/21 | F6 | Cannot generate multi-call routine |
| HassGetState-media_player (medium) | 21/21 | F2 | Over-calls (queries both TV and soundbar) |
| multi-office_all_off (small) | 21/21 | F6 | Multi-call — model undercalls |
| HassTurnOff-light-kitchen-area (small) | 20/21 | F6/F8 | Enumerates individual lights instead of area |
| multi-lock_lights (medium) | 19/21 | F6 | Multi-call — model undercalls |

**These are the same structural failures observed in reasoning-off and in Qwen3-8B.** Reasoning does not solve:
- Multi-call implicit routines (good_morning, goodnight, etc.)
- Unavailable entity detection (model ignores `unavailable` state)
- Complex light attribute arguments (color_temp, RGBW)
- Area-based vs entity-based control disambiguation

---

## Three-Mode Comparison

### Accuracy Across Reasoning Modes (best config per model family)

| Config | Combined Acc | Avg Latency | Latency vs Qwen3-8B |
|--------|:----------:|:-----------:|:--------------------:|
| Qwen3-8B Q4 /no_think | 79.6% | 1.7s | baseline |
| E4B Q6_K budget-512 | **81.0%** | 8.7s | 5.1x slower |
| E2B Q4 budget-512 | 80.1% | 4.3s | 2.5x slower |
| E2B Q4 unlimited* | ~81% | 4.1s | 2.4x slower |
| E4B Q5 reasoning off | 77.5% | 0.8s | 2.1x faster |
| E2B Q8 reasoning off | 70.7% | 0.7s | 2.4x faster |

*Unlimited = 1-run only, not 3-run averaged.

### Reasoning Mode Impact by Model (budget-512 vs off, 3-run averages)

| Model | Off | Budget-512 | Delta | Latency Off | Latency 512 | Slowdown |
|-------|:---:|:----------:|:-----:|:-----------:|:-----------:|:--------:|
| E2B Q4 | 62.3% | 80.1% | **+17.8pp** | 0.6s | 4.3s | 7.2x |
| E2B Q5 | 68.7% | 76.3% | +7.6pp | 0.7s | 4.8s | 6.9x |
| E2B Q8 | 70.7% | 78.6% | +7.9pp | 0.7s | 4.6s | 6.6x |
| E4B Q4 | 75.4% | 79.3% | +3.9pp | 0.8s | 6.4s | 8.0x |
| E4B Q5 | 77.5% | 79.7% | +2.2pp | 1.0s | 6.6s | 6.6x |
| E4B Q6 | 77.2% | 81.0% | +3.8pp | 0.9s | 8.7s | 9.7x |
| E4B Q8 | 76.4% | 79.9% | +3.5pp | 1.0s | 9.1s | 9.1x |

**Pattern:** Reasoning helps smaller models more dramatically. E2B gains 8-18pp while E4B gains 2-4pp. This confirms that reasoning compensates for model capacity limitations — the 2.3B E2B model "thinks its way" to performance that its raw parameters can't deliver.

The flip side: the accuracy/latency exchange rate is poor. E4B Q6_K gains 3.8pp accuracy at a cost of 7.8s additional latency per request. At ~0.5pp per second of latency added, this is not a favorable trade for interactive voice use.

---

## Comparison with All Tested Models

### Accuracy Ranking (combined small+medium, best config per model, 3-run averaged where available)

| Rank | Model | Config | Combined Acc | Avg Latency |
|------|-------|--------|:----------:|:-----------:|
| 1 | **Gemma 4 E4B Q6_K** | **budget-512** | **81.0%** | **8.7s** |
| 2 | Gemma 4 E2B Q4 | budget-512 | 80.1% | 4.3s |
| 3 | Qwen3.5-4B Q5 | thinking ON | 80.4% | 5.4s |
| 4 | **Qwen3-8B Q4** | **/no_think** | **79.6%** | **1.7s** |
| 5 | Gemma 4 E4B Q8 | budget-512 | 79.9% | 9.1s |
| 6 | Gemma 4 E4B Q5 | budget-512 | 79.7% | 6.6s |
| 7 | Gemma 4 E4B Q5 | reasoning off | 77.5% | 0.8s |
| 8 | Gemma 4 E4B Q6 | reasoning off | 77.2% | 0.8s |
| 9 | Gemma 4 E2B Q8 | budget-512 | 78.6% | 4.6s |

### Deployment Recommendation

For a voice assistant with interactive latency requirements, **Qwen3-8B Q4_K_M remains the deployment choice.** It sits at the Pareto frontier — no other model on this hardware achieves both higher accuracy AND lower latency. The positions are:

- **Want faster + slightly worse:** E4B Q5 reasoning off (77.5%, 0.8s) — viable if latency is critical and 2pp accuracy loss is acceptable.
- **Want more accurate + much slower:** E4B Q6_K budget-512 (81.0%, 8.7s) — only viable if better compute brings latency down to ~2s, or if the use case tolerates 8s+ response times.
- **Best compute upgrade path:** With faster hardware (e.g., RTX PRO 4000), E4B Q6_K budget-512 could potentially reach <2s latency and become the best overall option. The model has the accuracy; it just lacks the decode speed on current hardware.

---

## Pending Work

1. **Reasoning budget 256 run** — test whether a tighter cap still captures most of the accuracy gain with lower latency. The median reasoning usage was ~200 tokens, so 256 may truncate meaningful reasoning on complex samples.

2. **Per-sample flip analysis** — compare individual sample outcomes across all three modes (off / budget-512 / unlimited) to identify which specific test cases benefit from reasoning and which are reasoning-invariant.

3. **Prompt engineering for reasoning mode** — the current prompt was optimized for Qwen3-8B without thinking. A Gemma-4-specific prompt that guides the reasoning chain could improve accuracy further.

---

## Run Log References

| Run | Directory | Config | Notes |
|-----|-----------|--------|-------|
| Budget-512, run 1 | `2026-04-25T17-38-33` | `--reasoning-budget 512` | All 7 models, both tiers, 2h 22m |
| Budget-512, run 2 | `2026-04-25T20-00-53` | `--reasoning-budget 512` | All 7 models, both tiers, 2h 29m |
| Budget-512, run 3 | `2026-04-25T22-29-45` | `--reasoning-budget 512` | All 7 models, both tiers, 2h 26m |
| Reasoning off, runs 1-3 | `2026-04-25T16-22-21` to `2026-04-25T17-07-19` | `--reasoning off` | Baseline comparison |
| Unlimited reasoning | `2026-04-25T11-30-04` | No `--reasoning` flag | E2B complete, E4B partial |

All runs under `logs/benchmark/gemma4/`. Config copies preserved in each run directory.
Total benchmark wall time for budget-512 3-run set: ~7h 17m.
