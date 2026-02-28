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

### Potential prompt mitigations to try

- Add guidance distinguishing when to use `HassClimateGetTemperature` vs `HassGetState`
- Clarify in the prompt that climate entities should use climate-specific intents

---

## Observations by model / run

| Date | Model | Test set | n | Accuracy | F1 cases | F2 cases | Notes |
|------|-------|----------|---|----------|----------|----------|-------|
| 2026-02-28 | Qwen2.5-7B-Instruct Q4_K_M | small (25) | 25 | 92% (23/25) | 1 | 1 | First full run |

---

## Failure types to watch for (not yet observed)

- **F3 — Hallucinated tool name**: model invents a tool not in the provided list
- **F4 — Missing required argument**: correct tool, but omits a key argument (e.g. no `name`)
- **F5 — Extra/spurious arguments**: correct tool and required args present, but extra args added
- **F6 — Wrong call count**: too many or too few tool calls for the request
- **F7 — Plain text instead of tool call**: model responds in prose rather than calling a tool
- **F8 — Wrong domain filter**: correct tool and entity name, but wrong `domain` value passed
