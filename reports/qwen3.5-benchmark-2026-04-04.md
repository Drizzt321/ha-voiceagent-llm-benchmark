# HA Voice LLM Benchmark — Qwen3.5 Model Evaluation, April 2026

First benchmark of the Qwen3.5 model family (9B and 4B) for Home Assistant voice intent processing, comparing thinking vs non-thinking modes against the established Qwen3-8B baseline.

## Top-Line Results

**Overall accuracy (averaged across small + medium tiers, 3 runs each):**

| Model | Quant | Thinking | Accuracy | Avg Latency | vs Qwen3-8B Iter4 |
|-------|-------|----------|:--------:|:-----------:|:------------------:|
| **Qwen3.5-4B** | Q5_K_M | **on** | **80.4%** | 5.4s | +0.8pp |
| **Qwen3.5-4B** | Q8_0 | **on** | 76.7% | 6.3s | -2.9pp |
| Qwen3.5-4B | Q5_K_M | off | 68.6% | 1.9s | -11.0pp |
| Qwen3.5-4B | Q8_0 | off | 66.9% | 1.9s | -12.7pp |
| Qwen3.5-9B | Q3_K_M | on | 66.8% | 8.2s | -12.8pp |
| Qwen3.5-9B | Q3_K_M | off | 67.1% | 2.7s | -12.5pp |
| — | — | — | — | — | — |
| *Qwen3-8B (Iter4)* | *Q4_K_M* | *off (/no_think)* | *79.6%* | *1.7s* | *baseline* |

**Key findings:**

1. **Qwen3.5-4B Q5_K_M with thinking is the surprise star** — 80.4% overall, slightly beating the Qwen3-8B baseline despite being half the parameter count. It achieves 97% on state queries (small) vs 80% for Qwen3-8B. Thinking mode is essential for this model.

2. **Qwen3.5-9B at Q3_K_M is disappointing** — the aggressive quantization (Q3_K_M needed to fit in 8GB VRAM) likely cripples it. At 66-69% it's well below the Qwen3-8B baseline and even below the 4B model with thinking enabled.

3. **Thinking mode is critical for Qwen3.5** — unlike Qwen3 where thinking hurt performance, Qwen3.5 gains +12-15pp from thinking on the 4B models. The 9B model shows a mixed effect (helps small, hurts medium).

4. **The latency cost of thinking is ~3x** — 4B thinking runs at 5-6s/sample vs 1.9s without. This is much better than Qwen3's 6-9x penalty, but still a real production trade-off.

5. **Q5_K_M consistently outperforms Q8_0 on the 4B model** — surprising but consistent across all runs. The imatrix-guided Q5 quantization may actually help regularize outputs.

---

## Benchmark Setup

### Hardware

- **GPU:** NVIDIA GeForce GTX 1080 (8 GB VRAM)
- **CPU:** AMD Ryzen 7 3800X (4 cores allocated to VM)
- **RAM:** 7.8 GiB
- **Inference:** llama.cpp server build 8366, fully GPU-offloaded (`ngl=99`)

### Test Configuration

- **Tiers:** Small (34 entities, 80 test cases) and Medium (88 entities, 104 test cases)
- **Scoring:** Strict multi-dimensional (all dimensions must pass)
- **Runs:** 3 per model/config/tier combination
- **Prompt:** Iteration 4 (F7 refusal) without `/no_think` (Qwen3.5 doesn't support it)
- **Thinking control:** `--reasoning off` server flag for non-thinking mode

### Models Tested

| Model | HF Repo | Quant | File Size | Context | Thinking |
|-------|---------|-------|-----------|---------|----------|
| Qwen3.5-9B | bartowski/Qwen_Qwen3.5-9B-GGUF | Q3_K_M | ~4.9 GB | 22000 | on / off |
| Qwen3.5-4B | bartowski/Qwen_Qwen3.5-4B-GGUF | Q5_K_M | ~3.3 GB | 22000 | on / off |
| Qwen3.5-4B | bartowski/Qwen_Qwen3.5-4B-GGUF | Q8_0 | ~4.5 GB | 22000 | on / off |

### Prompt

Iteration 4 prompt (F7 refusal line, no `/no_think`):
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

## Detailed Results by Tier

### Small Tier (34 entities, 80 test cases)

| Model | Thinking | Accuracy | Latency | F2 | F4 | F5 | F7 |
|-------|----------|:--------:|:-------:|:--:|:--:|:--:|:--:|
| **4B Q5** | **on** | **83.3% ± 0.7%** | 5.3s | 4.3 | 7.3 | 5.0 | 6.7 |
| 4B Q8 | on | 78.8% ± 1.2% | 6.0s | 6.3 | 10.7 | 6.0 | 8.0 |
| 4B Q5 | off | 71.2% ± 3.8% | 1.8s | 10.7 | 12.7 | 6.7 | 14.3 |
| 4B Q8 | off | 69.2% ± 2.6% | 1.9s | 14.0 | 15.7 | 5.3 | 17.0 |
| 9B Q3 | on | 69.6% ± 3.6% | 8.0s | 12.7 | 17.3 | 12.7 | 11.0 |
| 9B Q3 | off | 65.4% ± 1.9% | 2.6s | 13.7 | 19.3 | 11.0 | 14.3 |
| *Qwen3-8B* | *off* | *84.6% ± 0.7%* | *1.5s* | *2.0* | *3.3* | *0* | *6.3* |

### Medium Tier (88 entities, 104 test cases)

| Model | Thinking | Accuracy | Latency | F2 | F4 | F5 | F7 |
|-------|----------|:--------:|:-------:|:--:|:--:|:--:|:--:|
| **4B Q5** | **on** | **77.9% ± 1.0%** | 5.5s | 10.7 | 16.0 | 10.7 | 10.0 |
| 4B Q8 | on | 75.0% ± 3.8% | 6.6s | 15.3 | 17.0 | 10.7 | 14.3 |
| 9B Q3 | off | 68.9% ± 2.2% | 2.7s | 17.0 | 21.7 | 14.3 | 16.0 |
| 4B Q5 | off | 66.3% ± 1.0% | 1.9s | 19.0 | 22.0 | 9.7 | 21.7 |
| 4B Q8 | off | 65.1% ± 1.5% | 2.0s | 21.7 | 24.7 | 8.3 | 23.0 |
| 9B Q3 | on | 64.4% ± 3.5% | 8.3s | 24.3 | 29.0 | 13.3 | 20.3 |
| *Qwen3-8B* | *off* | *74.7% ± 0.6%* | *1.9s* | *2.7* | *7.7* | *1.0* | *10.7* |

---

## Thinking vs Non-Thinking Impact

| Model | Tier | No-Think | Think | Delta | Latency Delta |
|-------|------|:--------:|:-----:|:-----:|:-------------:|
| 4B Q5 | small | 71.2% | **83.3%** | **+12.1pp** | 1.8s → 5.3s (2.9×) |
| 4B Q5 | medium | 66.3% | **77.9%** | **+11.6pp** | 1.9s → 5.5s (2.9×) |
| 4B Q8 | small | 69.2% | **78.8%** | **+9.6pp** | 1.9s → 6.0s (3.2×) |
| 4B Q8 | medium | 65.1% | **75.0%** | **+9.9pp** | 2.0s → 6.6s (3.3×) |
| 9B Q3 | small | 65.4% | **69.6%** | **+4.2pp** | 2.6s → 8.0s (3.1×) |
| 9B Q3 | medium | **68.9%** | 64.4% | **-4.5pp** | 2.7s → 8.3s (3.1×) |

**Thinking helps the 4B models dramatically (+10-12pp)** but has a mixed effect on the 9B Q3 model (+4pp small, -4pp medium). The 9B at Q3_K_M quantization may be too degraded for the thinking process to be reliable — the model thinks, but thinks poorly at this quant level.

---

## Per-Type Accuracy — Best Configs vs Qwen3-8B Baseline

### Small Tier (types where Qwen3.5-4B Q5 Think differs from Qwen3-8B)

| Intent Type | n | Qwen3-8B (Iter4) | 4B-Q5 Think | 4B-Q5 NoThink |
|-------------|:-:|:----------------:|:-----------:|:-------------:|
| state_query | 10 | 80% | **97%** ↑ | 80% |
| out_of_scope | 4 | 75% | **83%** ↑ | 33% ↓ |
| climate_control | 3 | 100% | **100%** = | 67% ↓ |
| disambiguation | 4 | 83% | **83%** = | 58% ↓ |
| multi_action | 2 | 100% | **100%** ↑ | 67% ↓ |
| cover_control | 3 | 100% | 89% ↓ | 78% ↓ |
| media_control | 11 | 91% | 85% ↓ | 94% |
| light_control | 6 | 78% | 67% ↓ | 78% |
| implicit_intent | 3 | 33% | 22% | 11% |

### Medium Tier

| Intent Type | n | Qwen3-8B (Iter4) | 4B-Q5 Think | 4B-Q5 NoThink |
|-------------|:-:|:----------------:|:-----------:|:-------------:|
| state_query | 18 | 70% | **80%** ↑ | 52% ↓ |
| utility | 4 | 92% | **100%** ↑ | 58% ↓ |
| out_of_scope | 4 | 75% | **75%** = | 25% ↓ |
| edge_case | 5 | 60% | **60%** = | 33% ↓ |
| climate_control | 4 | 100% | 83% ↓ | 83% ↓ |
| cover_control | 4 | 100% | **100%** = | 83% ↓ |
| media_control | 11 | 85% | **94%** ↑ | 94% |
| implicit_intent | 6 | 17% | 22% | 0% ↓ |

**State query is the standout:** 4B-Q5 Think hits 97% small / 80% medium vs Qwen3-8B's 80% / 70%. The thinking process helps the model reason through entity matching for sensor queries.

**Non-thinking mode collapses on several types** — out_of_scope drops to 25-33%, state_query to 52-80%, utility to 50-58%. Without thinking, the 4B model can't reliably decide when to call tools vs respond with text.

---

## Failure Pattern Analysis

### Dominant Patterns — 4B Q5 Think (best config)

| Pattern | Small | Medium | Notes |
|---------|:-----:|:------:|-------|
| F7 (response type) | 6.7 | 10.0 | Comparable to Qwen3-8B (6.3 / 10.7) |
| F4 (missing arg) | 7.3 | 16.0 | Higher than Qwen3-8B (3.3 / 7.7) |
| F5 (extra args) | 5.0 | 10.7 | Higher than Qwen3-8B (0 / 1.0) |
| F2 (wrong tool) | 4.3 | 10.7 | Higher than Qwen3-8B (2.0 / 2.7) |
| F1 (entity ID) | 0.3 | 2.0 | Low — similar to Qwen3-8B (0.7 / 4.3) |

**F4 and F5 are the gap** — Qwen3.5-4B produces more argument errors (missing keys, extra keys) than Qwen3-8B. The F7 refusal behavior is comparable, confirming the prompt instruction works across model families.

### F7 Direction Breakdown — 4B Q5 Think

| Direction | Small | Medium |
|-----------|:-----:|:------:|
| Didn't-call-when-should | 2.7 | 5.3 |
| Called-when-shouldn't | 4.0 | 4.7 |

Similar distribution to Qwen3-8B. The F7 refusal line is effective on Qwen3.5 as well.

---

## Latency Analysis

| Model | Thinking | Small | Medium | Notes |
|-------|----------|:-----:|:------:|-------|
| 4B Q5 | off | 1.83s | 1.92s | Fastest config |
| 4B Q8 | off | 1.87s | 1.99s | Slightly slower than Q5 |
| 9B Q3 | off | 2.59s | 2.74s | Slower due to larger model |
| 4B Q5 | on | 5.27s | 5.45s | 2.9× thinking penalty |
| 4B Q8 | on | 6.02s | 6.57s | 3.2× thinking penalty |
| 9B Q3 | on | 7.96s | 8.34s | 3.1× thinking penalty |
| *Qwen3-8B* | *off* | *1.51s* | *1.93s* | *Baseline reference* |

The thinking penalty is consistently ~3× across all Qwen3.5 models — much more predictable than Qwen3's 6-9× with highly variable thinking lengths. Max latencies peak at 14-34s for thinking models.

---

## Q5_K_M vs Q8_0 Comparison (4B model)

| Metric | Q5 Think | Q8 Think | Q5 NoThink | Q8 NoThink |
|--------|:--------:|:--------:|:----------:|:----------:|
| Small accuracy | **83.3%** | 78.8% | **71.2%** | 69.2% |
| Medium accuracy | **77.9%** | 75.0% | **66.3%** | 65.1% |
| Small latency | **5.27s** | 6.02s | **1.83s** | 1.87s |
| Medium latency | **5.45s** | 6.57s | **1.92s** | 1.99s |

**Q5_K_M beats Q8_0 on every metric** — higher accuracy AND lower latency. This is counterintuitive (higher precision should mean better quality) but bartowski's imatrix-guided Q5 quantization appears to provide a regularization benefit. The Q8 model's higher precision may allow it to be "more creative" in ways that hurt structured tool-calling output.

---

## Recommendations

### For HA voice deployment (production use):

**If latency tolerance ≥ 5s:** Use **Qwen3.5-4B Q5_K_M with thinking on**. At 80.4% overall accuracy it matches Qwen3-8B while using far less VRAM (~3.3GB vs ~4.7GB), leaving substantial headroom for conversation history and larger inventories. The 5.3s latency is acceptable for voice assistants.

**If latency must be < 2s:** Stay with **Qwen3-8B Q4_K_M with `/no_think`** (Iteration 4). At 79.6% accuracy and 1.7s latency, it remains the best low-latency option.

**Do not use Qwen3.5-9B at Q3_K_M** — the aggressive quantization kills performance. If Q4_K_M or Q5_K_M could fit (would need more VRAM or smaller context), the 9B might perform better, but on 8GB GTX 1080 hardware it's not viable.

### For further testing:

1. **Test at larger tiers** (large/enormous) if future hardware allows lower-latency thinking — currently the 3× latency penalty makes Qwen3.5-4B impractical for voice production.
2. **Consider Qwen3.5-4B Q4_K_M** (2.87 GB) only if higher-compute hardware becomes available — the latency problem is fundamental to thinking mode, not VRAM.

### Model disposition:

| Model | Disposition | Reason |
|-------|------------|--------|
| Qwen3.5-4B Q5 Think | **Keep — primary candidate** | 80.4%, competitive with Qwen3-8B, much less VRAM |
| Qwen3.5-4B Q8 Think | **Keep — reference** | 76.7%, confirms Q5 > Q8 pattern |
| Qwen3.5-4B Q5 NoThink | **Deprioritize** | 68.6%, thinking is essential for this model |
| Qwen3.5-4B Q8 NoThink | **Deprioritize** | 66.9%, same issue |
| Qwen3.5-9B Q3 | **Drop** | 66-69%, VRAM-limited quantization kills performance |
