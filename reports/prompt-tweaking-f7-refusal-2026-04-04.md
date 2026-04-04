# Prompt Tweak Analysis: F7 Refusal Guidance

**Date:** 2026-04-04
**Config:** `configs/prompt_tweaking_f7.yaml`
**Prompt:** `configs/prompt_tweaking_f7_refusal.txt`
**Change from Iteration 3:** Added `"If no provided tool directly fulfills the user's request, respond without calling any tool."`
**Runs:** 3 repetitions
**Models:** Qwen3-8B Q4_K_M (ctx 22000), Qwen2.5-7B Q5_K_M (ctx 32768)
**Tiers:** small (80 cases), medium (104 cases)

---

## Accuracy Summary (mean ± stdev across 3 runs)

| Model | Tier | Accuracy | Iter3 Baseline | Delta |
|-------|------|----------|----------------|-------|
| Qwen3-8B Q4 | small | 84.6% ± 0.7% | 78.8% | **+5.8pp** |
| Qwen3-8B Q4 | medium | 74.7% ± 0.6% | 71.2% | **+3.5pp** |
| Qwen2.5-7B Q5 | small | 77.1% ± 2.6% | 76.2% | +0.9pp |
| Qwen2.5-7B Q5 | medium | 72.8% ± 2.4% | 69.2% | +3.6pp |

**Note:** Iteration 3 baselines are single-run values from `docs/ha-prompt-engineering.md` (Iter3 R2 for Qwen3, Iter3 R1 for Qwen2.5-Q5). Run-to-run variance of ±3pp makes deltas under ~4pp indistinguishable from noise.

**Assessment:** Qwen3-8B shows a meaningful improvement (+5.8pp small). Qwen2.5-7B improvement is within noise on small but plausible on medium.

---

## Per-Dimension Failure Counts (averaged)

| Dimension | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| response_type | 6.3 ± 0.6 | 10.7 ± 1.5 | 8.7 ± 0.6 | 11.3 ± 1.2 |
| format_valid | 0 | 0 | 0 | 0 |
| call_count | 6.3 ± 0.6 | 12.0 ± 1.0 | 9.0 ± 1.0 | 14.0 ± 1.7 |
| tool_name | 4.0 ± 0.0 | 7.7 ± 0.6 | 4.7 ± 1.5 | 10.7 ± 0.6 |
| args | 8.0 ± 1.0 | 20.7 ± 0.6 | 12.0 ± 2.6 | 22.0 ± 1.7 |
| no_hallucinated_tools | 0 | 0 | 0 | 0 |

---

## Failure Pattern Classification (averaged)

| Pattern | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| F1 (entity ID) | 0.7 | 4.3 | 5.3 | 7.0 |
| F2 (wrong tool) | 2.0 | 2.7 | 2.3 | 5.7 |
| F4 (missing arg) | 3.3 | 7.7 | 2.0 | 3.0 |
| F5 (extra args) | 0 | 1.0 | 0 | 1.0 |
| F7 (response type) | 6.3 | 10.7 | 8.7 | 11.3 |

---

## F7-Specific Breakdown (averaged)

| Direction | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| Didn't-call-when-should | 2.0 ± 0.0 | 5.0 ± 1.0 | 2.3 ± 0.6 | 5.0 ± 0.0 |
| Called-when-shouldn't | 4.3 ± 0.6 | 5.7 ± 0.6 | 6.3 ± 1.2 | 6.3 ± 1.2 |

The F7 refusal prompt reduced "called-when-shouldn't" for Qwen3-8B but had mixed effect on Qwen2.5-7B. The "didn't-call-when-should" cases are dominated by implicit multi-step commands (good morning, goodnight, movie time, I'm heading out) which no prompt instruction can fix — models don't have learned routines.

---

## Match Quality Distribution (averaged)

| Quality | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| optimal | 69.7 | 87.0 | 72.7 | 99.0 |
| equivalent | 2.3 | 2.7 | 2.0 | 2.0 |
| acceptable | 8.0 | 14.3 | 5.3 | 3.0 |
| degraded | 0 | 0 | 0 | 0 |

---

## Latency Summary (averaged)

| Model | Tier | Mean | Min | Max |
|-------|------|------|-----|-----|
| Qwen3-8B Q4 | small | 1.51s | 0.41s | 2.82s |
| Qwen3-8B Q4 | medium | 1.93s | 0.71s | 18.66s |
| Qwen2.5-7B Q5 | small | 1.93s | 0.38s | 17.24s |
| Qwen2.5-7B Q5 | medium | 2.40s | 0.66s | 10.97s |

Qwen2.5-7B has high-latency outliers on small tier (17s) likely from single-sample decode runaways.

---

## Consistently Failing Samples (3/3 runs, both models)

| Sample ID | Utterance | Pattern | Notes |
|-----------|-----------|---------|-------|
| all-text-out_of_scope-search-001 | "search for pasta recipes" | F7 | Qwen3 maps to HassMediaSearchAndPlay |
| all-text-out_of_scope-shopping-001 | "order more paper towels from amazon" | F7 | Qwen2.5 maps to HassShoppingListAddItem |
| medium-HassTurnOn-light-unavailable-001 | "turn on the smart bulb e7a2" | F7 | Both models call HassTurnOn on unavailable entity |
| medium-text-edge-unavailable_light-001 | "turn on the smart bulb in the office" | F7 | Same unavailable entity pattern |
| medium-implicit-good_morning-001 | "good morning" | F7 | Both return [] — no learned routines |
| medium-implicit-leaving-001 | "I'm heading out" | F7 | Both return [] |
| medium-implicit-movie_time-001 | "movie time" | F7 | Both return [] |
| medium-HassGetState-sensor-kitchen_temperature-001 | "what's the kitchen temperature" | F1 | Both use snake_case entity ID |
| medium-HassGetState-sensor-garage_temperature-001 | "what's the temperature in the garage" | F1 | Both use snake_case entity ID |
| medium-HassLightSet-light-color_temp-001 | "set the kitchen ceiling light to warm white" | F4 | Both use `temperature` instead of `color_temp` |

---

## Key Observations

1. **F7 refusal instruction helped Qwen3-8B meaningfully** (+5.8pp small), primarily by reducing "called-when-shouldn't" errors on out-of-scope and ambiguous-intent cases.
2. **Qwen2.5-7B benefit is marginal** — within run-to-run variance on small, slightly better on medium.
3. **Implicit multi-step commands are unfixable by prompt** — "good morning", "movie time", "I'm heading out" require learned routines that small local models don't have.
4. **Unavailable entity detection is not prompt-fixable** — models can't distinguish `state: unavailable` from normal entities in the inventory format.
5. **F1 (snake_case entity IDs) persists** — the name instruction from Iter1 didn't fully fix sensor-domain entities.
6. **F4 (missing args) is stable** — not targeted by this prompt, no change expected or observed.
