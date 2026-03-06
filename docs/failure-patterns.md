# Model Failure Patterns

A living taxonomy of ways models produce incorrect tool calls during HA voice benchmarking.
Updated as new patterns are observed across runs and models.

The goal is to classify failures so we can:
- Track prevalence across models and test sets
- Design targeted prompt tweaks and measure their effect
- Decide which failures are prompt-fixable vs. model-capability limits

---

## Failure Classification

| ID | Name | Scorer dimension(s) affected |
|----|------|-------------------------------|
| F1 | Entity ID used instead of friendly name | `args` |
| F1.partial | Partial/truncated friendly name | `args` |
| F2 | Wrong tool for semantically similar intent | `tool_name`, `args` |
| F3 | Hallucinated tool name | `no_hallucinated_tools` |
| F4 | Missing required argument | `args` |
| F5 | Extra/spurious arguments | `args` |
| F6 | Wrong call count | `call_count` |
| F7 | Wrong response type (called/didn't-call) | `response_type`, `call_count` |
| F8 | Wrong domain filter | `args` |
| F9 | Out-of-scope request mapped to nearest HA tool | `response_type` |
| F10 | Prompt format incompatibility / model doesn't use tool calling | `response_type`, `tool_name`, `args` (all) |

---

## F1 — Entity ID used instead of friendly name

### Description

The model passes the entity's ID (e.g. `front_door`, `kitchen_ceiling`) as the `name`
argument instead of the entity's friendly name (e.g. `Front Door Lock`, `Kitchen Ceiling`).

Entity IDs appear as keys in the inventory (`lock.front_door:`, `light.kitchen_ceiling:`)
while friendly names appear under `names:`. The model conflates the two.

### Why it fails in HA

The `name` parameter in all HA intent tools is matched against the entity's friendly name, not
its ID. There is no `id` parameter. Passing an entity ID as `name` will fail to resolve at
runtime in actual HA.

### Observed in

| Test case ID | Input | Expected `name` | Actual `name` |
|---|---|---|---|
| `small-HassGetState-lock-front_door-001` | "is the front door locked" | `Front Door Lock` | `front_door` |
| `small-HassTurnOn-light-kitchen_ceiling-001` (smoke test) | "turn on the kitchen light" | `Kitchen Ceiling` | `kitchen_ceiling` (1 of 2 runs) |

### Potential prompt mitigations to try

- Explicitly state in the system prompt: *"Use the friendly name from `names:`, not the entity ID"*
- Add an example in the prompt showing correct name vs. ID usage
- Reformat the inventory to de-emphasise entity IDs (e.g. omit the `entity_id:` key line, lead with `names:`)

---

## F2 — Wrong tool for semantically similar intent

### Description

The model selects a tool that is semantically related but not the expected one. Often occurs
when multiple tools could plausibly answer the query and the distinction requires domain
knowledge (e.g. climate vs. sensor readings).

### Observed in

| Test case ID | Input | Expected tool | Actual tool | Notes |
|---|---|---|---|---|
| `small-HassClimateGetTemperature-climate-main_thermostat-001` | "what's the temperature inside" | `HassClimateGetTemperature` | `HassGetState` on `sensor.hallway_temperature` | Model read the temperature sensor instead of querying the climate entity. Both are valid in practice; test expects the climate-specific intent. |

### Notes

Some F2 cases may reflect genuine intent ambiguity rather than model error. The test case
expectation may warrant revisiting (e.g. accepting `HassGetState` on a temperature sensor as
an alternate correct answer for temperature queries).

### New sub-patterns (2026-03-04 small run)

- **Lock direction confusion**: "lock the front door" → expected `HassTurnOn` (HA: on=lock), got
  `HassTurnOff`. The model uses the intuitive on/off polarity rather than HA's inverted lock
  convention. Prompt guidance for the lock domain is likely needed.
- **Multi-call implicit refused**: "good morning" expected 2 tool calls but model returned [].
  Model may not attempt multi-step implicit sequences without explicit prompt guidance.
- **Media player action confusion (CPU run)**: "resume the living room TV" → expected
  `HassMediaUnpause`, got `HassMediaPlayerUnmute`. Model conflates "resume" (unpause) with
  "unmute". Seen only on CPU (different FP behaviour from GPU with same seed).
- **Media player state query misrouted (CPU run)**: "what's playing in the living room" →
  expected `HassGetState`, got `HassMediaPause`. The model took an action instead of querying
  state. Much more severe than the GPU run failure (entity-ID form but correct tool). Indicates
  non-deterministic ambiguity between get-state and playback-control intents.

### Potential prompt mitigations to try

- Add guidance distinguishing when to use `HassClimateGetTemperature` vs `HassGetState`
- Clarify in the prompt that climate entities should use climate-specific intents
- Add lock domain note: "For locks, HassTurnOn means lock and HassTurnOff means unlock"

---

## F4 — Missing required argument

### Description

The model calls the correct tool but omits one or more required arguments present in the
expected call. Commonly occurs alongside F1 (entity ID substitution) and F5 (extra args) —
the model provides a different set of keys, often replacing `domain` with `device_class` or
omitting `name` entirely.

### Observed in

| Test case ID | Input | Missing arg | Notes |
|---|---|---|---|
| `small-HassGetState-binary_sensor-motion-001` | "is there motion in the living room" | `domain` | Model used `device_class: ["motion"]` instead |
| `small-HassGetState-binary_sensor-smoke-001` | "is the kitchen smoke detector alarming" | `domain` | Model used `device_class: ["smoke"]` instead |
| `small-HassClimateGetTemperature-living_room-001` | "what's the temperature in the kitchen" | `area` | Model queried sensor entity, no area arg |
| `small-HassLightSet-light-color_temp-001` | "set the kitchen ceiling light to warm white" | `color_temp` | Model used `temperature: 3000` (numeric Kelvin) instead of `"warm white"` |
| `small-HassSetVolumeRelative-media_player-living_room_soundbar-001` | "turn the living room TV volume down 20 percent" | `name` | Model passed only `volume_step: -20`, no entity name |

### Potential prompt mitigations to try

- Restate required arguments in tool descriptions (especially `name` for all entity tools)
- For binary sensors: clarify that `domain` (not `device_class`) is the filter parameter
- For HassLightSet: clarify that `color_temp` accepts string values like `"warm white"`, not
  numeric Kelvin

---

## F5 — Extra/spurious arguments

### Description

The model passes arguments not present in the expected call. Two systematic sub-patterns:

**F5.area** — Model adds `area: "<room>"` when the expected call addresses an entity by name
only. The model appears to ground every entity it recognises in its area, even when `area` is
not needed or expected. This is the most common F5 sub-pattern (13/15 cases in small run).

**F5.device_class** — Model uses `device_class: ["motion"]` / `device_class: ["smoke"]` in
place of `domain: ["binary_sensor"]`. The model draws on its HA schema knowledge rather than
the intent tool's parameter list.

Other extra args observed: `domain` on tools that don't use it, numeric `temperature` on
`HassLightSet` instead of the string `color_temp`.

### Observed in (2026-03-04 small run — 15 cases)

| Sub-pattern | Count | Example |
|---|---|---|
| F5.area | 13 | `HassTurnOn(name="kitchen_ceiling", area="Kitchen", domain=["light"])` — `area` not expected |
| F5.device_class | 2 | `HassGetState(name="binary_sensor.kitchen_smoke", device_class=["smoke"])` |

### Notes

F5 almost always co-occurs with F1 — the model uses entity ID for `name` and pads with extra
keys to show its reasoning. Fixing F1 (prompt: use `names:` value) may incidentally reduce F5.

Whether F5.area should remain a hard failure is worth reviewing: if the entity + area combo
is unambiguous, HA may still resolve it correctly at runtime. Accepting `area` as an optional
extra in the scorer would recover ~13 cases, at the cost of obscuring the divergence.

### Potential prompt mitigations to try

- Add prompt instruction: "Do not add `area` unless it is the only way to identify the entity"
- Add prompt instruction: "Use `domain` (not `device_class`) to filter by entity type"

---

## F9 — Out-of-scope request mapped to nearest HA tool

### Description

When the user's request is outside HA's capabilities, the model finds the closest available
tool and calls it rather than refusing. Observed for out-of-scope requests that have a
superficially related HA tool.

### Observed in

| Test case ID | Input | Expected | Actual | Notes |
|---|---|---|---|---|
| `all-text-out_of_scope-shopping-001` | "order more paper towels from amazon" | `[]` | `HassShoppingListAddItem(item="paper towels")` | Mapped Amazon order to HA shopping list |

### Notes

This is distinct from F3 (hallucinated tool): the tool called is real. The model correctly
identified that a shopping list is adjacent to "ordering" but failed to recognise that Amazon
ordering is out of HA's scope entirely. A prompt constraint ("only call a tool if it directly
fulfills the request within HA") may reduce this.

### Potential prompt mitigations to try

- Add prompt instruction: "If no provided tool directly fulfills the user's request, respond
  without calling any tool"
- Add an out-of-scope example to the system prompt

---

## Observations by model / run

| Date | Model | Test set | n | Accuracy | Dominant failures | Notes |
|------|-------|----------|---|----------|-------------------|-------|
| 2026-02-28 | Qwen2.5-7B-Instruct Q4_K_M | small (25) | 25 | 92% (23/25) | F1×1, F2×1 | First full run |
| 2026-02-28 | Qwen2.5-7B-Instruct Q4_K_M | small (25) | 25 | 96% (24/25) | F1×1 | After adding HassGetState as alternative for temperature query |
| 2026-03-04 | Qwen2.5-7B-Instruct Q4_K_M | small (80) | 80 | 56% (45/80) | args×26, response_type×7, tool_name×5 | M2 full small tier; lower accuracy reflects harder/broader test cases |
| 2026-03-04 | Qwen2.5-7B-Instruct Q4_K_M | enormous (146) | 146 | 53% (77/146) | args×44, response_type×14, tool_name×8, call_count×3 | 453-entity inventory; state_query 7% (F1 dominant) |
| 2026-03-04 | Qwen2.5-7B-Instruct Q4_K_M (GPU ctx32768) | small (80) | 80 | 56.2% (45/80) | F1×25, F5.area×13, F4×7, F7×8, F2×5 | Orchestration integration test run; confirms F1 dominant; F4/F5/F9 now formally observed |

> **Quantization source matters:** `bartowski/Qwen2.5-7B-Instruct-GGUF` (imatrix-guided quant)
> shows measurably higher accuracy than `Qwen/Qwen2.5-7B-Instruct-GGUF` (standard quant) at
> the same Q4_K_M level. Prefer bartowski or other imatrix builds when available. Runs above
> use bartowski unless noted otherwise.
| 2026-03-04 | Qwen2.5-7B-Instruct Q4_K_M (CPU ngl=0 ctx32768) | small (80) | 80 | 57.5% (46/80) | F1×22, F5.area×11, F7×9, F4×4, F2×5 | Same seed; accuracy equivalent to GPU; 6.6× slower (9.47s mean vs 1.43s); 3 samples differ from GPU run (FP non-determinism) |

**Multi-model comparison — Run 1: 2026-03-05 (multi-test.yaml, no targeted prompt, GPU, small+medium tiers)**

| Date | Model | Quant | ctx | small (80) | medium (104) | Dominant failures | Notes |
|------|-------|-------|-----|-----------|-------------|-------------------|-------|
| 2026-03-05 | Qwen2.5-7B-Instruct | Q5_K_M | 32768 | **67.5%** (54/80) | **64.4%** (67/104) | F1, F5, F7 | Best overall; Q5 +5–11pp over Q4 |
| 2026-03-05 | Qwen2.5-7B-Instruct | Q4_K_M | 32768 | 56.2% (45/80) | 53.8% (56/104) | F1, F5, F7 | Strong; same F1 pattern |
| 2026-03-05 | functionally-small-3.1 | Q5_K_M | 20000 | 60.0% (48/80) | 46.2% (48/104) | F1, F5, args | Medium drop larger than Qwen |
| 2026-03-05 | functionally-small-3.1 | Q4_K_M | 24000 | 56.2% (45/80) | 48.1% (50/104) | F1, F5, args | Comparable to Qwen2.5-7B-q4 on small |
| 2026-03-05 | Qwen3-8B | Q4_K_M | 22000 | 52.5% (42/80) | 44.2% (46/104) | F1, F5, F2 | Extended thinking; 6–9× slower than Qwen2.5; no accuracy gain |
| 2026-03-05 | functionally-small-3.1 | Q3_K_M | 32768 | 42.5% (34/80) | 36.5% (38/104) | F1, F5, args | Q3 loses ~15pp vs Q4 |
| 2026-03-05 | Meta-Llama-3.1-8B-Instruct | Q4_K_M | 25000 | 32.5% (26/80) | 35.6% (37/104) | F1, F7, call_count | Flat across tiers; high call_count errors |
| 2026-03-05 | phi4-mini-instruct | Q8_0 | 28000 | 22.5% (18/80) | ~2.6% (1/39)\* | F10 (no tool calls) | BROKEN: model does not use tool calling |
| 2026-03-05 | Llama-3.2-3B-Instruct | F16 | 13000 | 15.0% (12/80) | 8.7% (9/104) | F1, F4, F5 | Near capability floor; high args failures |
| 2026-03-05 | Llama-3.2-3B-Instruct | Q8_0 | 30000 | 11.2% (9/80) | 8.7% (9/104) | F1, F4, F5 | Equivalent to F16 at same tier |
| 2026-03-05 | functionally-small-2.4 | Q4_0 | 28000 | 2.5% (2/80) | 0.0% (0/104) | F10 (random tools) | BROKEN: wrong tool format; see F10 |

\* phi4 medium: partial run — 1 sample stalled 193.89s, no scorer recorded; run terminated at 39/40 samples.

**Multi-model comparison — Run 2: 2026-03-05 (multi-test.yaml, `system_prompt_always_name.txt`, GPU, small+medium tiers)**

Prompt: *"When controlling a device, always pass the friendly name from `names:` and the domain."*

| Model | Quant | ctx | small (80) | medium (104) | Dominant failures | Notes |
|-------|-------|-----|-----------|-------------|-------------------|-------|
| Qwen3-8B | Q4_K_M | 22000 | 70.0% (56/80) | ~65% | F7, F2 | +17.5pp vs Run 1; thinking still active |
| Meta-Llama-3.1-8B | Q4_K_M | 25000 | 58.8% (47/80) | ~52% | F1, F7 | +26.3pp vs Run 1; huge gain from name fix |
| Qwen2.5-7B | Q5_K_M | 32768 | ~68% | ~65% | F1, F7 | Roughly flat vs Run 1 |
| functionally-3.1 | Q4/Q5_K_M | 24/20K | ~56–60% | ~46–49% | F1, F2 | Roughly flat |

**Multi-model comparison — Run 3: 2026-03-05 (multi-test_prompt_2, `system_prompt_always_no_think_2.txt`, GPU, small+medium tiers)**

Prompt: *"When controlling a specific device, always use the friendly name from `names:` and the domain. When controlling an area, prefer passing just the area name and domain. /no_think"*

| Model | Quant | ctx | small (80) | medium (104) | Dominant failures | Notes |
|-------|-------|-----|-----------|-------------|-------------------|-------|
| **Qwen3-8B** | Q4_K_M | 22000 | **81.2%** (65/80) | **71.2%** (74/104) | F7, other | New leader; `/no_think` restored normal latency (1.70s mean) |
| Qwen2.5-7B | Q5_K_M | 32768 | 73.8% (59/80) | 68.3% (71/104) | F7, F1 | Best non-qwen3 |
| Qwen2.5-7B | Q4_K_M | 32768 | 68.8% (55/80) | 67.3% (70/104) | F7, F1 | Consistent with q5 on medium |
| functionally-3.1 | Q5_K_M | 20000 | 61.3% (49/80) | 58.7% (61/104) | F1, F2, F7 | F2 dominates medium (20 cases) |
| functionally-3.1 | Q4_K_M | 24000 | 60.0% (48/80) | 52.9% (55/104) | F1, F2, F7 | F2 capability ceiling |
| **Meta-Llama-3.1-8B** | Q4_K_M | 25000 | **47.5%** (38/80) | 49.0% (51/104) | F7, F1 | **Regression** −11.3pp vs Run 2; area clause confused model; 2×600s server hangs |

**Three-run progression (small tier):**

| Model | Run 1 (baseline) | Run 2 (+name-fix) | Run 3 (+area+nothink) | Total delta |
|-------|-----------------|-------------------|-----------------------|-------------|
| Qwen3-8B | 52.5% | 70.0% | **81.2%** | +28.7pp |
| Meta-Llama-3.1-8B | 32.5% | **58.8%** | 47.5% | best at Run 2 |
| Qwen2.5-7B Q5 | 67.5% | ~68% | **73.8%** | +6.3pp |
| Qwen2.5-7B Q4 | 56.2% | ~57% | **68.8%** | +12.6pp |
| functionally-3.1 Q5 | 60.0% | ~60% | **61.3%** | +1.3pp |
| functionally-3.1 Q4 | 56.2% | ~56% | **60.0%** | +3.8pp |

---

## Latency Observations

### Run A: 2026-03-04 / Qwen2.5-7B-Instruct Q4_K_M / GPU (ngl=99) ctx32768 / small tier (80 samples)

| Metric | Value |
|--------|-------|
| Min latency | 0.42 s |
| Mean latency | 1.43 s |
| Median (p50) | 1.36 s |
| p90 | 1.66 s |
| p95 | 2.25 s |
| Max latency | 11.23 s |
| Output tokens/sec | 23.8 tok/s |
| Input tokens/sec (prefill) | 4,460 tok/s |
| Input token range | 6,406 – 6,416 (very narrow; single tier) |
| Output token range | 8 – 100 |
| Total wall time | 115 s (23:50:39 → 23:52:34 UTC) |
| Aggregate: input tokens | 512,880 |
| Aggregate: output tokens | 2,733 |

**Input token vs latency:** All 80 samples fall in the 6,000–6,499 bin. The small tier
inventory is constant across samples, so input length does not vary. Per-sample latency
variance is driven almost entirely by output length, not input.

**Outliers (> 2× mean = 2.86 s):**

| Sample | Latency | Input tok | Output tok | Cause |
|--------|---------|-----------|------------|-------|
| `small-HassGetState-binary_sensor-motion-001` | 11.23 s | 6,412 | 35 | First sample in run — cold-start / GPU KV-cache warm-up; input/output token counts are typical |
| `all-text-conversational-capabilities-001` | 3.54 s | 6,409 | 100 | Prose response (no tool call) — 100 output tokens is the run maximum; decode-phase bottleneck |

**Interpretation (GPU):** At Q4_K_M on a single GTX 1080, prefill (~6,400 tok) takes well
under 1 s. The mean 1.43 s per sample is dominated by tool-call JSON decode (~20–40 tokens)
plus request overhead. The first-sample spike is a one-time GPU warm-up artefact and should
not be treated as representative latency; strip it before comparing runs. Prose responses
generate 3–5× more output tokens than tool calls, causing 2–3× higher latency.

### Run B: 2026-03-04 / Qwen2.5-7B-Instruct Q4_K_M / CPU (ngl=0) ctx32768 / small tier (80 samples)

| Metric | Value |
|--------|-------|
| Min latency | 2.98 s |
| Mean latency | 9.47 s |
| Median (p50) | 9.46 s |
| p90 | 11.71 s |
| p95 | 13.81 s |
| Max latency | 34.83 s |
| Output tokens/sec | 3.6 tok/s |
| Input tokens/sec (prefill) | 676 tok/s |
| Input token range | 6,406 – 6,416 (same tier, same variance) |
| Output token range | 10 – 91 |
| Total wall time | 759 s (00:56:37 → 01:09:16 UTC) |
| Aggregate: input tokens | 512,880 |
| Aggregate: output tokens | 2,728 |

**Outliers (> 2× mean = 18.94 s):**

| Sample | Latency | Output tok | Cause |
|--------|---------|------------|-------|
| `small-HassGetState-binary_sensor-motion-001` | 34.83 s | 37 | First sample cold-start — same warm-up pattern as GPU run, but ~3× more pronounced on CPU |
| `all-text-conversational-capabilities-001` | 21.28 s | 91 | Prose response — 91 output tokens, highest in run; decode-phase bottleneck |

### GPU vs CPU comparison (same model, same tier, same seed)

| Metric | GPU | CPU | Ratio |
|--------|-----|-----|-------|
| Accuracy | 56.2% (45/80) | **57.5% (46/80)** | — |
| Mean latency | **1.43 s** | 9.47 s | 6.6× faster on GPU |
| p95 latency | **2.25 s** | 13.81 s | 6.1× faster on GPU |
| Output tok/s | **23.8** | 3.6 | 6.6× faster on GPU |
| Input tok/s (prefill) | **4,460** | 676 | 6.6× faster on GPU |
| Wall time (80 samples) | **115 s** | 759 s | 6.6× faster on GPU |

**Accuracy delta:** CPU +1 sample (net). 3 samples flipped GPU-fail→CPU-pass, 2 flipped
GPU-pass→CPU-fail. With 80 samples the difference (56.2% vs 57.5%) is not significant;
both runs reflect the same underlying capability gaps. The sample-level differences are
attributable to floating-point non-determinism between GPU and CPU inference paths.

**Notable cross-hw sample differences:**

| Sample | GPU | CPU | Notes |
|--------|-----|-----|-------|
| `small-HassGetState-media_player-living_room_tv-001` | I (args only: entity ID) | I (response_type+tool_name+args: called `HassMediaPause` instead of `HassGetState`) | CPU failure is qualitatively worse — wrong action taken |
| `small-HassMediaPause-media_player-kitchen_display-001` | I (entity ID) | **C** | CPU used friendly name correctly |
| `small-HassTurnOff-light-living_room_ceiling-001` | I (entity ID+area) | **C** | CPU used friendly name correctly |
| `small-HassGetState-cross-office_temp_6way-001` | I (F2: wrong tool) | **C** | GPU used `HassClimateGetTemperature` on temperature sensor; CPU chose correctly |
| `small-HassMediaUnpause-media_player-living_room_tv-001` | **C** | I (F2: called `HassMediaPlayerUnmute`) | CPU confused "resume" with "unmute" |
| `small-HassMediaPrevious-media_player-dining_room_speaker-001` | **C** | I (F1: entity ID) | CPU used entity ID where GPU used friendly name |

**Interpretation (CPU vs GPU):** The 6.6× throughput gap is consistent with full-CPU
inference for a ~4 GB quantized model on a system without VRAM constraints. Accuracy is
statistically equivalent. The sample-level divergences are stochastic artefacts of
different FP rounding paths, not systematic capability differences. For benchmarking
accuracy, either hw mode is valid. For latency comparison across models, GPU is the
reference since CPU throughput is more sensitive to host hardware.

### Run C: 2026-03-05 / Multi-model comparison / GPU / small+medium tiers

| Model | Tier | Min | Mean | p95 | Max | Wall (s) | TPS | iTok (mean) |
|---|---|---|---|---|---|---|---|---|
| llama3.2-3B Q8_0 | small | 0.29s | **1.09s** | 1.58s | 2.27s | 88s | 34.2 | 7,833 |
| functionally-3.1 Q3_K_M | small | 0.39s | **1.07s** | 1.52s | 3.17s | 86s | 26.1 | 6,850 |
| functionally-3.1 Q4_K_M | small | 0.39s | 1.27s | 1.66s | 20.33s | 102s | 27.0 | 6,850 |
| functionally-3.1 Q5_K_M | small | 0.43s | 1.38s | 1.89s | 16.60s | 110s | 23.7 | 6,850 |
| qwen2.5-7b Q4_K_M | small | 0.41s | 1.30s | 1.66s | 3.61s | 105s | 26.7 | 6,411 |
| qwen2.5-7b Q5_K_M | small | 0.45s | 1.40s | 1.88s | 2.70s | 112s | 24.0 | 6,411 |
| llama3.2-3B Q8_0 | medium | 0.44s | 1.24s | 1.65s | 7.04s | 130s | 29.9 | 10,248 |
| functionally-3.1 Q3_K_M | medium | 0.30s | 1.25s | 1.57s | 11.16s | 130s | 22.8 | 9,265 |
| meta-llama3.1-8B Q4_K_M | small | 0.62s | 1.23s | 1.74s | 2.40s | 99s | 27.3 | 7,836 |
| meta-llama3.1-8B Q4_K_M | medium | 0.52s | 1.42s | 1.85s | 11.48s | 148s | 24.1 | 10,251 |
| qwen2.5-7b Q4_K_M | medium | 0.55s | 1.97s | 2.26s | 23.83s | 206s | 17.7 | 8,872 |
| qwen2.5-7b Q5_K_M | medium | 0.68s | 2.20s | 2.46s | 24.66s | 230s | 16.6 | 8,872 |
| **qwen3-8b Q4_K_M** | **small** | **3.17s** | **9.56s** | **25.86s** | **47.58s** | **765s** | 29.6 | 6,411 |
| **qwen3-8b Q4_K_M** | **medium** | **3.67s** | **12.02s** | **35.02s** | **77.08s** | **1250s** | 24.7 | 8,872 |

**Qwen3-8B thinking mode:** Qwen3 uses extended chain-of-thought reasoning by default, generating
700–1,800 output tokens per sample vs. ~30–100 for other models. Aggregate output tokens:
22,631 (small) and 30,930 (medium) vs. ~2,600–4,800 for other models. Wall time is 6–9×
higher than qwen2.5-7b-q5 with no accuracy advantage (52.5% vs 67.5% on small). If benchmarking
this model, use `/no_think` in the system prompt or disable thinking via model config to get
representative tool-call latency.

**Outlier — `medium-HassGetState-binary_sensor-front_door-001` (first sample in medium runs):**

Every model running the medium tier shows a 7–38s spike on this sample (vs 0.5–2s normally):
output token counts are small (25–46), ruling out decode. This is a **cold-prefill spike** at
~9–10K input tokens on a fresh KV cache — same artifact as the first-sample cold-start observed
in small-tier runs. Strip the first medium-tier sample when computing latency stats or benchmarks.

| Model | Spike | Output tok | Normal mean |
|---|---|---|---|
| functionally-3.1 (all quants) | 10–11s | 25–27 | ~1.25–1.31s |
| llama3.2-3B Q8_0 | 7.0s | 46 | 1.24s |
| meta-llama3.1-8B Q4_K_M | 11.5s | 29 | 1.42s |
| qwen2.5-7b Q4_K_M | 23.8s | 37 | 1.97s |
| qwen2.5-7b Q5_K_M | 24.7s | 37 | 2.20s |
| qwen3-8b Q4_K_M | 37.6s | 228 | 12.02s |

**Other notable outliers:**

| Model / tier | Sample | Latency | Output tok | Cause |
|---|---|---|---|---|
| llama3.2-3B-f16 / medium | `all-text-ambiguous_intent-001` "it's getting dark" | **110.75s** | 2,810 | Unbounded prose/reasoning chain; decode bottleneck |
| functionally-3.1-q4 / small | `all-text-conversational-capabilities-001` "what can you do" | 20.33s | 606 | Very verbose capability list; decode bottleneck |
| phi4-mini / medium | `medium-HassSetVolume-media_player-sonos_bathroom` | **193.89s** | ? | Server stall/timeout; run terminated; no scorer entry |
| qwen3-8b / medium | `medium-multi-office_all_off-001` | 77.08s | 1,843 | Thinking tokens for multi-entity complex request |
| qwen3-8b / small | `small-multi-cover_light_bedroom-001` | 47.58s | 1,350 | Thinking tokens |

**Input token vs latency (small vs medium):**
Within a tier, latency variance is driven by output length, not input length (input is nearly
constant per tier). Across tiers, mean latency increases 20–100% from small→medium (consistent
with ~40% more input tokens + larger inventory search). Qwen3 shows smaller cross-tier latency
growth because thinking tokens dominate decode time regardless of input size.

**Best accuracy/latency tradeoff (Run C):** qwen2.5-7b Q5_K_M — 67.5% (small) / 64.4% (medium),
1.40s mean, 24 TPS. Strongly preferred over qwen3-8b which is 6–9× slower for lower accuracy.

### Run D: 2026-03-05 / Multi-model prompt_2 run / GPU / small+medium tiers

Prompt: `system_prompt_always_no_think_2.txt` (`/no_think` + area/device distinction)

| Model | Tier | Min | Mean | p95 | Max | Wall (s) | TPS | AggOut |
|---|---|---|---|---|---|---|---|---|
| functionally-3.1 Q4_K_M | small | 0.39s | 1.24s | 2.76s | 12.30s | 101s | 25.4 | 2,566 |
| functionally-3.1 Q4_K_M | medium | 0.43s | 1.31s | 1.88s | 11.01s | 137s | 23.3 | 3,193 |
| functionally-3.1 Q5_K_M | small | 0.41s | 1.34s | 1.98s | 18.13s | 108s | 24.1 | 2,599 |
| functionally-3.1 Q5_K_M | medium | 0.45s | 1.34s | 1.72s | 11.39s | 140s | 21.8 | 3,045 |
| qwen2.5-7b Q4_K_M | small | 0.49s | 1.77s | 2.42s | 16.39s | 142s | 19.1 | 2,718 |
| qwen2.5-7b Q4_K_M | medium | 0.62s | 2.46s | 2.64s | 31.03s | 257s | 14.9 | 3,823 |
| qwen2.5-7b Q5_K_M | small | 0.53s | 1.93s | 2.74s | 17.38s | 155s | 17.7 | 2,744 |
| qwen2.5-7b Q5_K_M | medium | 0.67s | 2.60s | 2.96s | 31.91s | 271s | 13.9 | 3,778 |
| **qwen3-8b Q4_K_M** | **small** | **0.60s** | **1.70s** | **1.80s** | 20.94s | **136s** | **21.1** | **2,868** |
| **qwen3-8b Q4_K_M** | **medium** | **0.71s** | **2.05s** | **2.16s** | 39.16s | **215s** | **17.4** | **3,740** |
| meta-llama3.1-8B Q4_K_M | medium | 0.38s | 1.52s | 1.84s | 11.84s | 159s | 24.5 | 3,897 |
| **meta-llama3.1-8B Q4_K_M** | **small** | **0.26s** | **16.70s** | **2.90s** | **620.78s** | **1,336s** | **2.3** | **3,016** |

**Qwen3-8B with `/no_think`:** Mean latency dropped from 9.56s (Run C) → 1.70s (Run D) on small — a 5.6× improvement. Aggregate output tokens dropped from 22,631 → 2,868 (8× reduction), confirming thinking tokens were fully suppressed. Qwen3-8B now has the best accuracy AND competitive latency.

**Cold-prefill outliers persist (Run D):** All models still spike on their first sample per tier. Every model hits 10–39s on `medium-HassGetState-binary_sensor-front_door-001` and 5–21s on `small-HassGetState-binary_sensor-motion-001`. These are KV-cache cold-start artifacts; strip first sample per tier before computing representative latency.

**Functionary "what can you do" spike:** functionally-3.1 models generate 304–503 output tokens answering this capability query (prose list), causing 11–18s outliers — 8–13× the model's mean. Other models either refuse (F7) or respond briefly.

**CRITICAL — meta-llama3.1-8B small server hangs:** Two samples caused catastrophic stalls:

| Sample | Latency | Output tok | Input |
|---|---|---|---|
| `small-HassGetState-binary_sensor-occupancy-001` ("is anyone in the office") | **620.78s** | 57 | |
| `small-HassTurnOff-light-kitchen-area-001` ("turn off the kitchen lights") | **605.97s** | 28 | |

Output token counts are small (28–57), ruling out decode runaways. These appear to be server-level hangs — likely stale KV state or context fragmentation between samples. The run's p95=2.90s confirms 95%+ of samples completed normally; these two were isolated catastrophic failures that skewed mean to 16.70s and wall time to 1,336s.

**Mitigation required:** Set `attempt_timeout` in the benchmark config before re-running meta-llama3.1-8B. Without a per-sample timeout, two stuck samples consumed over 20 minutes and blocked the entire run queue.

**Best accuracy/latency tradeoff (Run D):** qwen3-8b Q4_K_M — 81.2%/71.2% (small/medium), 1.70s/2.05s mean. Qwen2.5-7b Q5_K_M is the closest competitor at 73.8%/68.3% with slightly lower latency (1.93s/2.60s on small/medium).

---

## F10 — Prompt format incompatibility / model does not use tool calling

### Description

The model systematically fails to use tool calling, either:
1. **Never calling tools:** responds in plain text for all utterances regardless of context, OR
2. **Random tool selection:** calls completely unrelated tools that bear no semantic relationship
   to the request (e.g. `HassLawnMowerStartMowing` for a fan speed query, `HassMediaPlayerMute`
   for a binary sensor read).

Both sub-patterns suggest the model was not fine-tuned for the tool-calling format sent by
this benchmark, or the system prompt structure is incompatible with the model's expectations.
This is a **model-level systematic failure**, distinct from F7 (which is per-sample wrong
response type choice by an otherwise functional model).

### Observed in

| Model | Pattern | Observed behaviour |
|---|---|---|
| `phi4-mini-instruct` Q8_0 | Never calls tools | 73/80 samples on small tier produced no tool call; all 18 correct samples expected no tool call; called a tool in 7/80 cases, all mostly wrong |
| `functionally-small-v2.4` Q4_0 | Random tool selection | tool_name: I in 58/80 (small) and 75/104 (medium); calls unrelated tools like `HassLawnMowerStartMowing` for fan queries, `HassShoppingListAddItem` for occupancy queries |

### Notes

- For phi4-mini: the model likely uses a different system-prompt or tool-spec format. Needs
  investigation of whether the llama.cpp server is correctly activating its tool-calling mode
  (check `/v1/models` tool_call support, or try with explicit `tool_choice: required`).
- For functionally-small-v2.4: the v2.4 and v3.1 models use different function-calling formats.
  The v2.4 model (`meetkai/functionary-small-v2.4-GGUF`) was released before the OpenAI
  tool-calling standard was finalized and expects a different prompt structure. Do not compare
  v2.4 accuracy against v3.1 or other models; treat it as incompatible with the current setup.

### Potential mitigations

- For phi4: investigate prompt format (chat template, tool spec), try `tool_choice: required`
  in the API call, check llama.cpp chat template detection for this model family.
- For functionally-2.4: use v3.1 only; v2.4 is functionally superseded and format-incompatible.

---

## Failure types to watch for (not yet observed)

- **F3 — Hallucinated tool name**: model invents a tool not in the provided list
- **F8 — Wrong domain filter**: correct tool and entity name, but wrong `domain` value passed

### Open question: HassNevermind vs empty for gibberish

`all-text-gibberish-noise-001` ("asdf qwerty zxcv nnnn") expects `[]` (no tool call), but the
model called `HassNevermind`. The test scored I. If HassNevermind is intended to signal "I
didn't understand", calling it for gibberish may be a valid model behaviour. Consider whether
the test expectation should accept `HassNevermind({})` as an equivalent correct answer here.

---

---

## F1.partial — Partial friendly name (truncation)

### Description

A sub-pattern of F1 where the model uses a truncated version of the friendly name rather than
a full entity ID. The model knows it should use a name (not an entity ID) but picks only a
partial match — typically dropping a suffix word like "Weather", "Light", or "Lock".

### Observed in

| Test case ID | Input | Expected `name` | Actual `name` |
|---|---|---|---|
| `small-limit-weather_forecast-001` | "what's the weather forecast for tomorrow" | `Home Weather` | `Home` |

### Notes

Distinct from F1 proper (which uses snake_case entity IDs). Here the model appears to be
pattern-matching on how the entity might be named by a user rather than the exact inventory
name. Could be reduced by repeating `names:` as a more prominent key in the inventory format
or by adding an instruction to always copy the name verbatim.

---

## F6 — Wrong call count

### Description

Model makes too many or too few tool calls. Seen in M2 enormous tier (3 cases). Typically the
model calls an extra tool (e.g. also calls `HassGetState` after completing the primary action)
or splits a single-entity request into multiple calls.

### Observed in

M2 enormous tier: 3 cases (call_count dimension = I).

---

## F7 — Plain text / wrong response type

### Description

Model responds in prose when a tool call is expected (`response_type: I`, answer is `[]`), or
calls a tool when the expected response type is conversational/error. The `response_type`
dimension captures both directions.

### Observed in

| Run | Cases | Direction |
|-----|-------|-----------|
| M2 small (80) | 7 | Mix of called-when-shouldn't and didn't-call-when-should |
| M2 enormous (146) | 14 | Predominantly didn't-call for state queries in large inventory |
| 2026-03-04 small (80) | 8 | 7 called-when-shouldn't, 1 didn't-call-when-should |

**Called when shouldn't (2026-03-04 small run):**
- 2 × unavailable entity: model called `HassTurnOn` for entities marked unavailable
- 1 × `"the kitchen is too hot"` → `HassClimateSetTemperature` (unilateral action on ambient complaint)
- 1 × `"it's getting dark"` → `HassClimateSetTemperature` (non-sequitur tool choice)
- 1 × `"turn off the lights in the"` (incomplete) → `HassTurnOff` (model guessed intent)
- 1 × `"asdf qwerty zxcv nnnn"` (gibberish) → `HassNevermind` (see open question below)
- 1 × `"order more paper towels from amazon"` → `HassShoppingListAddItem` (see F9)

**Didn't call when should (2026-03-04 small run):**
- 1 × `"good morning"` → `[]` (expected 2 calls: `HassTurnOn` + `HassClimateSetTemperature`)

### Notes

High `response_type: I` rate in state_query cases at the enormous tier may reflect the model
giving up on tool calling when the entity list is very long and it can't identify the right entity.

For the "called when shouldn't" cases in the small run, the pattern is that the model is
too eager to act on ambient complaints ("too hot", "getting dark") and incomplete/nonsense
utterances. Prompt guidance on when to refuse may help.
