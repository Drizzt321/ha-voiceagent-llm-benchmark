# Prompt Tweak Analysis: F4 Domain Clarification

**Date:** 2026-04-04
**Config:** `configs/prompt_tweaking_f4.yaml`
**Prompt:** `configs/prompt_tweaking_f4_domain.txt`
**Change from Iteration 3:** Added `"Use domain (not device_class) to filter by entity type."`
**Runs:** 3 repetitions
**Models:** Qwen3-8B Q4_K_M (ctx 22000), Qwen2.5-7B Q5_K_M (ctx 32768)
**Tiers:** small (80 cases), medium (104 cases)

---

## Accuracy Summary (mean ± stdev across 3 runs)

| Model | Tier | Accuracy | Iter3 Baseline | Delta |
|-------|------|----------|----------------|-------|
| Qwen3-8B Q4 | small | 75.8% ± 0.7% | 78.8% | **-3.0pp** |
| Qwen3-8B Q4 | medium | 69.2% ± 0.0% | 71.2% | **-2.0pp** |
| Qwen2.5-7B Q5 | small | 74.6% ± 1.9% | 76.2% | -1.6pp |
| Qwen2.5-7B Q5 | medium | 68.3% ± 1.9% | 69.2% | -0.9pp |

**Assessment:** The F4 domain instruction caused a slight regression for both models. Qwen3-8B regressed more clearly (-3.0pp small, -2.0pp medium). Qwen2.5-7B regression is within noise. **This prompt change is net-negative.**

---

## Per-Dimension Failure Counts (averaged)

| Dimension | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| response_type | 8.0 ± 0.0 | 12.7 ± 0.6 | 9.0 ± 1.0 | 12.3 ± 1.5 |
| format_valid | 0 | 0 | 0 | 0 |
| call_count | 8.0 ± 0.0 | 14.7 ± 0.6 | 9.0 ± 1.0 | 15.7 ± 1.2 |
| tool_name | 3.0 ± 0.0 | 7.3 ± 0.6 | 5.3 ± 0.6 | 12.3 ± 0.6 |
| args | 12.3 ± 0.6 | 23.0 ± 0.0 | 13.7 ± 2.1 | 25.0 ± 2.6 |
| no_hallucinated_tools | 0 | 0 | 0 | 0 |

---

## Failure Pattern Classification (averaged)

| Pattern | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| F1 (entity ID) | 4.3 | 5.3 | 5.7 | 7.3 |
| F2 (wrong tool) | 3.0 | 7.3 | 5.3 | 12.3 |
| F4 (missing arg) | 8.0 | 15.3 | 7.0 | 12.0 |
| F5 (extra args) | 8.7 | 17.0 | 6.3 | 14.0 |
| F6 (call count) | 8.0 | 14.7 | 9.0 | 15.7 |
| F7 (response type) | 8.0 | 12.7 | 9.0 | 12.3 |

**Concerning:** F4 (missing arg) and F5 (extra args) are substantially elevated compared to F7 config. The domain instruction may be confusing models into restructuring their argument patterns, adding extra keys and dropping expected ones.

---

## F4-Specific Breakdown (averaged)

| Metric | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|--------|:-----------:|:------------:|:-------------:|:--------------:|
| missing_domain | 2.3 �� 0.6 | 3.7 ± 0.6 | 1.3 ± 0.6 | 2.7 ± 1.2 |
| device_class_instead | 4.3 ± 0.6 | 6.7 ± 0.6 | 1.0 ± 1.0 | 0.7 ± 0.6 |

**The domain instruction did NOT reduce device_class usage for Qwen3-8B** — it still uses `device_class` 4-7 times per run. The model treats `device_class` as a different semantic concept than `domain` and the instruction doesn't resolve that confusion. Qwen2.5-7B already had low device_class misuse, so the instruction had nothing to fix.

---

## Match Quality Distribution (averaged)

| Quality | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| optimal | 74.3 | 95.7 | 71.3 | 96.0 |
| equivalent | 3.0 | 3.0 | 2.0 | 2.0 |
| acceptable | 2.7 | 5.3 | 6.7 | 6.0 |
| degraded | 0 | 0 | 0 | 0 |

---

## Latency Summary (averaged)

| Model | Tier | Mean | Min | Max |
|-------|------|------|-----|-----|
| Qwen3-8B Q4 | small | 1.55s | 0.60s | 2.59s |
| Qwen3-8B Q4 | medium | 1.99s | 0.70s | 18.79s |
| Qwen2.5-7B Q5 | small | 1.96s | 0.52s | 17.63s |
| Qwen2.5-7B Q5 | medium | 2.46s | 0.66s | 10.87s |

Latency is consistent with F7 config — no prompt-induced latency change.

---

## Key Observations

1. **The F4 domain instruction is net-negative** — slight accuracy regression for both models, no meaningful reduction in device_class misuse.
2. **Qwen3-8B's device_class habit is deeply ingrained** — even with explicit "use domain not device_class" instruction, it persists at 4-7 instances per run. This appears to be a model capability limitation, not a prompt-fixable issue.
3. **Qwen2.5-7B already uses domain correctly** — the instruction has nothing to fix for this model.
4. **F5 (extra args) spiked** — the domain instruction may have caused models to add more argument keys generally, increasing F5 failures.
5. **Recommendation: Drop this prompt line.** The instruction doesn't help and may hurt. Device_class confusion should be addressed in tool descriptions or inventory format, not the system prompt.
