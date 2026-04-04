# HA Voice LLM Benchmark — F7/F4 Prompt Tweaking Results, April 2026

Targeted prompt engineering experiments testing two failure-pattern-specific instructions (F7 refusal, F4 domain clarification) on the two best-performing models from the March 2026 baseline runs.

## Top-Line Results

**Overall accuracy (averaged across small + medium tiers, 3 runs each):**

| Config | Qwen3 8B | Qwen2.5 7B Q5 | Avg Latency |
|--------|:--------:|:--------------:|:-----------:|
| **Iter3 baseline** | 74.8% | 72.5% | 1.8s / 2.3s |
| **F7 refusal** | **79.3%** (+4.5pp) | 74.8% (+2.3pp) | 1.7s / 2.2s |
| F4 domain | 72.3% (-2.5pp) | 71.3% (-1.2pp) | 1.8s / 2.2s |
| F7+F4 combined | 76.6% (+1.8pp) | 73.7% (+1.2pp) | 1.8s / 2.2s |

**Key findings:**

1. **The F7 refusal line is the clear winner** — Qwen3-8B improved from 74.8% to 79.3% overall, with the largest gains on edge cases (+46.7pp medium) and out-of-scope (+25pp). This is the single biggest improvement since the "always use friendly name" instruction in Iteration 1.

2. **The F4 domain instruction is net-negative** — slight regressions for both models, and it does not reduce `device_class` misuse. Rejected as a prompt-level fix.

3. **Combining F7+F4 cancels out** — the F7 benefit and F4 regression offset each other, producing neutral results.

4. **One sentence changed everything.** The entire F7 improvement comes from adding a single line: `"If no provided tool directly fulfills the user's request, respond without calling any tool."`

---

## Benchmark Setup

### Hardware

- **GPU:** NVIDIA GeForce GTX 1080 (8 GB VRAM)
- **CPU:** AMD Ryzen 7 3800X (4 cores allocated to VM)
- **RAM:** 7.8 GiB
- **Inference:** llama.cpp server build 8366, fully GPU-offloaded (`ngl=99`)
- **Connection:** Remote via SSH

### Test Configuration

- **Tiers:** Small (34 entities, 80 test cases) and Medium (88 entities, 104 test cases)
- **Scoring:** Strict multi-dimensional — all of response_type, format_valid, call_count, tool_name, args, and no_hallucinated_tools must pass
- **Runs:** 3 per model/config/tier combination
- **Framework:** [Inspect AI](https://inspect.ai-safety-institute.org.uk/)
- **Run tool:** `scripts/run_multi_benchmark.py` with `--runs 3`

### Models Tested

| Model | HF Repo | Quant | Context |
|-------|---------|-------|---------|
| Qwen3 8B | unsloth/Qwen3-8B-GGUF | Q4_K_M | 22000 |
| Qwen2.5 7B | bartowski/Qwen2.5-7B-Instruct-GGUF | Q5_K_M | 32768 |

These are the two best performers from the March 2026 runs. Lower-performing models (Functionary, Meta-Llama, Llama 3.2) were excluded to focus resources on the prompt engineering signal.

### Prompt Configurations

All prompts build on Iteration 3 (the best prompt from the March runs). The 3 configs test single-variable additions:

| Config | Label | Change from Iteration 3 |
|--------|-------|------------------------|
| Baseline | **Iter3** | No change (HassGetState hint + `/no_think`) |
| F7 | **+ Refusal** | Added: `"If no provided tool directly fulfills the user's request, respond without calling any tool."` |
| F4 | **+ Domain** | Added: `"Use domain (not device_class) to filter by entity type."` |
| F7+F4 | **+ Both** | Both F7 and F4 lines added |

### Full Prompt Text

Each config modifies only the system prompt instructions block. The entity inventory, tool definitions, and timestamp are appended identically. Lines that differ from Iteration 3 are marked with `>>>`.

**Iteration 3 baseline** (`configs/system_prompt_always_no_think_sensor.txt`):
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
/no_think
```

**F7 — + Refusal** (`configs/prompt_tweaking_f7_refusal.txt`):
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
>>> If no provided tool directly fulfills the user's request, respond without calling any tool.
/no_think
```

**F4 — + Domain** (`configs/prompt_tweaking_f4_domain.txt`):
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
>>> Use `domain` (not `device_class`) to filter by entity type.
/no_think
```

**F7+F4 — + Both** (`configs/prompt_tweaking_f7_f4_combined.txt`):
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
>>> If no provided tool directly fulfills the user's request, respond without calling any tool.
>>> Use `domain` (not `device_class`) to filter by entity type.
/no_think
```

---

## Detailed Results by Tier

### Small Tier (34 entities, 80 test cases)

| Model | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|-------|------:|-----------:|----------:|------:|
| **Qwen3 8B** | 77.1% | **84.6% ± 0.7%** | 75.8% ± 0.7% | 79.6% ± 1.4% |
| **Qwen2.5 7B Q5** | 75.4% | 77.1% ± 2.6% | 74.6% ± 1.9% | 78.3% ± 1.9% |

### Medium Tier (88 entities, 104 test cases)

| Model | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|-------|------:|-----------:|----------:|------:|
| **Qwen3 8B** | 69.6% | **74.7% ± 0.6%** | 69.2% ± 0.0% | 74.0% ± 2.5% |
| **Qwen2.5 7B Q5** | 68.3% | 72.8% ± 2.4% | 68.3% ± 1.9% | 69.6% ± 2.8% |

Iteration 3 baselines are 3-run averages from the `benchmark_test_4` runs (March 2026).

### Statistical Significance

Given observed run-to-run stdev of ±0.7% to ±2.8%:

| Config | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|--------|:-----------:|:------------:|:-------------:|:--------------:|
| F7 refusal | **Significant** (+7.5pp) | **Significant** (+5.1pp) | Noise (+1.7pp) | Borderline (+4.5pp) |
| F4 domain | **Sig. regression** (-1.3pp) | Noise (-0.4pp) | Noise (-0.8pp) | Noise (0pp) |
| F7+F4 | Noise (+2.5pp) | Borderline (+4.4pp) | Noise (+2.9pp) | Noise (+1.3pp) |

---

## Per-Type Accuracy — Qwen3 8B

### Small Tier (showing types where configs differ)

| Intent Type | n | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|-------------|:-:|:-----:|:----------:|:---------:|:-----:|
| state_query | 10 | 63% | **80%** ↑ | 53% ↓ | 53% ↓ |
| edge_case | 5 | 40% | **60%** ↑ | 40% | **60%** ↑ |
| out_of_scope | 4 | 50% | **75%** ↑ | 50% | **75%** ↑ |
| disambiguation | 4 | 58% | **83%** ↑ | 67% | 67% |
| climate_control | 3 | 89% | **100%** ↑ | 67% ↓ | 89% |
| incomplete_command | 3 | 67% | **89%** ↑ | 67% | 78% |
| implicit_intent | 3 | 33% | 33% | 33% | 33% |
| light_control | 6 | 83% | 78% | 78% | 78% |

### Medium Tier (showing types where configs differ)

| Intent Type | n | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|-------------|:-:|:-----:|:----------:|:---------:|:-----:|
| edge_case | 5 | 13% | **60%** ↑↑ | 20% | **60%** ↑↑ |
| out_of_scope | 4 | 50% | **75%** ↑ | 50% | **75%** ↑ |
| state_query | 18 | 65% | **70%** ↑ | 56% ↓ | 52% ↓ |
| disambiguation | 7 | 62% | 67% | 62% | **76%** ↑ |
| area_command | 2 | 50% | 33% | 50% | **83%** ↑ |
| media_control | 11 | 91% | 85% | 85% | 88% |
| multi_action | 3 | 67% | 67% | 67% | 56% ↓ |
| implicit_intent | 6 | 17% | 17% | 17% | 17% |

### Notable Patterns

**F7 refusal dominates edge_case:** 13% → 60% on medium (+46.7pp). The model now correctly refuses to act on unavailable entities and incomplete utterances instead of guessing.

**F7 refusal improves out_of_scope:** 50% → 75%. The model correctly distinguishes "order paper towels from Amazon" (refuse) from "add milk to the shopping list" (tool call) — despite a `todo.shopping_list` entity existing in the inventory.

**state_query improves with F7 but regresses with F4:** The domain instruction confuses argument construction for sensor queries, while the refusal instruction has a collateral benefit of cleaning up argument patterns.

**implicit_intent is immovable:** 33% small, 17% medium across all configs. "Good morning", "movie time", "I'm heading out" require learned multi-action routines that small local models can't infer from a system prompt.

---

## Failure Pattern Analysis

### Failure Pattern Comparison — Qwen3 8B (3-run averages)

#### Small Tier (80 cases)

| Pattern | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|---------|:-----:|:----------:|:---------:|:-----:|
| F1 (entity ID) | 6.7 | **0.7** ↓ | 4.3 | 4.3 |
| F2 (wrong tool) | 3.7 | 2.0 | 3.0 | 3.7 |
| F4 (missing arg) | 6.7 | **3.3** ↓ | 8.0 ↑ | 6.7 |
| F5 (extra args) | 8.3 | **0** ↓ | 8.7 | 9.0 |
| F7 (response type) | 8.7 | **6.3** ↓ | 8.0 | 6.3 |
| **Total failures** | **18.3** | **12.3** | **19.3** | **16.3** |

#### Medium Tier (104 cases)

| Pattern | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|---------|:-----:|:----------:|:---------:|:-----:|
| F1 (entity ID) | 7.3 | **4.3** ↓ | 5.3 | 5.3 |
| F2 (wrong tool) | 7.7 | **2.7** ↓ | 7.3 | 7.7 |
| F4 (missing arg) | 12.7 | **7.7** ↓ | 15.3 ↑ | 8.7 ↓ |
| F5 (extra args) | 16.3 | **1.0** ↓ | 17.0 | 15.3 |
| F6 (call count) | 2.0 | 0 | 14.7 ↑↑ | 2.0 |
| F7 (response type) | 13.3 | **10.7** ↓ | 12.7 | 10.7 |
| **Total failures** | **31.7** | **26.3** | **32.0** | **27.0** |

### Per-Dimension Failure Counts — Both Models (3-run averages)

| Dimension | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| **F7 Refusal config** |
| response_type | 6.3 | 10.7 | 8.7 | 11.3 |
| call_count | 6.3 | 12.0 | 9.0 | 14.0 |
| tool_name | 4.0 | 7.7 | 4.7 | 10.7 |
| args | 8.0 | 20.7 | 12.0 | 22.0 |
| format_valid | 0 | 0 | 0 | 0 |
| no_hallucinated_tools | 0 | 0 | 0 | 0 |
| **F4 Domain config** |
| response_type | 8.0 | 12.7 | 9.0 | 12.3 |
| call_count | 8.0 | 14.7 | 9.0 | 15.7 |
| tool_name | 3.0 | 7.3 | 5.3 | 12.3 |
| args | 12.3 | 23.0 | 13.7 | 25.0 |

The `args` dimension dominates failures across all configs — consistent with the March findings.

### F7-Specific: Response Type Breakdown (F7 Refusal config)

| Direction | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|-----------|:-----------:|:------------:|:-------------:|:--------------:|
| Didn't-call-when-should | 2.0 | 5.0 | 2.3 | 5.0 |
| Called-when-shouldn't | 4.3 | 5.7 | 6.3 | 6.3 |

### F4-Specific: Domain vs Device_Class (F4 Domain config)

| Metric | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|--------|:-----------:|:------------:|:-------------:|:--------------:|
| missing_domain | 2.3 | 3.7 | 1.3 | 2.7 |
| device_class_instead | 4.3 | 6.7 | 1.0 | 0.7 |

**The F4 instruction failed its primary objective.** Qwen3 still uses `device_class` 4–7 times per run despite being told not to. Qwen2.5 already had low `device_class` usage — the instruction had nothing to fix.

### Match Quality Distribution (F7 Refusal config, averaged)

| Quality | Qwen3/small | Qwen3/medium | Qwen2.5/small | Qwen2.5/medium |
|---------|:-----------:|:------------:|:-------------:|:--------------:|
| optimal | 69.7 | 87.0 | 72.7 | 99.0 |
| equivalent | 2.3 | 2.7 | 2.0 | 2.0 |
| acceptable | 8.0 | 14.3 | 5.3 | 3.0 |
| degraded | 0 | 0 | 0 | 0 |

---

## Latency

| Model | Tier | Iter3 | F7 Refusal | F4 Domain | F7+F4 |
|-------|------|:-----:|:----------:|:---------:|:-----:|
| Qwen3 8B | small | 1.7s | 1.51s | 1.55s | 1.56s |
| Qwen3 8B | medium | 2.1s | 1.93s | 1.99s | 1.98s |
| Qwen2.5 7B Q5 | small | 1.9s | 1.93s | 1.96s | 1.95s |
| Qwen2.5 7B Q5 | medium | 2.6s | 2.40s | 2.46s | 2.35s |

No meaningful latency differences between prompt configs. All within normal variation.

---

## Irreducible Failures (present in ALL configs, ALL runs)

These failures are model capability limits, not prompt-addressable:

| Category | Examples | Count | Root Cause |
|----------|---------|:-----:|------------|
| Implicit multi-step | "good morning", "goodnight", "movie time", "I'm heading out" | 4 | No learned routines — models can't infer multi-action sequences from ambient phrases |
| Unavailable entity | "turn on the smart bulb e7a2", "turn on the smart bulb in the office" | 2 | Models can't distinguish `state: unavailable` in inventory format |
| Sensor entity IDs (F1) | "what's the kitchen temperature", "what's the garage temperature" | 5–8 | Entity ID visual prominence in YAML overrides name instruction for sensor domain |
| Color temp semantics | "set the kitchen ceiling light to warm white" | 1 | Models use numeric Kelvin `temperature` instead of string `color_temp` |
| Missing entity name | "turn the living room soundbar down 20 percent" | 1 | Model omits `name` arg, passes only `volume_step` |

---

## Recommendations

### Immediate: Adopt F7 refusal line as Iteration 4

The F7 refusal instruction is the clear winner:
- **+7.5pp Qwen3 small** (77.1% → 84.6%), **+5.1pp medium** (69.6% → 74.7%)
- No regression for Qwen2.5-7B
- Very low run-to-run variance (most stable config tested)
- Broad collateral improvements: F1, F4, F5 all reduced for Qwen3

**Iteration 4 prompt** = Iteration 3 + `"If no provided tool directly fulfills the user's request, respond without calling any tool."`

### Drop: F4 domain instruction

The domain/device_class instruction doesn't work as a system prompt directive. Do NOT include it. If `device_class` confusion needs fixing:
- Address in tool descriptions (add "Use `domain` parameter" to HassGetState tool doc)
- Or restructure inventory YAML to not expose `device_class` as a visible field

### Future prompt experiments

Documented in `docs/ha-prompt-engineering.md` under "Future F7 refinement variants":

1. **"Ask first" variant** — `"...ask for clarification or respond without calling any tool."`
2. **"Unclear intent" trigger** — `"If the user's intent is unclear or no provided tool directly fulfills..."` (highest-signal next test)
3. **"Unavailable entity" variant** — `"...or the target device is unavailable, respond without calling any tool."`
4. **Positive framing** — `"Only call intent tools when you are confident the correct tool and entity are available..."`

### Other next steps

- **Sensor entity ID persistence (F1):** Consider targeted instruction for sensor/binary_sensor entities
- **Color temp semantics (F4):** Address in HassLightSet tool description, not system prompt
- **Validation run:** Before finalizing Iteration 4, run with `--runs 5` and test on large/enormous tiers to verify the improvement scales
