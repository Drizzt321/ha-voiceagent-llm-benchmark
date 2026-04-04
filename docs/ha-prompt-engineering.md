# HA Voice Benchmark — Prompt Engineering Notes

**Purpose:** Track prompt variants, rationale, and results. One change at a time.
**Baseline:** Qwen2.5-7B-Instruct bartowski Q4_K_M, small tier (80 cases), ~56-57% accuracy.
**Key constraint:** Entity inventory format is fixed — must match exactly what HA produces.
  The entity ID is the top-level key, `names:` is the friendly name indented under it.
  Prompt engineering is limited to the instructions block only.

---

## Current Instructions Block (Baseline)

From `docs/ha-prompt-reference.md` — `DEFAULT_INSTRUCTIONS_PROMPT`:

```
You are a voice assistant for Home Assistant.
Answer questions about the world truthfully.
Answer in plain text. Keep it simple and to the point.
When controlling Home Assistant always call the intent tools.
Use HassTurnOn to lock and HassTurnOff to unlock a lock.
When controlling a device, prefer passing just name and domain.
When controlling an area, prefer passing just area name and domain.
When a user asks to turn on all devices of a specific type,
ask user to specify an area, unless there is only one device of that type.
```

**Known weakness:** "prefer passing just name and domain" — "prefer" is weak and doesn't
specify *which* name to use. Models are defaulting to the entity ID (the top-level key in
the inventory YAML) rather than the friendly name under `names:`.

---

## Failure Pattern Summary (from `docs/failure-patterns.md`)

| ID | Name | Count (small/80) | Priority |
|----|------|-----------------|----------|
| F1 | Entity ID used instead of friendly name | ~25 cases | **High — most dominant** |
| F5.area | Spurious `area` argument added | ~13 cases | High — co-occurs with F1 |
| F4 | Missing/wrong argument | ~7 cases | Medium |
| F7 | Wrong response type (called/didn't-call) | ~8 cases | Medium |
| F2 | Wrong tool for similar intent | ~5 cases | Medium |
| F9 | Out-of-scope mapped to nearest tool | ~1 case | Low |

**F5.area likely reduces automatically if F1 is fixed** — the model pads with `area` when
using entity IDs to show its reasoning. Fixing F1 may incidentally fix F5.

---

## Model Disposition (post-baseline runs)

| Model | Disposition | Reason |
|-------|------------|--------|
| Qwen2.5-7B Q5_K_M | **Keep — primary** | Best overall, 67.5%/64.4% small/medium |
| Qwen2.5-7B Q4_K_M | **Keep — reference** | ~10% behind Q5, useful quant comparison |
| Functionary-3.1 Q5_K_M | **Keep — rerun at larger ctx** | 60% small but ctx20000 suspected limiting medium |
| Functionary-3.1 Q4_K_M | **Keep — monitor** | Competitive, same ctx caveat |
| Functionary-3.1 Q3_K_M | **Deprioritize** | 42.5%/36.5% — below Q4, not worth prompt engineering effort |
| Qwen3-8B Q4_K_M | **Monitor** | Underperforms Qwen2.5-7B — reasoning training likely hurting structured output |
| Meta-Llama-3.1-8B Q4_K_M | **Drop** | 32.5%/35.6% — clear underperformer vs Qwen at same size |
| Phi-4-mini Q8_0 | **Drop** | 22.5% small, broken on medium |
| Llama3.2-3B (F16 + Q8_0) | **Drop** | Small model ceiling ~10-15% |
| Functionary-2.4 Q4_0 | **Drop** | Completely broken |

---

## Prompt Variant Iteration Plan

### Iteration 1 — Strengthen name instruction (CURRENT)

**Change:** Replace "prefer passing just name and domain" with "always pass the friendly
name from `names:` and the domain."

**Full changed line:**
```
When controlling a device, always pass the friendly name from `names:` and the domain.
```

**Hypothesis:** "prefer" is not directive enough. "always" + explicit pointer to `names:`
field directly addresses F1 without restructuring anything else.

**Success criterion:** Meaningful accuracy improvement on small tier vs 56-57% baseline.
**Next if succeeds:** Move to next highest-priority failure pattern (F2 lock direction, F7 refusal).
**Next if fails:** Try adding the negative form (Iteration 2).

---

### Iteration 2 — Add negative constraint (if Iteration 1 insufficient)

**Change:** Also add explicit "never use entity ID" instruction.

```
When controlling a device, always pass the friendly name from `names:` and the domain.
Never use the entity ID (the `domain.object_id` key) as the name argument.
```

**Hypothesis:** Positive + negative framing together may be needed if the entity ID's
visual prominence in the inventory still dominates.

---

### Iteration 3+ — Address remaining failures (after F1 resolved)

Priority order once F1/F5 are addressed:

1. **F2 — Lock direction:** The lock instruction exists but models still get it wrong.
   May need to be more prominent or repeated. Candidate: move it closer to or within
   the entity list preamble.

2. **F7 — Over-eager action:** Models act on ambient complaints ("it's too hot"),
   incomplete utterances, gibberish. Candidate instruction:
   "If no provided tool directly fulfills the user's request, respond without calling
   any tool."

3. **F9 — Out-of-scope:** Model maps Amazon order to HA shopping list. Related to F7
   refusal guidance — may be covered by the same instruction.

4. **F4 — domain vs device_class:** Models use `device_class` filter instead of `domain`.
   Candidate: clarify in tool descriptions or add instruction
   "Use `domain` (not `device_class`) to filter by entity type."
   **2026-04-04 result: TESTED AND REJECTED.** Caused regression (-3.0pp Qwen3 small).
   Device_class misuse unchanged. Do not revisit as system prompt instruction — address
   in tool descriptions or inventory format instead.

### Iteration 4 — F7 refusal line (adopted 2026-04-04)

Added: `"If no provided tool directly fulfills the user's request, respond without calling any tool."`

**Result:** +5.8pp Qwen3 small, +3.5pp medium. Broad collateral improvements (F1, F4, F5 reduced). See `reports/prompt-tweaking-cross-config-comparison-2026-04-04.md`.

### Future F7 refinement variants (not yet tested)

The current F7 line is effective. These are theoretical variations that could be tested
if further improvement is needed on edge cases, incomplete commands, or unavailable entities:

1. **"Ask first" variant** — encourages clarification over silence:
   `"If no provided tool directly fulfills the user's request, ask for clarification or respond without calling any tool."`
   Target: ambiguous cases where the model currently acts instead of asking.
   Risk: could cause over-asking on clear but casual commands.

2. **"Unclear intent" trigger** — scopes refusal to ambiguity as well as tool mismatch:
   `"If the user's intent is unclear or no provided tool directly fulfills the request, respond without calling any tool."`
   Target: incomplete commands ("turn off the lights in the"), ambiguous phrasing.
   Risk: "unclear" is subjective — may suppress valid casual utterances. **Highest-signal next test.**

3. **"Unavailable entity" variant** — explicitly addresses unavailable device failures:
   `"If no provided tool directly fulfills the user's request, or the target device is unavailable, respond without calling any tool."`
   Target: persistent unavailable-entity F7 failures (smart bulb E7A2).
   Risk: model may not connect "unavailable" to `state: unavailable` in the inventory YAML format.

4. **Positive framing** — flips from prohibition to confidence threshold:
   `"Only call intent tools when you are confident the correct tool and entity are available to fulfill the request."`
   Target: covers both ambiguous intents and unavailable entities elegantly.
   Risk: "confident" is a fuzzy threshold — could suppress borderline-correct calls that currently pass.

---

## Iteration 3 — Add HassGetState guidance for sensor/binary_sensor/state queries

**Config file:** `configs/system_prompt_iter3_getstate.txt`

**Change from Iteration 2:** Added one new line targeting F7 refusals on sensor and binary_sensor state queries.

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

**What changed and why:**
- Added: `Prefer HassGetState for sensor and binary_sensor state queries, and for checking the state of locks, covers, and media players.`
- "Prefer" (not "always") — soft nudge, avoids over-application to action intents
- "checking the state of" for locks/covers/media_player — scopes to read-only queries, preserves HassTurnOn/Off, HassSetPosition, HassMediaPause etc. for action intents
- Explicit domain list removes ambiguity about what counts as a state query — which is where models were hesitating
- Confirmed by inventory inspection: all F7 refusal targets (binary_sensor.office_occupancy, binary_sensor.kitchen_smoke, binary_sensor.living_room_motion) exist in small inventory — failures are genuine model hesitation, not inventory gaps

**Hypothesis:** Eliminates or significantly reduces F7 binary_sensor/sensor refusals without disturbing F1/F2 patterns.

**Success criterion:** F7 count drops for top models (qwen3, qwen2.5) on small tier. No meaningful regression on F1 or F2.

**Models to run:** Full set (qwen3-8b-q4, qwen2.5-7b-q5, qwen2.5-7b-q4, functionary-3.1-q5, functionary-3.1-q4). **Do NOT include meta-llama-3.1-8B in this run** — see per-model prompt finding below.

---

## Per-model prompt finding (2026-03-05 isolated runs)

**`/no_think` is not model-neutral.** Fully characterized across all tested models:

| Model | Effect | Evidence |
|-------|--------|----------|
| Qwen3-8B | **Essential** — 5.6× latency reduction, +11pp accuracy | Thinking tokens suppressed: 22,631→2,868 aggregate; 9.56s→1.70s mean |
| Qwen2.5-7B | **Neutral** — no measurable effect | ±1–5pp across 4 runs = normal run-to-run variance; latency delta ~0.1s noise |
| Meta-Llama-3.1-8B | **Harmful** — F1 nearly doubled (7→13 small), F2 +5 medium | Model treats token as literal instruction text, degrading entity name reasoning |
| Functionary-3.1 | Assumed neutral (not tested in isolation) | F2-ceiling limited; prompt changes have minimal effect regardless |

**Conclusion: `/no_think` is safe to include in a shared prompt for all models except meta-llama3.1-8B**, which requires its own prompt without it.

Other findings from isolated meta-llama runs:
- With Run 2 prompt (no `/no_think`, no area clause): 55.0% small / 46.2% medium — best result for this model
- With Run 3 prompt (+ area clause + `/no_think`): 47.5% small / 41.3% medium — clear regression
- Previous multi-model run hangs (620s/606s) were KV state corruption from back-to-back runs, NOT prompt-related
- New decode runaway (14,823 tokens, 578s) on medium with Run 3 prompt — attempt_timeout essential

**Implication: shared system prompt is invalid across model families.** Per-model prompts required:

| Model | Best prompt so far | Key constraints |
|-------|-------------------|-----------------|
| Qwen3-8B | Iteration 3 (getstate + area split + `/no_think`) | `/no_think` essential for latency |
| Qwen2.5-7B | Iteration 3 (getstate + area split + `/no_think`) | `/no_think` neutral but harmless; safe to share prompt |
| Functionary-3.1 | Either (F2-ceiling limited) | Prompt has minimal effect |
| Meta-Llama-3.1-8B | Run 2 wording + HassGetState line, no area clause, no `/no_think` | Still TBD — Iteration 3b pending |

**Iteration 3b — meta-llama-only prompt:**
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
```
(No `/no_think`. No explicit area/device split clause beyond the existing area line.) **Requires attempt_timeout set before running.**

---

## Results Log

| Date | Variant | Model | Tier | n | Accuracy | Delta | Notes |
|------|---------|-------|------|---|----------|-------|-------|
| 2026-03-04 | Baseline | Qwen2.5-7B bartowski Q4_K_M GPU | small | 80 | 56.2% | — | Reference run |
| 2026-03-04 | Baseline | Qwen2.5-7B bartowski Q4_K_M CPU | small | 80 | 57.5% | +1.3% | FP non-determinism, not significant |
| 2026-03-05 | Baseline | Qwen2.5-7B bartowski Q5_K_M GPU | small | 80 | 67.5% | — | New high watermark — clear winner |
| 2026-03-05 | Baseline | Qwen2.5-7B bartowski Q5_K_M GPU | medium | 104 | 64.4% | — | Consistent across tiers |
| 2026-03-05 | Baseline | Qwen2.5-7B bartowski Q4_K_M GPU | medium | 104 | 53.8% | — | ~10% behind Q5 on medium |
| 2026-03-05 | Baseline | Functionary-3.1 Q5_K_M GPU ctx20000 | small | 80 | 60.0% | — | Competitive on small |
| 2026-03-05 | Baseline | Functionary-3.1 Q5_K_M GPU ctx20000 | medium | 104 | 46.2% | — | Drops on medium — ctx constraint suspected |
| 2026-03-05 | Baseline | Functionary-3.1 Q4_K_M GPU ctx24000 | small | 80 | 56.2% | — | |
| 2026-03-05 | Baseline | Functionary-3.1 Q4_K_M GPU ctx24000 | medium | 104 | 48.1% | — | |
| 2026-03-05 | Baseline | Functionary-3.1 Q3_K_M GPU ctx32768 | small | 80 | 42.5% | — | |
| 2026-03-05 | Baseline | Functionary-3.1 Q3_K_M GPU ctx32768 | medium | 104 | 36.5% | — | |
| 2026-03-05 | Baseline | Qwen3-8B Q4_K_M GPU ctx22000 | small | 80 | 52.5% | — | Underperforms Qwen2.5-7B despite larger/newer |
| 2026-03-05 | Baseline | Qwen3-8B Q4_K_M GPU ctx22000 | medium | 104 | 44.2% | — | |
| 2026-03-05 | Baseline | Meta-Llama-3.1-8B Q4_K_M GPU ctx25000 | small | 80 | 32.5% | — | Clear underperformer |
| 2026-03-05 | Baseline | Meta-Llama-3.1-8B Q4_K_M GPU ctx25000 | medium | 104 | 35.6% | — | |
| 2026-03-05 | Baseline | Phi-4-mini Q8_0 GPU ctx28000 | small | 80 | 22.5% | — | |
| 2026-03-05 | Baseline | Phi-4-mini Q8_0 GPU ctx28000 | medium | 39 | 2.6% | — | Partial run (39/40); 38/39 response_type failures — broken on medium |
| 2026-03-05 | Baseline | Llama3.2-3B F16 GPU ctx13000 | small | 80 | 15.0% | — | Small model ceiling |
| 2026-03-05 | Baseline | Llama3.2-3B F16 GPU ctx13000 | medium | 104 | 8.7% | — | |
| 2026-03-05 | Baseline | Llama3.2-3B Q8_0 GPU ctx30000 | small | 80 | 11.2% | — | |
| 2026-03-05 | Baseline | Llama3.2-3B Q8_0 GPU ctx30000 | medium | 104 | 8.7% | — | |
| 2026-03-05 | Baseline | Functionary-2.4 Q4_0 GPU ctx28000 | small | 80 | 2.5% | — | Completely broken |
| 2026-03-05 | Baseline | Functionary-2.4 Q4_0 GPU ctx28000 | medium | 104 | 0.0% | — | Dead |
| 2026-03-05 | Iteration 1 (always_name) | Qwen2.5-7B Q5_K_M | small | 80 | 73.8% | +6.3pp | Every model improved, no regressions |
| 2026-03-05 | Iteration 1 (always_name) | Qwen2.5-7B Q5_K_M | medium | 104 | 69.2% | +4.8pp | |
| 2026-03-05 | Iteration 1 (always_name) | Qwen2.5-7B Q4_K_M | small | 80 | 67.5% | +11.3pp | |
| 2026-03-05 | Iteration 1 (always_name) | Qwen2.5-7B Q4_K_M | medium | 104 | 61.5% | +7.7pp | |
| 2026-03-05 | Iteration 1 (always_name) | Qwen3-8B Q4_K_M | small | 80 | 70.0% | +17.5pp | |
| 2026-03-05 | Iteration 1 (always_name) | Qwen3-8B Q4_K_M | medium | 104 | 64.4% | +20.2pp | |
| 2026-03-05 | Iteration 1 (always_name) | Functionary-3.1 Q5_K_M | small | 80 | 66.2% | +6.2pp | |
| 2026-03-05 | Iteration 1 (always_name) | Functionary-3.1 Q5_K_M | medium | 104 | 57.7% | +11.5pp | |
| 2026-03-05 | Iteration 1 (always_name) | Functionary-3.1 Q4_K_M | small | 80 | 61.3% | +5.1pp | |
| 2026-03-05 | Iteration 1 (always_name) | Functionary-3.1 Q4_K_M | medium | 104 | 56.7% | +8.6pp | |
| 2026-03-05 | Iteration 1 (always_name) | Meta-Llama-3.1-8B Q4_K_M | small | 80 | 58.8% | +26.3pp | Biggest mover; area/name conflict side effect |
| 2026-03-05 | Iteration 1 (always_name) | Meta-Llama-3.1-8B Q4_K_M | medium | 104 | 53.8% | +18.2pp | |
| 2026-03-05 | Iteration 1 (always_name) | Llama3.2-3B F16 | small | 80 | 27.5% | +12.5pp | Dropped after Run 2 — accuracy ceiling too low |
| 2026-03-05 | Iteration 1 (always_name) | Llama3.2-3B F16 | medium | 104 | 17.3% | +8.6pp | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Qwen3-8B Q4_K_M | small | 80 | 81.2% | +28.7pp total | /no_think: latency 9.56s→1.70s mean; new leader |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Qwen3-8B Q4_K_M | medium | 104 | 71.2% | +27.0pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Qwen2.5-7B Q5_K_M | small | 80 | 73.8% | +6.3pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Qwen2.5-7B Q5_K_M | medium | 104 | 68.3% | +3.9pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Qwen2.5-7B Q4_K_M | small | 80 | 68.8% | +12.6pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Qwen2.5-7B Q4_K_M | medium | 104 | 67.3% | +13.5pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Functionary-3.1 Q5_K_M | small | 80 | 61.3% | +1.3pp total | Prompt changes minimal effect — F2 capability ceiling |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Functionary-3.1 Q5_K_M | medium | 104 | 58.7% | +12.5pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Functionary-3.1 Q4_K_M | small | 80 | 60.0% | +3.8pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Functionary-3.1 Q4_K_M | medium | 104 | 52.9% | +4.8pp total | |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Meta-Llama-3.1-8B Q4_K_M | small | 80 | 47.5% | +15.0pp total | REGRESSION vs R2 (-11.3pp): area split clause backfired; F7 rose to 20 |
| 2026-03-05 | Iteration 2 (area_split+no_think) | Meta-Llama-3.1-8B Q4_K_M | medium | 104 | 49.0% | +13.4pp total | Two 600s+ server stalls; attempt_timeout critical before rerun |
| 2026-03-05 | Isolated: meta-llama Run2-prompt | Meta-Llama-3.1-8B Q4_K_M | small | 80 | 55.0% | — | Best result for this model; clean run (max 5.67s, no hangs) |
| 2026-03-05 | Isolated: meta-llama Run2-prompt | Meta-Llama-3.1-8B Q4_K_M | medium | 104 | 46.2% | — | Clean run (max 12.09s); F1=18, F2=7 |
| 2026-03-05 | Isolated: meta-llama Run3-prompt | Meta-Llama-3.1-8B Q4_K_M | small | 80 | 47.5% | -7.5pp vs R2 | /no_think degrades F1: 7→13; token is literal text for this model |
| 2026-03-05 | Isolated: meta-llama Run3-prompt | Meta-Llama-3.1-8B Q4_K_M | medium | 104 | 41.3% | -4.9pp vs R2 | F2: 7→12; decode runaway 14823 tok on fan speed cmd (578s) |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Qwen3-8B Q4_K_M | small | 80 | 78.8% | −2.4pp vs R3 | Slight regression — prompt dilution or noise; run-to-run variance ±3pp |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Qwen3-8B Q4_K_M | medium | 104 | 67.3% | −3.9pp vs R3 | |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Qwen2.5-7B Q5_K_M | small | 80 | 76.2% | +2.4pp vs R3 | Best run for this model |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Qwen2.5-7B Q5_K_M | medium | 104 | 69.2% | +0.9pp vs R3 | |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Qwen2.5-7B Q4_K_M | small | 80 | 68.8% | =0pp vs R3 | Flat |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Qwen2.5-7B Q4_K_M | medium | 104 | 66.3% | −1.0pp vs R3 | |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Functionary-3.1 Q5_K_M | small | 80 | 63.7% | +2.4pp vs R3 | Lock direction hint may have helped |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Functionary-3.1 Q5_K_M | medium | 104 | 54.8% | −3.9pp vs R3 | |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Functionary-3.1 Q4_K_M | small | 80 | 60.0% | =0pp vs R3 | |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Functionary-3.1 Q4_K_M | medium | 104 | 54.8% | +1.9pp vs R3 | |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Meta-Llama-3.1-8B Q4_K_M | small | 80 | 43.8% | −3.7pp vs R3 | /no_think regression confirmed again; name dim=2 (low) but args=26 (high) |
| 2026-03-05 | Iteration 3 (getstate+no_think) | Meta-Llama-3.1-8B Q4_K_M | medium | 104 | 40.4% | −8.6pp vs R3 | Clean run (max 11.71s); no hangs |
| — | Iteration 3b (getstate, no /no_think, no area clause) | Meta-Llama-3.1-8B Q4_K_M | — | — | — | — | Pending — per-model prompt; attempt_timeout required |
| 2026-03-05 | Iteration 3 R2 (getstate+no_think) | Qwen3-8B Q4_K_M | small | 80 | 78.8% | =0pp vs R1 | Stable; medium improved +3.9pp; gap over qwen2.5-q5 widened to 5pp avg |
| 2026-03-05 | Iteration 3 R2 (getstate+no_think) | Qwen3-8B Q4_K_M | medium | 104 | 71.2% | +3.9pp vs R1 | |
| 2026-03-05 | Iteration 3 R2 (getstate+no_think) | Qwen2.5-7B Q5_K_M | small | 80 | 73.8% | −2.4pp vs R1 | Within variance; on/off 89% (still leads qwen3 by ~6pp) |
| 2026-03-05 | Iteration 3 R2 (getstate+no_think) | Qwen2.5-7B Q5_K_M | medium | 104 | 66.3% | −2.9pp vs R1 | multi_call dropped 80%→60%; ambiguous_edge collapsed 50%→0% |
| 2026-04-04 | F7 refusal (3-run avg) | Qwen3-8B Q4_K_M | small | 80 | 84.6% ± 0.7% | +5.8pp vs Iter3 | **Best result for Qwen3 small**; refusal line reduces F7 called-when-shouldn't |
| 2026-04-04 | F7 refusal (3-run avg) | Qwen3-8B Q4_K_M | medium | 104 | 74.7% ± 0.6% | +3.5pp vs Iter3 | Stable improvement; collateral F1/F4/F5 reduction |
| 2026-04-04 | F7 refusal (3-run avg) | Qwen2.5-7B Q5_K_M | small | 80 | 77.1% ± 2.6% | +0.9pp vs Iter3 | Within variance |
| 2026-04-04 | F7 refusal (3-run avg) | Qwen2.5-7B Q5_K_M | medium | 104 | 72.8% ± 2.4% | +3.6pp vs Iter3 | Borderline improvement |
| 2026-04-04 | F4 domain (3-run avg) | Qwen3-8B Q4_K_M | small | 80 | 75.8% ± 0.7% | −3.0pp vs Iter3 | **Regression**; device_class misuse unchanged; F5 inflated |
| 2026-04-04 | F4 domain (3-run avg) | Qwen3-8B Q4_K_M | medium | 104 | 69.2% ± 0.0% | −2.0pp vs Iter3 | Regression; domain instruction confuses arg construction |
| 2026-04-04 | F4 domain (3-run avg) | Qwen2.5-7B Q5_K_M | small | 80 | 74.6% ± 1.9% | −1.6pp vs Iter3 | Within variance; Qwen2.5 already uses domain correctly |
| 2026-04-04 | F4 domain (3-run avg) | Qwen2.5-7B Q5_K_M | medium | 104 | 68.3% ± 1.9% | −0.9pp vs Iter3 | Within variance |
| 2026-04-04 | F7+F4 combined (3-run avg) | Qwen3-8B Q4_K_M | small | 80 | 79.6% ± 1.4% | +0.8pp vs Iter3 | F7 gain offset by F4 regression; net neutral |
| 2026-04-04 | F7+F4 combined (3-run avg) | Qwen3-8B Q4_K_M | medium | 104 | 74.0% ± 2.5% | +2.8pp vs Iter3 | Within variance |
| 2026-04-04 | F7+F4 combined (3-run avg) | Qwen2.5-7B Q5_K_M | small | 80 | 78.3% ± 1.9% | +2.1pp vs Iter3 | Within variance |
| 2026-04-04 | F7+F4 combined (3-run avg) | Qwen2.5-7B Q5_K_M | medium | 104 | 69.6% ± 2.8% | +0.4pp vs Iter3 | Within variance |
