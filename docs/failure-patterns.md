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
| F2 | Wrong tool for semantically similar intent | `tool_name`, `args` |
| F3 | Hallucinated tool name | `no_hallucinated_tools` |
| F4 | Missing required argument | `args` |
| F5 | Extra/spurious arguments | `args` |
| F6 | Wrong call count | `call_count` |
| F7 | Wrong response type (called/didn't-call) | `response_type`, `call_count` |
| F8 | Wrong domain filter | `args` |

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
