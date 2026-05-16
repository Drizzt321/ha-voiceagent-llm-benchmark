# HA Voice LLM Benchmark — Gemma 4 Reasoning Budget 256, April 2026

Follow-up benchmark of Google's Gemma 4 model family (E2B and E4B) with `--reasoning-budget 256` — a tighter thinking cap than the budget-512 runs. The goal was to determine whether halving the reasoning budget could bring latency closer to the Qwen3-8B baseline while preserving accuracy gains from reasoning.

**Conclusion: Not worth it.** Budget-256 trims tail latency (P90 down 37-44%) but median latency barely moves because most samples already think under 256 tokens. Meanwhile, accuracy drops 1-6pp vs budget-512, falling below Qwen3-8B on most models. The tighter budget cuts into productive reasoning, not just excess.

> **Note:** This is a single-run sample (1 run per model), not the standard 3-run averaged benchmark. The run was killed early after E2B results confirmed the hypothesis. All 7 models completed both tiers before termination. Results are directionally reliable but lack variance estimates.

## Top-Line Results

**Overall accuracy (small + medium tiers combined, 1 run, `--reasoning-budget 256`):**

| Model | Quant | Size | Combined | Small | Medium | Avg Lat | P90 Lat | vs Qwen3-8B | vs Budget-512 |
|-------|-------|------|:--------:|:-----:|:------:|:-------:|:-------:|:-----------:|:-------------:|
| **E4B** | **Q6_K** | **6.33 GB** | **80.4%** | 78.8% | 81.7% | 6.3s | 8.1s | +0.8pp | **-0.6pp** |
| E4B | Q4_K_M | 5.41 GB | 79.9% | 78.8% | 80.8% | 4.9s | 7.0s | +0.3pp | +0.6pp |
| E4B | Q8_0 | 8.03 GB | 78.8% | 78.8% | 78.8% | 6.4s | 8.7s | -0.8pp | 0.0pp |
| E4B | Q5_K_M | 5.82 GB | 77.2% | 76.2% | 77.9% | 5.3s | 7.6s | -2.4pp | -3.2pp |
| E2B | Q4_K_M | 3.46 GB | 76.6% | 80.0% | 74.0% | 3.6s | 4.6s | -3.0pp | **-6.0pp** |
| E2B | Q5_K_M | 3.66 GB | 76.6% | 81.2% | 73.1% | 4.0s | 5.0s | -3.0pp | +2.1pp |
| E2B | Q8_0 | 4.97 GB | 73.9% | 77.5% | 71.2% | 3.5s | 5.1s | -5.7pp | -4.4pp |
| -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| *Qwen3-8B (Iter4)* | *Q4_K_M* | *~5 GB* | *79.6%* | *~80%* | *~79%* | *1.7s* | *--* | *baseline* | *--* |

**Key findings:**

1. **Only E4B Q6_K and Q4_K_M remain above Qwen3-8B**, barely — at +0.8pp and +0.3pp respectively. Budget-512's clear winner (E4B Q6_K at 81.0%) drops to 80.4%, and E2B Q4's 82.6% collapses to 76.6%.

2. **E2B Q4_K_M took the hardest hit: -6.0pp vs budget-512.** This was the budget-512 star performer. It generated the most reasoning tokens (276 mean), so the 256-token cap truncates substantial productive thinking.

3. **Latency improvement is real but insufficient.** Mean latency drops 19-28% for E2B, 18-30% for E4B. But median barely moves — most samples were already thinking under 256 tokens. The wins are in the tail (P90 down 37-44%).

4. **Still 2-4x slower than Qwen3-8B.** The fastest competitive config (E4B Q4 at 79.9%, 4.9s) is still 2.9x Qwen's 1.7s. This is a hardware-bound gap, not a budget-tuning problem.

5. **Format quality held steady** — zero format_valid and zero hallucinated_tools failures, same as budget-512. Budget-256 doesn't cause degenerate outputs; it just produces less accurate reasoning.

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
- **Runs:** 1 (single run — killed early after confirming hypothesis)
- **Prompt:** Iteration 4 (F7 refusal + HassGetState preference), file: `configs/qwen3.5_f7_refusal.txt`
- **Context:** 22000 tokens (matching Qwen3-8B baseline)
- **Reasoning:** `--reasoning-budget 256` (llama.cpp state-machine sampler, caps thinking tokens at 256)

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

### Per-Tier Breakdown

| Model | Quant | Small Acc | Small Lat | Medium Acc | Medium Lat |
|-------|-------|:---------:|:---------:|:----------:|:----------:|
| E2B | Q4_K_M | 80.0% | 3.3s | 74.0% | 3.9s |
| E2B | Q5_K_M | 81.2% | 4.0s | 73.1% | 4.0s |
| E2B | Q8_0 | 77.5% | 3.5s | 71.2% | 3.5s |
| E4B | Q4_K_M | 78.8% | 4.8s | 80.8% | 5.0s |
| E4B | Q5_K_M | 76.2% | 5.0s | 77.9% | 5.5s |
| E4B | Q6_K | 78.8% | 6.1s | 81.7% | 6.4s |
| E4B | Q8_0 | 78.8% | 6.6s | 78.8% | 6.3s |

**Notable patterns:**
- **E2B degrades small->medium** as before (80.0% -> 74.0% for Q4), though less than reasoning-off. The 2.3B model still struggles with larger inventories even with reasoning help.
- **E4B is stable or improves small->medium** — Q6_K goes from 78.8% to 81.7%, same pattern as budget-512. The larger model uses reasoning effectively on entity-dense contexts.
- **Latency is more uniform within each model** — the tighter budget reduces variance between easy and hard samples.

### Latency Breakdown

| Model | Quant | Mean | Median | P90 | Max |
|-------|-------|:----:|:------:|:---:|:---:|
| E2B | Q4_K_M | 3.6s | 4.1s | 4.6s | 11.8s |
| E2B | Q5_K_M | 4.0s | 4.6s | 5.0s | 12.6s |
| E2B | Q8_0 | 3.5s | 4.1s | 5.1s | 12.0s |
| E4B | Q4_K_M | 4.9s | 5.6s | 7.0s | 27.9s |
| E4B | Q5_K_M | 5.3s | 6.8s | 7.6s | 19.5s |
| E4B | Q6_K | 6.3s | 7.5s | 8.1s | 28.7s |
| E4B | Q8_0 | 6.4s | 7.9s | 8.7s | 19.3s |

**Comparison vs budget-512 (run 1):**

| Model | Quant | B-512 Mean | B-256 Mean | Delta | B-512 P90 | B-256 P90 | Delta |
|-------|-------|:----------:|:----------:|:-----:|:---------:|:---------:|:-----:|
| E2B | Q4_K_M | 4.5s | 3.6s | **-19%** | 7.2s | 4.6s | **-37%** |
| E2B | Q5_K_M | 4.9s | 4.0s | -19% | 8.4s | 5.0s | -40% |
| E2B | Q8_0 | 4.8s | 3.5s | -28% | 9.0s | 5.1s | -44% |
| E4B | Q4_K_M | 6.6s | 4.9s | -26% | 10.9s | 7.0s | -36% |
| E4B | Q5_K_M | 6.2s | 5.3s | -15% | 11.7s | 7.6s | -35% |
| E4B | Q6_K | 7.7s | 6.3s | -18% | 14.2s | 8.1s | -43% |
| E4B | Q8_0 | 9.1s | 6.4s | -30% | 15.0s | 8.7s | -42% |

The tail compression is significant — P90 drops 35-44% across the board. Mean drops 15-30%. But the median is stubbornly close because most samples don't reach the 256-token reasoning cap.

### Output Token Comparison

| Model | Quant | B-512 Mean Tokens | B-256 Mean Tokens | Reduction |
|-------|-------|:-----------------:|:-----------------:|:---------:|
| E2B | Q4_K_M | 276 | 228 | -17% |
| E2B | Q5_K_M | 275 | 228 | -17% |
| E2B | Q8_0 | 258 | 192 | -26% |
| E4B | Q4_K_M | 253 | 194 | -23% |
| E4B | Q5_K_M | 223 | 197 | -12% |
| E4B | Q6_K | 265 | 217 | -18% |
| E4B | Q8_0 | 254 | 212 | -17% |

Mean output tokens drop 12-26%, confirming the budget cap is actively truncating reasoning. E2B Q4 drops from 276 to 228 — this model was using the most reasoning tokens, which explains its 6pp accuracy loss.

---

## Failure Analysis

### Dimension Breakdown (all models, budget-256)

| Dimension | Failures | % of All Failures |
|-----------|:--------:|:-----------------:|
| args | 229 | 79.5% |
| call_count | 174 | 60.4% |
| tool_name | 164 | 56.9% |
| response_type | 127 | 44.1% |
| format_valid | 0 | 0.0% |
| no_hallucinated_tools | 0 | 0.0% |

Total: 1288 samples, 288 failures (22.4% failure rate).

**Comparison across reasoning modes (per-run failure rate):**

| Mode | Samples/Run | Failures | Rate |
|------|:-----------:|:--------:|:----:|
| Reasoning OFF | 1288 | 352 | 27.3% |
| Budget-512 | 1288 | 267 | 20.7% |
| Budget-256 | 1288 | 288 | 22.4% |
| Qwen3-8B | 552 | 116 | 21.0% |

Budget-256 sits between reasoning-off and budget-512, closer to Qwen3-8B's failure rate but without Qwen's latency advantage.

**Positive signals (unchanged from budget-512):**
- **Zero format_valid failures** — Gemma 4 produces well-formed tool call JSON regardless of reasoning budget
- **Zero hallucinated tools** — never invents tool names

### Match Quality Distribution

| Quality | Count | % |
|---------|:-----:|:-:|
| optimal | 1048 | 81.4% |
| acceptable | 206 | 16.0% |
| equivalent | 34 | 2.6% |
| degraded | 0 | <0.1% |

Slightly lower optimal rate (81.4%) vs budget-512 (83.7%). When budget-256 gets the right answer, it's slightly less precise.

### Consistently Failing Samples

These samples fail across 5+ of 7 models — structural failures that reasoning budget doesn't fix:

| Failed By | Sample | Category |
|:---------:|--------|----------|
| 7/7 | implicit-leaving | Multi-call implicit routine |
| 7/7 | implicit-good_morning (both tiers) | Multi-call implicit routine |
| 7/7 | implicit-movie_time | Multi-call implicit routine |
| 7/7 | implicit-goodnight | Multi-call implicit routine |
| 7/7 | light-color_temp (both tiers) | color_temp arg format |
| 7/7 | light-unavailable (both tiers) | Unavailable entity handling |
| 7/7 | edge-unavailable_light (both tiers) | Unavailable entity handling |
| 7/7 | light-kitchen-area (both tiers) | Area-based control |
| 7/7 | multi-cover_light_bedroom | Multi-call explicit |
| 7/7 | media_player-living_room_tv (medium) | State query format |
| 7/7 | weather_forecast (small) | Forecast response format |
| 7/7 | multi-lock_lights (medium) | Multi-call explicit |

These are the same structural failure categories seen in budget-512 — implicit routines, color_temp formatting, unavailable entity detection, and multi-action sequences. These require prompt engineering or fine-tuning, not more reasoning tokens.

---

## Four-Mode Comparison

| Mode | Best Model | Combined | Avg Lat | Latency vs Qwen | Accuracy vs Qwen |
|------|-----------|:--------:|:-------:|:---------------:|:----------------:|
| **Qwen3-8B** | Q4_K_M | **79.6%** | **1.7s** | **1.0x** | **baseline** |
| Reasoning OFF | E4B Q5 | 78.8% | 1.1s | 0.7x | -0.8pp |
| Budget-512 | E4B Q6_K | 81.0% | 8.7s | 5.1x | +1.4pp |
| Budget-256 | E4B Q6_K | 80.4% | 6.3s | 3.7x | +0.8pp |

Budget-256 lands in an uncomfortable middle: not fast enough to justify switching from Qwen3-8B, and not accurate enough to justify the latency over budget-512. The accuracy-latency Pareto frontier has two viable points — reasoning-off (fast, slightly less accurate) and budget-512 (slow, most accurate). Budget-256 doesn't improve either frontier.

---

## Conclusions

1. **Budget-256 is not worth deploying.** It loses accuracy vs budget-512 without meaningfully closing the latency gap to Qwen3-8B. The remaining 2-4x latency gap is decode-speed-bound (GTX 1080 memory bandwidth), not reasoning-token-bound.

2. **Reasoning budget tuning has diminishing returns below 512.** The median sample uses ~200 reasoning tokens. Budget-512 captures virtually all reasoning (max observed was 494 in unlimited runs). Budget-256 starts cutting into the 200-256 token range where reasoning is productive.

3. **The Gemma 4 reasoning story on GTX 1080 is settled:**
   - Budget-512 E4B Q6_K is the most accurate Gemma 4 config at 81.0%, but at 5.1x Qwen's latency
   - Reasoning-off E4B Q5 is the fastest competitive config at 78.8% / 1.1s, but slightly below Qwen
   - No reasoning budget setting bridges the gap — the bottleneck is hardware decode speed

4. **Qwen3-8B Q4_K_M remains the deployment choice** on GTX 1080 hardware. It offers the best accuracy/latency balance at 79.6% / 1.7s. Gemma 4 with reasoning is genuinely more capable, but needs faster hardware (or speculative decoding, or a more efficient architecture) to realize that advantage in a voice pipeline.

---

## Log Locations

- **Budget-256 (this report):** `logs/benchmark/gemma4/2026-04-26T09-10-01/`
- **Budget-512 (3 runs):** `logs/benchmark/gemma4/2026-04-25T17-38-33/`, `2026-04-25T20-00-53/`, `2026-04-25T22-29-45/`
- **Reasoning OFF (3 runs):** `logs/benchmark/gemma4/2026-04-25T16-22-21/`, `2026-04-25T16-45-39/`, `2026-04-25T17-07-19/`
- **Config:** `configs/gemma4.yaml` (reasoning-budget 256)
