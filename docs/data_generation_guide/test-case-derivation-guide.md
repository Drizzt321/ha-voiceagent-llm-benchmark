# Home Assistant Voice LLM Benchmark — Test Case Derivation Guide

**Purpose:** How to derive test cases from the Enormous tier downward to Large, Medium,
and Small tiers. Covers tier applicability rules, field adaptation, entity retargeting,
partial match handling, and the push-down algorithm.

**Audience:** An LLM agent or human adapting Enormous-tier NDJSON test cases for smaller
inventory tiers, without access to the original discussion history.

**Created:** 2026-03-02 (M2 Step 12)

**See also:**
- `test-case-generation-principles.md` — how to generate seed test cases (format spec, §7 entity_id safety)
- `derivation-guide.md` — how YAML entity tiers were derived (explains which entities exist per tier)
- `generation-principles.md` — YAML inventory generation principles
- `verify_entity_consistency.py` — post-derivation verification

---

## 1. Overview

Test case derivation is analogous to YAML tier derivation but requires more judgment.
YAML derivation is mechanical (filter by entity list). Test case derivation involves
deciding whether a case still makes sense with fewer entities, and sometimes adapting
it to target different entities.

The Enormous tier is the seed tier — all initial test cases are written against it.
Derivation produces Large, Medium, and Small versions of applicable cases.

### What changes between tiers

| Field | Changes? | How |
|-------|----------|-----|
| `id` | Yes | Tier prefix: `enormous-` → `large-`, `medium-`, `small-` |
| `utterance` | Sometimes | If retargeted to a different entity, the utterance must change to match |
| `expected_tool_calls` | Sometimes | Entity names and areas may change if retargeted |
| `alternative_expected_tool_calls` | Sometimes | Alternatives referencing missing entities must be removed |
| `expected_response_type` | Rarely | Only if the case fundamentally changes meaning |
| `inventory_tier` | Yes | Updated to target tier |
| `inventory_file` | Yes | Updated to target tier's combined.yaml path |
| `metadata.target_entities` | Sometimes | Updated if retargeted; verified against tier YAML |
| `metadata.target_areas` | Sometimes | Updated if area doesn't exist in tier |
| `metadata.case_key` | No | **Never changes** — this is the cross-tier join key |
| `metadata.notes` | Sometimes | Add tier-specific notes if behavior differs |

### What never changes

The `case_key` is the cross-tier identity. It must be identical across all tiers where
a case exists. This enables `GROUP BY case_key` analysis comparing the same logical
test across different inventory sizes.

---

## 2. Tier Applicability Rules

### Rule 1: All target entities must exist in the tier

For cases with specific `target_entities`, check whether ALL listed entity_ids exist
in the target tier's YAML inventory. The entity_ids are the `entity_id` fields in the
per-domain YAML files.

- **All present** → Push down (may need field updates but case is applicable).
- **None present** → Skip this tier (case doesn't apply).
- **Partial match** → Apply the retargeting rules in §3.

### Rule 2: Area-scoped commands require the area to exist

For cases with empty `target_entities` but specific `target_areas`, check whether
the referenced area exists in the tier's `areas.yaml`.

- **Area exists** → Push down. The entities in that area may differ, so the "turn off
  everything in the office" case may affect fewer devices, but the command is still valid.
- **Area doesn't exist** → Skip this tier.

### Rule 3: Inventory-independent cases push to all tiers

Cases with `inventory_tier: "all"` (utility, conversational, out-of-scope, gibberish)
are included in every tier unconditionally. They don't reference specific entities or
areas. The merge script copies them into each tier's combined test file with the
appropriate `inventory_file` path filled in.

### Rule 4: Empty target_entities + empty target_areas → push to all tiers

Cases like edge cases with no specific entity or area reference (e.g., "turn on the
swimming pool lights" which tests for a nonexistent entity) are tier-independent in
principle. Push them to all tiers — the test is whether the model correctly handles
the absence.

However, review whether the "absence" is still true in the target tier. If a smaller
tier happens to have a pool light entity that the Enormous tier didn't, the case would
need re-evaluation (unlikely but worth checking).

---

## 3. Handling Partial Entity Matches — Retargeting

When some but not all `target_entities` exist in a smaller tier, there are three
strategies, applied in priority order:

### Strategy A: Retarget to an equivalent entity (preferred)

If the missing entity has a functional equivalent in the tier (same domain, similar
role, tests the same reasoning), retarget the case:

- Update `utterance` to reference the new entity's name/area
- Update `expected_tool_calls` arguments
- Update `target_entities` and `target_areas`
- Keep the same `case_key` — the logical test is preserved
- Add a note: "Retargeted from [original entity] to [new entity] for [tier] tier"

**Example:** Enormous has `lock.patio_door` (state: jammed) testing unusual lock states.
If `lock.patio_door` doesn't exist in Medium but `lock.front_door` does and happens to
have an interesting state, retarget. If no lock entity has an interesting state in Medium,
skip the case (don't force a retarget that loses the test's purpose).

### Strategy B: Simplify multi-entity cases

For cases targeting multiple entities (like the backyard water disambiguation with 4
switch entities), the case may still be valid with fewer entities in the same area:

- If the area still has at least 2 entities that create ambiguity, keep the case
- Update `target_entities` to only list the entities that exist in this tier
- The utterance and expected_tool_calls may not need to change if they use area-scoping
- Add a note explaining the reduced entity set

### Strategy C: Skip the case

If retargeting would change what the case fundamentally tests, skip it for this tier.
A case that exists only in larger tiers is meaningful data — it shows which tests require
a certain inventory complexity to be valid.

**Do not force-fit cases.** A disambiguation test that becomes a simple single-entity
test after retargeting has lost its purpose. Skip it and let the cross-tier analysis
show the gap.

---

## 4. Adapting Alternative Expected Tool Calls

When pushing down, each alternative in `alternative_expected_tool_calls` must also be
checked:

1. **Entity references in alternatives** — if an alternative targets an entity that
   doesn't exist in the tier, remove that alternative entirely.
2. **Quality ratings may change** — if the tier has fewer entities, what was "degraded"
   in Enormous (because a better option existed) might become "acceptable" in Small
   (because it's the only option).
3. **New alternatives may appear** — in a smaller tier, area-scoped commands might
   resolve unambiguously to a single entity, making by-name targeting an `equivalent`
   alternative that wasn't worth listing in Enormous.

When in doubt, err toward removing alternatives rather than keeping stale ones. A case
with no alternatives is fine — it just means there's one right answer in that tier.

---

## 5. The Push-Down Algorithm

This describes the mechanical process. It can be implemented as a script or performed
by an LLM with judgment.

### Input

- Enormous NDJSON files (all `*_test_cases.ndjson` in `enormous/`)
- YAML inventories for all four tiers
- Target tier name (large, medium, or small)

### Process

```
For each NDJSON file in enormous/:
  For each test case:
    1. Read inventory_tier:
       - If "all" → copy to target tier, update inventory_file → DONE
       - If "enormous" → continue to step 2

    2. Read target_entities:
       - If empty AND target_areas is empty → copy to target tier → DONE
       - If empty AND target_areas is non-empty → check area exists in tier
         - Area exists → copy, update tier fields → DONE
         - Area missing → SKIP
       - If non-empty → continue to step 3

    3. Check entity existence:
       - Load all entity_ids from target tier's YAML files
       - For each entity in target_entities:
         - Present in tier? Mark as FOUND
         - Missing from tier? Mark as MISSING

    4. Apply retargeting decision:
       - All FOUND → copy, update tier fields → DONE
       - All MISSING → attempt retarget (Strategy A) or SKIP
       - Partial match → attempt simplification (Strategy B) or retarget or SKIP

    5. Update fields for target tier:
       - id: replace tier prefix
       - inventory_tier: set to target tier
       - inventory_file: set to target tier's combined.yaml path
       - utterance: update if retargeted
       - expected_tool_calls: update names/areas if retargeted
       - alternative_expected_tool_calls: filter out invalid alternatives
       - target_entities: update to reflect what exists in tier
       - target_areas: update if areas changed
       - notes: append tier-specific adaptation notes

    6. Write to target tier's NDJSON file (same filename as source)
```

### Output

Per-domain NDJSON files in the target tier directory, following the same file naming
convention as Enormous.

---

## 6. Retargeting Decision Framework

Not every case can or should be retargeted. Use this framework:

### Good retargets (preserve test purpose)

- Simple control case → same domain, different entity in tier
  (e.g., "turn on kitchen light" → "turn on living room light")
- State query → same domain, different entity with same state
- Area command → same area exists, just fewer entities in it

### Bad retargets (lose test purpose — skip instead)

- Disambiguation case → tier only has one entity in the relevant area
  (disambiguation requires multiple candidates)
- Unusual state case → no entity in tier has that state
  (jammed lock, unavailable sensor — these need specific entity states)
- Cross-domain collision → one of the colliding domains is absent from the tier
  (TV + TV plug needs both media_player and switch entities)
- Name collision case → collision doesn't exist in smaller tier

### Edge retargets (judgment call)

- Multi-action → one action's entity exists but other's doesn't
  (could retarget the missing half, but might change the test character)
- Capability-specific test → entity exists but doesn't have the tested feature
  (e.g., brightness test but the tier's light is on/off only)

---

## 7. Handling Expanded (Mutated) Test Cases

When deriving mutated/expanded cases (future Step 12.3), the same push-down rules
apply. Additional considerations:

- Mutations that are entity substitutions should already target tier-appropriate entities
  (the mutation process should be tier-aware)
- Phrasing variations share the same entity targets as their seed — if the seed pushes
  down, the variation should too
- Expanded cases get new `case_key` values but follow the same derivation algorithm

---

## 8. Post-Derivation Verification

After generating derived NDJSON files for each tier:

1. **Run `verify_entity_consistency.py`** with the target tier's data directory.
   This confirms all `target_entities` values in the derived NDJSON exist in that
   tier's YAML.

2. **Count check** — the number of cases should decrease as tiers get smaller:
   Enormous > Large > Medium > Small (for entity-specific cases). `all`-tier cases
   should be identical count across tiers.

3. **case_key continuity** — spot check that derived cases preserve their `case_key`
   values from Enormous.

4. **Retarget audit** — review any cases that were retargeted (look for "Retargeted"
   in notes). Verify the retarget preserves the test's purpose.

```
python3 verify_entity_consistency.py <data_dir> --output <report_dir>
```

---

## 9. Worked Example — Pushing Down a Lock Case

### Enormous case

```json
{
  "id": "enormous-HassTurnOn-lock-front_door-001",
  "utterance": "lock the front door",
  "expected_tool_calls": [{"name": "HassTurnOn", "arguments": {"name": "Front Door Lock", "domain": ["lock"]}}],
  "expected_response_type": "action_done",
  "inventory_tier": "enormous",
  "inventory_file": "test_data/inventories/enormous/combined.yaml",
  "metadata": {
    "target_entities": ["lock.front_door"],
    "target_areas": ["Entry"],
    "case_key": "HassTurnOn-lock-front_door-001",
    "notes": "Counter-intuitive mapping: lock = HassTurnOn."
  }
}
```

### Check: Does lock.front_door exist in Large?

Look in `large/lock.yaml` → yes, `lock.front_door` exists with same name and area.

### Large derived case

```json
{
  "id": "large-HassTurnOn-lock-front_door-001",
  "utterance": "lock the front door",
  "expected_tool_calls": [{"name": "HassTurnOn", "arguments": {"name": "Front Door Lock", "domain": ["lock"]}}],
  "expected_response_type": "action_done",
  "inventory_tier": "large",
  "inventory_file": "test_data/inventories/large/combined.yaml",
  "metadata": {
    "target_entities": ["lock.front_door"],
    "target_areas": ["Entry"],
    "case_key": "HassTurnOn-lock-front_door-001",
    "notes": "Counter-intuitive mapping: lock = HassTurnOn."
  }
}
```

Only `id`, `inventory_tier`, and `inventory_file` changed. Everything else identical.
`case_key` is preserved for cross-tier analysis.

### Check: Does lock.front_door exist in Small?

Look in `small/lock.yaml` → yes (1 lock entity retained). Same adaptation.

---

## 10. Worked Example — Skipping a Disambiguation Case

### Enormous case

```json
{
  "id": "enormous-HassClimateGetTemperature-cross-living_room_temp-001",
  "utterance": "what's the temperature in the living room",
  "metadata": {
    "target_entities": ["climate.living_room_thermostat", "sensor.living_room_temperature"],
    "case_key": "HassClimateGetTemperature-cross-living_room_temp-001",
    "notes": "Disambiguation: climate + sensor in same area."
  }
}
```

### Check: Do both entities exist in Small?

- `climate.living_room_thermostat` → exists in Small? Yes.
- `sensor.living_room_temperature` → exists in Small? No.

Partial match. This is a disambiguation case — its purpose is testing the model's
choice between a climate entity and a sensor entity. With only the climate entity,
there's no disambiguation to test.

### Decision: Skip for Small

The case loses its purpose. Don't retarget — there's no equivalent disambiguation
scenario in the Small inventory. The case exists in Enormous and Large (where both
entities are present) but not Medium or Small. This is meaningful cross-tier data.

---

## 11. Checklist Before Finalizing Derived Tiers

Per target tier:

- [ ] All `all`-tier cases included
- [ ] Empty-target cases included (edge cases with no entity/area reference)
- [ ] Entity-specific cases checked against tier YAML
- [ ] Retargeted cases preserve original test purpose
- [ ] Alternatives pruned for missing entities
- [ ] `case_key` identical to Enormous source
- [ ] `inventory_tier` and `inventory_file` updated correctly
- [ ] `verify_entity_consistency.py` passes with 0 errors
- [ ] Case count is Enormous ≥ Large ≥ Medium ≥ Small (for entity-specific)
- [ ] Retarget decisions documented in notes
