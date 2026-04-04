# Cross-Config Comparison: F7/F4 Prompt Tweaking Experiments

**Date:** 2026-04-04
**Configs compared:**
- **F7-only:** `prompt_tweaking_f7.yaml` — refusal guidance
- **F4-only:** `prompt_tweaking_f4.yaml` — domain clarification
- **F7+F4:** `prompt_tweaking_f7_f4.yaml` — both combined
- **Baseline:** Iteration 3 from `docs/ha-prompt-engineering.md` (single-run values)

**Each config:** 3 runs × 2 models × 2 tiers = 12 evals per config, 36 total

---

## Accuracy Comparison (mean ± stdev)

### Qwen3-8B Q4_K_M

| Config | Small (80) | Medium (104) |
|--------|:----------:|:------------:|
| **Iter3 baseline** | **78.8%** | **71.2%** |
| F7-only | **84.6% ± 0.7%** (+5.8pp) | **74.7% ± 0.6%** (+3.5pp) |
| F4-only | 75.8% ± 0.7% (-3.0pp) | 69.2% ± 0.0% (-2.0pp) |
| F7+F4 | 79.6% ± 1.4% (+0.8pp) | 74.0% ± 2.5% (+2.8pp) |

### Qwen2.5-7B Q5_K_M

| Config | Small (80) | Medium (104) |
|--------|:----------:|:------------:|
| **Iter3 baseline** | **76.2%** | **69.2%** |
| F7-only | 77.1% ± 2.6% (+0.9pp) | **72.8% ± 2.4%** (+3.6pp) |
| F4-only | 74.6% ± 1.9% (-1.6pp) | 68.3% ± 1.9% (-0.9pp) |
| F7+F4 | 78.3% ± 1.9% (+2.1pp) | 69.6% ± 2.8% (+0.4pp) |

---

## Statistical Significance Assessment

Given observed run-to-run variance of ±0.7% to ±2.8% (stdev), and baseline being single-run:

| Config | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|--------|:-----------:|:------------:|:-------------:|:--------------:|
| F7-only | **Significant** (+5.8pp, 8× stdev) | **Likely real** (+3.5pp, 6× stdev) | Noise (+0.9pp) | Borderline (+3.6pp, 1.5× stdev) |
| F4-only | **Significant regression** (-3.0pp, 4× stdev) | **Likely regression** (-2.0pp) | Noise (-1.6pp) | Noise (-0.9pp) |
| F7+F4 | Noise (+0.8pp) | Noise (+2.8pp, 1× stdev) | Noise (+2.1pp) | Noise (+0.4pp) |

---

## Failure Pattern Comparison (averaged, Qwen3-8B small for readability)

| Pattern | F7-only | F4-only | F7+F4 | Target |
|---------|:-------:|:-------:|:-----:|--------|
| F1 (entity ID) | 0.7 | 4.3 | 4.3 | — |
| F2 (wrong tool) | 2.0 | 3.0 | 3.7 | — |
| F4 (missing arg) | 3.3 | 8.0 | 6.7 | ← F4 prompt target |
| F5 (extra args) | 0 | 8.7 | 9.0 | — |
| F7 (response type) | 6.3 | 8.0 | 6.3 | ← F7 prompt target |

**Key finding:** F7-only dramatically reduces F1 (0.7 vs 4.3), F4 (3.3 vs 8.0), and F5 (0 vs 8.7) for Qwen3 small — even though these aren't the target pattern. The refusal instruction appears to have a general regularizing effect on Qwen3's output.

The F4 domain instruction does the opposite — inflates F4 and F5 failures, suggesting it confuses argument construction.

---

## Head-to-Head: F7 vs F4 vs Combined

### What F7-only does well:
- Qwen3-8B small: **+5.8pp** — largest improvement of any config
- Reduces "called-when-shouldn't" F7 errors (4.3 vs 8.0 baseline)
- Collateral benefit: reduces F1, F4, F5 for Qwen3
- Very stable (stdev 0.7%)

### What F4-only does poorly:
- **Regressions across the board** — -3.0pp Qwen3 small, -2.0pp medium
- Does NOT reduce device_class misuse (Qwen3: 4.3/run small, 6.7/run medium — unchanged)
- Inflates F5 (extra args) — domain instruction causes argument bloat

### What F7+F4 combined shows:
- F7 benefit and F4 regression cancel out → net neutral
- Unexpected: Qwen3 device_class usage drops to near zero in combined (0 medium) vs high in F4-only (6.7 medium) — interaction effect
- Still has F4-induced F5 bloat

---

## Irreducible Failures (present in ALL configs, ALL runs)

These failures are model capability limits, not prompt-addressable:

| Category | Examples | Count | Root Cause |
|----------|---------|-------|------------|
| Implicit multi-step | "good morning", "goodnight", "movie time", "I'm heading out" | 4 cases | No learned routines — models can't infer multi-action sequences from ambient phrases |
| Unavailable entity | "turn on the smart bulb e7a2" | 2 cases | Models can't distinguish `state: unavailable` in inventory format |
| Sensor entity IDs (F1) | "what's the kitchen temperature", "what's the garage temperature" | 5-8 cases | Entity ID visual prominence in YAML overrides name instruction for sensor domain |
| Color temp semantics | "set the kitchen ceiling light to warm white" | 1 case | Models use numeric Kelvin `temperature` instead of string `color_temp` |
| Missing entity name | "turn the living room soundbar down 20 percent" | 1 case | Model omits `name` arg, passes only `volume_step` |

---

## Recommendations

### Immediate: Adopt F7-only prompt as new Iteration 4

The F7 refusal instruction is the clear winner:
- Meaningful accuracy gain for Qwen3-8B (+5.8pp small, +3.5pp medium)
- No regression for Qwen2.5-7B
- Very low run-to-run variance (most stable config)

**Proposed Iteration 4 prompt** = current Iteration 3 + `"If no provided tool directly fulfills the user's request, respond without calling any tool."`

### Drop: F4 domain instruction

The domain/device_class instruction doesn't work as a system prompt directive. Do NOT include it. If device_class confusion needs fixing:
- Address in tool descriptions (add "Use `domain` parameter" to HassGetState tool doc)
- Or restructure inventory YAML to not expose `device_class` as a visible field

### Next prompt experiments to consider:

1. **Sensor entity ID persistence (F1):** The remaining F1 failures are almost exclusively sensor-domain entities. Consider: "For sensor and binary_sensor entities, always use the friendly name shown after `name:`, never the entity_id key."
2. **Color temp semantics (F4):** Add to HassLightSet tool description: "`color_temp` accepts string values like 'warm white', 'cool white', 'daylight'"
3. **Unavailable entity handling:** Mark unavailable entities differently in inventory (e.g., add `[UNAVAILABLE]` suffix) — but this changes the inventory format, which is supposed to match HA exactly.
4. **Implicit multi-step commands:** These are fundamentally beyond prompt engineering for small models. Could be handled by a separate automation/routine layer in HA.

### Run validation:

Before adopting F7-only as Iteration 4, run it with `--runs 5` for tighter confidence intervals, and test on large/enormous tiers to verify the improvement scales.
