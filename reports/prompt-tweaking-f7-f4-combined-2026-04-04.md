# Prompt Tweak Analysis: F7 + F4 Combined

**Date:** 2026-04-04
**Config:** `configs/prompt_tweaking_f7_f4.yaml`
**Prompt:** `configs/prompt_tweaking_f7_f4_combined.txt`
**Changes from Iteration 3:** Added both:
- `"If no provided tool directly fulfills the user's request, respond without calling any tool."`
- `"Use domain (not device_class) to filter by entity type."`
**Runs:** 3 repetitions
**Models:** Qwen3-8B Q4_K_M (ctx 22000), Qwen2.5-7B Q5_K_M (ctx 32768)
**Tiers:** small (80 cases), medium (104 cases)

---

## Accuracy Summary (mean ± stdev across 3 runs)

| Model | Tier | Accuracy | Iter3 Baseline | Delta |
|-------|------|----------|----------------|-------|
| Qwen3-8B Q4 | small | 79.6% ± 1.4% | 78.8% | +0.8pp |
| Qwen3-8B Q4 | medium | 74.0% ± 2.5% | 71.2% | +2.8pp |
| Qwen2.5-7B Q5 | small | 78.3% ± 1.9% | 76.2% | +2.1pp |
| Qwen2.5-7B Q5 | medium | 69.6% ± 2.8% | 69.2% | +0.4pp |

**Assessment:** Combined prompt is a wash — all deltas are within run-to-run variance (±3pp). The F7 benefit and F4 regression largely cancel each other out.

---

## Per-Dimension Failure Counts (averaged)

| Dimension | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| response_type | 6.3 ± 0.6 | 10.7 ± 1.5 | 7.7 ± 1.2 | 11.7 ± 1.5 |
| format_valid | 0 | 0 | 0 | 0 |
| call_count | 6.3 ± 0.6 | 12.7 ± 1.5 | 8.0 ± 1.0 | 14.3 ± 1.5 |
| tool_name | 3.7 ± 0.6 | 7.7 ± 1.5 | 5.0 ± 0.0 | 12.0 ± 1.7 |
| args | 11.7 ± 0.6 | 21.3 ± 2.1 | 11.7 ± 0.6 | 24.7 ± 2.1 |
| no_hallucinated_tools | 0 | 0 | 0 | 0 |

---

## Failure Pattern Classification (averaged)

| Pattern | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| F1 (entity ID) | 4.3 | 5.3 | 5.0 | 8.0 |
| F2 (wrong tool) | 3.7 | 7.7 | 5.0 | 12.0 |
| F4 (missing arg) | 6.7 | 8.7 | 4.0 | 6.7 |
| F5 (extra args) | 9.0 | 15.3 | 5.3 | 13.3 |
| F6 (call count) | 0 | 2.0 | 0.3 | 2.7 |
| F7 (response type) | 6.3 | 10.7 | 7.7 | 11.7 |

---

## F7-Specific Breakdown (averaged)

| Direction | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| Didn't-call-when-should | 1.7 ± 0.6 | 5.0 ± 1.0 | 2.0 ± 0.0 | 4.7 ± 0.6 |
| Called-when-shouldn't | 4.7 ± 0.6 | 5.7 ± 0.6 | 5.7 ± 1.2 | 7.0 ± 1.0 |

## F4-Specific Breakdown (averaged)

| Metric | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|--------|:-----------:|:------------:|:-------------:|:--------------:|
| missing_domain | 2.3 ± 0.6 | 2.3 ± 0.6 | 0.7 ± 0.6 | 2.3 ± 1.2 |
| device_class_instead | 1.3 ± 0.6 | 0 | 0.3 ± 0.6 | 0 |

**Interesting:** Qwen3-8B's device_class usage dropped significantly in the combined prompt (1.3 small, 0 medium) compared to the F4-only prompt (4.3 small, 6.7 medium). The F7 refusal instruction may be suppressing the model's tendency to over-specify arguments.

---

## Match Quality Distribution (averaged)

| Quality | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| optimal | 74.3 | 95.3 | 72.0 | 97.3 |
| equivalent | 2.7 | 3.3 | 2.0 | 2.0 |
| acceptable | 3.0 | 5.3 | 6.0 | 4.7 |
| degraded | 0 | 0 | 0 | 0 |

---

## Latency Summary (averaged)

| Model | Tier | Mean | Min | Max |
|-------|------|------|-----|-----|
| Qwen3-8B Q4 | small | 1.56s | 0.54s | 4.70s |
| Qwen3-8B Q4 | medium | 1.98s | 0.70s | 19.10s |
| Qwen2.5-7B Q5 | small | 1.95s | 0.55s | 17.20s |
| Qwen2.5-7B Q5 | medium | 2.35s | 0.70s | 10.75s |

---

## Key Observations

1. **Combined prompt is neutral** — F7 gains offset by F4 regression.
2. **Unexpected interaction:** Qwen3-8B device_class usage dropped to near zero in the combined prompt vs. high in F4-only. The F7 refusal line may have a moderating effect on argument over-specification.
3. **F5 (extra args) remains elevated** — same pattern as F4-only, the domain instruction still causes argument bloat.
4. **Same irreducible failures** — implicit multi-step, unavailable entities, sensor entity IDs.
