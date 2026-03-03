# Home Assistant Synthetic Inventory — Derivation Guide

**Purpose:** How to derive smaller inventory tiers (Large, Medium, Small) from the
Enormous tier by top-down subtraction. Covers methodology, selection principles,
tooling, and design records for each derived tier.

**Audience:** An LLM agent or human producing smaller-scale inventories from an
existing Enormous tier, without access to the original discussion history.

**Created:** 2026-03-01 (Step 11, M2)

**See also:**
- `generation-guide.md` — index and overview
- `generation-principles.md` — how Enormous was generated (§5 disambiguation scenarios
  and §7 naming diversity are particularly relevant for understanding *why* specific
  edge cases matter during derivation)
- `filter_inventory.py` — mechanical extraction tool (adjacent to this file)

---

## 1. Methodology

### Test Quality vs Realism

The tier stack is test data for evaluating LLM home assistant capabilities.
When tradeoffs arise between test quality (edge cases, disambiguation
scenarios, boundary conditions) and realistic home representation (balanced
density, typical device mixes), lean slightly toward test quality. A sparse
but tricky inventory is more useful for evaluation than a realistic but
straightforward one. This preference is mild — egregiously unrealistic
inventories (an area with 15 entities and another with 1) should still be
avoided.

The Enormous tier is the source of truth. Smaller tiers are derived from it by
subtraction, not generated independently. This ensures that every entity in a
smaller tier is identical (same entity_id, name, attributes, state) to its
counterpart in every larger tier that contains it.

**Top-down subtraction.** Each tier is derived from the one above it:
Enormous → Large → Medium → Small. The derivation process is: choose which
areas to drop, then choose which entities within remaining areas to keep.
Never add entities that don't exist in the parent tier.

**Subset property by construction.** Because each tier is strictly subtracted
from its parent, the subset relationship holds automatically:
Enormous ⊃ Large ⊃ Medium ⊃ Small. Any entity present in Small is guaranteed
to exist with identical data in Medium, Large, and Enormous. This is a
mechanical invariant, not something to verify case-by-case.

**Entity identity is preserved.** When an entity appears across multiple tiers,
its entity_id, name, state, and all attributes are byte-for-byte identical.
The only permitted change is area reassignment (see re-area rules below), and
even that preserves all other fields.

---

## 2. Tier Specifications

| Tier | Areas | Entities | Domains | Purpose |
|------|-------|----------|---------|----------|
| Enormous | 20 | ~450 | 14 | Full coverage: every state, every disambiguation, every edge case |
| Large | 14 | ~185 | 14 | Realistic large home. Most edge cases preserved, state coverage reduced |
| Medium | 8 | ~85 | 13 | Single floor + garage. Core edge cases, reduced diversity |
| Small | 5 | ~35 | 11 | Smoke test. Core domains, minimal ambiguity |

### Small Tier — Additional Derivation Principles

**Purpose:** Small is the test floor. If the LLM fails here, something is
fundamentally broken. The inventory should be minimal but not trivial — a
few tricky scenarios embedded in otherwise straightforward areas.

**Entity count:** Target 34-42 entities.
- Below 34, areas become unrealistically sparse — some areas may have no
  within-area complexity at all, reducing their value as test cases.
- Above 42, the tier stops testing minimal-home scenarios and starts
  overlapping with what Medium already covers. The value of a distinct
  “floor” tier diminishes.

**Area density floor:** No area below 4 entities. Three entities (typically
light + sensor + binary_sensor) is technically functional but offers no
within-area complexity. The 4th entity provides either a second controllable
device or a second sensor, making the area feel like a real room with at
least minimal decision-making for the LLM.

**Disambiguation coverage:** At least 2 of 5 areas must contain a
disambiguation scenario (multiple entities of the same domain, cross-domain
collision, or a name that could match elsewhere). 3 of 5 preferred.
Remaining areas serve as “clean” test cases for unambiguous intent
resolution — testing that the LLM handles a simple “turn on the bathroom
light” correctly is also valuable.

**Edge case budget:** Small has room for roughly 4-6 edge case entities
beyond baseline coverage. Allocate to must-keep constraints first
(unavailable actionable, one cross-domain collision, one RGB light),
then should-keep if slots remain. Don’t try to fit more than ~6 dedicated
edge case entities — comprehensive edge case coverage is what Medium and
Large are for.

**Climate at Small:** Single-zone HVAC is realistic and sufficient. One
thermostat in one area tests climate control. Multi-area climate
disambiguation is a Medium-tier concern. Dual climate in the same area
(e.g., thermostat + wine cooler) is a should-keep edge case — include
it if entity budget allows, but don’t sacrifice area coverage for it.

**RGB at Small:** At least one light with RGB/RGBW capability must survive
to Small. “Turn the light to red” or “set the bedroom light to warm white”
are realistic user commands that test color mode handling. This can be
placed in any area, including a “clean” area — combining unambiguous area
targeting with a tricky command type is itself a useful test.

**Edge case placement:** The derivation implementer chooses where edge
cases land, but they naturally cluster around their source devices —
climate scenarios in kitchen, tech-device groups in office, media
cross-domain in living room. Deviating from these natural placements
should be deliberate (e.g., re-area forces it) rather than accidental.

---

## 3. Selection Principles

When deciding which entities to keep at each derivation step:

**Area elimination drives most decisions.** Dropping an area automatically
eliminates all entities assigned to it (except `area: null` entities, which
survive all tiers). This is the primary lever — most entity-level decisions
follow naturally from which areas are retained.

**High-value areas retain more density.** Kitchen, Living Room, and Office
(the designated tech hub) are the most interesting areas for disambiguation
testing. They should retain 60-70% of their Enormous density even in smaller
tiers. Bedrooms, bathrooms, and utility spaces can drop to 40-50%.

**Density follows complexity.** When cutting entities for a smaller tier,
areas with more edge cases and disambiguation scenarios should retain
proportionally more entities than simpler areas. When cutting within a
high-complexity area, prefer removing generic entities (a third motion sensor,
a redundant light) before removing edge case participants (the aquarium light
that completes a companion group, the brand-name device). This means per-area
entity counts will be uneven — kitchen or office might have 2-3x the entities
of bathroom. That’s acceptable and expected. The goal is test quality per area,
not uniform entity distribution.

**Prioritize edge cases over volume.** When reducing within an area, keep the
entities that serve specific testing purposes (disambiguation, naming quirks,
cross-domain collisions) and cut the "more of the same" entities first. Five
motion sensors across five rooms test the same thing; the kitchen_patio_door
cross-area name tests something unique. See `generation-principles.md` §5 for
the full edge case catalog and §7 for naming diversity principles.

**Companion entity groups degrade gracefully.** A 3-entity companion group
(e.g., aquarium: light + sensor + switch) can lose one member and still test
cross-domain reasoning with the remaining two. At even smaller scale, a single
entity from the group still provides domain coverage, just without the
disambiguation challenge. Track this degradation explicitly.

**Domain elimination follows from area elimination.** If all entities of a
domain lived in dropped areas, the domain disappears from that tier. This is
acceptable and expected — document which domains are absent from which tiers.
For example, dropping all outdoor areas eliminates lawn_mower.

**State coverage is an Enormous-tier goal, not a universal one.** Smaller tiers
accept state coverage gaps rather than artificially inflating entity counts.
A single vacuum in `docked` state is realistic; three vacuums to cover
`docked`/`cleaning`/`error` is an Enormous-tier luxury.

**Unavailable actionable entity must survive every tier.** At least one entity
that is both *actionable* (light, switch, cover, fan, lock, etc.) and in state
`unavailable` must exist at every tier. This is a hard constraint, not a
best-effort goal — it enables Step 8d test cases (testing whether the LLM
correctly avoids issuing tool calls on offline entities). If the unavailable
actionable entity lives in an area being dropped, re-area it to a surviving
area or substitute another actionable entity in a surviving area by changing
its state to `unavailable`. Note: the existing `sensor.garage_temperature`
(unavailable) only tests query behavior, not action refusal, so it alone does
not satisfy this constraint.

### Edge Case Priority Tiers

When entity slots are limited (especially at Medium and Small), edge cases
compete for space. Prioritize in this order:

**Must-keep** (hard constraints — survive every tier including Small):
- Unavailable actionable entity (switch.smart_plug_3 or equivalent)
- At least one cross-domain collision (TV plug + media_player is the
  canonical example)
- At least one RGB/RGBW light (tests color-setting commands like
  “turn the light to red”)

**Should-keep** (keep through Medium; best-effort at Small, sacrifice
only if needed for area coverage):
- Dual climate in same area (kitchen thermostat + wine cooler)
- Companion groups (3D printer, aquarium) — degrade gracefully,
  keeping at least 2 members before dropping entirely
- Brand names in entity IDs (Hue, Sonos)
- Cross-area naming (kitchen_patio_door)
- °C/°F mixing within same domain

**Nice-to-have** (keep at Large; acceptable to lose at Medium/Small):
- Multiple locks on same door (deadbolt scenario)
- Unusual media_player types (projector, speaker group)
- Null-area entities beyond hard constraints
- Seasonal naming (christmas_lights)

---

## 4. Re-area Rules

Occasionally, dropping an area would eliminate an entity that serves a critical
coverage purpose (e.g., the only entity with `state: unknown`). In that case,
the entity can be reassigned to a surviving area.

Rules for re-area:
- **Rare by design.** Expect 0-2 re-area'd entities per tier transition, not
  dozens. If many entities need re-area, the area selection is wrong.
- **Physical plausibility required.** A back door contact sensor can move from
  mudroom to entry (both are entrances). A pool pump cannot move to a bedroom.
- **Document every instance.** Re-area'd entities must be called out in the
  tier's design record and in the areas.yaml header comments.
- **Apply after filtering.** The filter script preserves original areas. Fix
  re-area'd entities manually after running the script.

### Expected Re-Area Counts

As tiers get smaller, re-areas shift from “expected consequence of aggressive
area culling” to “possible signal of upstream distribution problems in the
parent tier.”

- **Enormous → Large** (dropping ~6 areas from ~20): 0-3 re-areas normal.
  The Enormous tier is uncurated — some domains may be concentrated in
  areas that don’t survive. 4+ re-areas warrants a check but isn’t
  alarming given the scale of the cut.

- **Large → Medium** (dropping ~6 areas from ~14): 0-1 re-areas normal.
  Large is already curated, so most domains should have representation
  in surviving areas. 2+ re-areas suggests entities in the parent Large
  tier could have been better distributed across areas.

- **Medium → Small** (dropping ~3 areas from ~8): 0-1 re-areas normal.
  Only 3 areas are being dropped from an already curated tier. 2+
  re-areas means take another look — either the area selection for
  Small should be reconsidered, or the Medium tier’s entity placement
  concentrated too many domain-critical entities in non-surviving areas.

---

## 5. Tooling

**`filter_inventory.py`** (adjacent to this guide) handles the mechanical
extraction. It takes a keep-list (text file of entity_ids) and a source tier
directory, and writes filtered YAML files to a target directory. It preserves
exact formatting, comments, and whitespace from the source.

The separation of concerns is deliberate: **LLM judgment builds the keep-list,
the script handles extraction.** The keep-list is where the design decisions
live — which entities to keep and why. The script just does the filtering so
there's no risk of transcription errors.

### Step 0: Hard Constraint Pre-Check

Before building the keep-list, ensure these entities will be included
regardless of area selection:

- [ ] Unavailable actionable entity (e.g., switch.smart_plug_3)
- [ ] At least one cross-domain collision pair
- [ ] At least one RGB/RGBW light

These entities MUST appear in the keep-list. If they’re in a dropped area,
they survive with area: null (they should already be null) or are re-area’d
per §4.

**Null-area entity guidance:** At Enormous and Large, maintain null-area
representation across domains where it exists in the source tier. At Medium
and Small, null-area entities survive only if they are (a) hard constraints
(e.g., the unavailable actionable entity) or (b) the sole representative
of their domain (e.g., weather.home, todo.shopping_list — these are
null-area by nature). Do not force null-area entities into Medium/Small
solely for null-area coverage.

### Running the filter

Usage:
```
python3 filter_inventory.py <tier_name> <keep_list> <source_dir> <target_dir>
```

**Execution environment:** The script lives adjacent to this guide on the project
filesystem. If your tool environment can execute scripts directly on the local
filesystem (e.g., Claude Code, terminal), run it in place. If your environment
has a separate working filesystem (e.g., Claude Desktop's conversation-local
container), copy the script and the relevant YAML files to that working
filesystem and run it there. The script has no external dependencies beyond
Python 3 stdlib — it's portable.

The keep-list format is one entity_id per line, with `#` comments and blank
lines ignored. Comments in the keep-list are a good place to annotate *why*
each entity was selected (edge case it serves, coverage it provides).

After running the filter:
1. Fix the `derived from` reference in file headers (the script writes
   "derived from Enormous" — change to the actual parent tier name)
2. Apply any re-area fixes via targeted sed or manual edit
3. Verify no dropped-area references remain: `grep -r "area: <dropped>" *.yaml`
4. Write the tier's `areas.yaml` manually (it's small and tier-specific)
5. Spot-check a few entities across tiers for attribute identity

---

## 6. Edge Case Degradation Tracking

As tiers shrink, edge cases are deliberately sacrificed. Track which edge cases
survive at each tier so test case generation (Step 12) knows what's testable.
See `generation-principles.md` §5 and §10 for full definitions of each edge case.

| Edge case | Enormous | Large | Medium | Small |
|-----------|----------|-------|--------|-------|
| Kitchen dual climate (thermostat + wine cooler) | ✓ | ✓ | ✓ | ✗ |
| TV plug cross-domain (media_player + switch) | ✓ | ✓ | ✓ | ✓ |
| Office heater cross-domain (climate + switch) | ✓ | ✓ | ✓ | ✗ |
| Standing desk as cover domain | ✓ | ✓ | ✓ | ✓ |
| Moved-but-never-renamed lamp | ✓ | ✓ | ✗ | ✗ |
| Generic auto-generated bulb (smart_bulb_e7a2) | ✓ | ✓ | ✗ | ✗ |
| Brand name: Hue | ✓ | ✓ | ✓ | ✓ |
| Brand name: Sonos | ✓ | ✓ | ✗ | ✗ |
| TV vs Television abbreviation | ✓ | ✓ | ✗ | ✗ |
| Cross-area name (kitchen_patio_door) | ✓ | ✓ | ✓ | ✗ |
| 3D printer °C in °F home | ✓ | ✓ | ✓ | ✓ |
| 3D printer companion group (switch + sensors) | ✓ (1+3) | ✓ (1+3) | ✓ (1+3) | partial (1+1) |
| Aquarium companion group (light + sensor + switch) | ✓ (3) | ✓ (3) | ✓ (2) | ✗ |
| Water disambiguation cluster | ✓ (8+) | ✓ (3) | ✗ | ✗ |
| Substring bedroom competition | ✓ (3) | ✓ (3) | ✗ (1) | ✗ (1) |
| Seasonal naming (christmas_lights) | ✓ | ✓ | ✗ | ✗ |
| Unknown meta-state entity | ✓ | ✓ | ✗ | ✗ |
| Unavailable meta-state entity (sensor) | ✓ | ✓ | ✗ | ✗ |
| **Unavailable actionable entity (light/switch/etc.)** | **✓** | **✓** | **✓** | **✓** |
| Portable heater (null area climate) | ✓ | ✓ | ✗ | ✗ |
| Generic smart plugs (unhelpful names) | ✓ | ✓ | ✗ | ✗ |

This table is descriptive, not prescriptive — a regeneration may arrive at
different specific trade-offs. The principle is: **track what you're losing
so test generation knows what's available at each tier.**

---

## 7. Large Tier — Design Record

**14 areas, 185 entities, 14 domains.**

Areas dropped from Enormous (6): mudroom, laundry_room, nursery, patio,
upstairs_hallway, upstairs_bathroom. These are the least essential for device
diversity — mudroom overlaps entry, patio overlaps back_yard, upstairs
hallway/bathroom are low-density duplicates of first-floor equivalents.

Re-area'd entities (1): `binary_sensor.back_door_contact` (mudroom → entry).
Preserves the `unknown` meta-state coverage. Entry is the natural fallback
for a door contact sensor.

Entity distribution:
- light: 47, sensor: 33, binary_sensor: 31, switch: 26
- cover: 11, media_player: 9, fan: 7, climate: 7, lock: 6
- weather: 2, valve: 2, todo: 2, vacuum: 1, lawn_mower: 1

Key preservation decisions:
- Tech hub (office) kept at high density — 3D printer sensors, aquarium,
  server rack temp all present
- All cross-domain collisions preserved (TV plug, office heater, dual climate)
- All naming edge cases preserved (brand names, generic bulb, moved lamp,
  TV/Television abbreviation)
- Irrigation reduced from 6 zones to 1 zone (zone_4 kept with its companion
  soil moisture sensor), plus fountain and water main valve — reduced but
  still tests the "turn off the water" disambiguation
- Light capability distribution maintained approximately across profiles

State coverage accepted gaps:
- Vacuum/lawn_mower: 1 entity each, docked state only
- Weather: 2 entities, lost cloudy state (vacation_cabin dropped)
- Media player: reduced but most states still covered

---

## 8. Medium Tier — Design Record

**8 areas, 88 entities, 13 domains (no lawn_mower).**

Areas dropped from Large (6): dining_room, master_bedroom, master_bathroom,
guest_bedroom, front_yard, back_yard. Consolidates to a single floor with
garage. Outdoor areas eliminated entirely, removing irrigation, lawn mower,
and outdoor lighting.

Re-area'd entities: none. All kept entities naturally belong in surviving
areas or null.

Entity distribution:
- light: 22, sensor: 16, binary_sensor: 15, switch: 12
- cover: 5, media_player: 4, climate: 4, fan: 3, lock: 3
- weather: 1, valve: 1, vacuum: 1, todo: 1

Key losses accepted:
- Guest_bedroom edge cases (old_living_room_lamp, smart_bulb_e7a2) — these
  naming quirks are only valuable at larger scale
- Substring bedroom competition (only one "Bedroom" now)
- All outdoor edge cases (irrigation, fountain, holiday lights, lawn mower)
- Sonos brand name, TV/Television abbreviation inconsistency
- Portable heater null-area climate scenario
- Jammed lock state (only 3 locks: 2 locked, 1 unlocked)

Key preservations:
- Kitchen dual climate, TV plug cross-domain, office heater cross-domain
- Standing desk unusual domain mapping
- 3D printer companion group (switch + 3 sensors) still complete
- Aquarium reduced to light + filter switch (2 of 3 companions)
- Cross-area name: binary_sensor.kitchen_patio_door

---

## 9. Small Tier — Design Record

**5 areas, 34 entities, 11 domains (no lawn_mower, vacuum, valve).**

Areas dropped from Medium (3): garage, entry, hallway. Absolute minimum:
the five rooms every home has.

Re-area'd entities: none.

Entity distribution:
- light: 10, sensor: 5, binary_sensor: 5, switch: 4
- cover: 2, climate: 2, media_player: 2
- fan: 1, lock: 1, weather: 1, todo: 1

Design philosophy: **Small is a smoke test, not a comprehensive benchmark.**
It answers: "can the LLM handle basic operations across core domains with
minimal ambiguity?" The interesting edge cases live in Medium and above.
Small exists for fast iteration and basic sanity checking.

State coverage is mostly default states (off/closed/locked). No exotic
states tested — acceptable because state coverage is a Medium+ concern.

Key preservations (the minimum interesting set):
- TV plug cross-domain (the most common real-world cross-domain scenario)
- Standing desk as cover (unusual domain mapping)
- Brand name: light.hue_kitchen_strip
- 3D printer nozzle temp °C alongside °F room temp (unit mixing)
- 3D printer power switch (single switch, no companion sensors at this scale)

---

## 10. Post-Generation Verification

After generating or modifying seed test cases (NDJSON), **always run a
verification pass before considering the data ready.** This applies to initial
seed generation (Step 12), seed expansion via mutation (Step 12.3), and any
manual edits to test case files.

### Why this matters

Test case metadata — particularly `target_entities` — serves as the ground
truth for cross-tier push-down and cohort analysis. If a `target_entities`
value doesn't match any entity_id in the YAML inventory, the `case_key` join
fails silently: the entity won't be found in lower tiers, the case won't be
pushed down, and cross-tier comparisons will have phantom gaps.

This class of error is easy to introduce and hard to spot manually. The
entity_id `lock.front_door` and the erroneous `lock.front_door_lock` both
look plausible — especially for domains where the entity type name echoes the
domain name (locks, lights, switches). An LLM generating test cases may
confabulate the entity_id from the entity's friendly name rather than copying
it exactly from the YAML.

### Verification checklist

Run `verify_entity_consistency.py` (adjacent to this file) after any data
generation or modification:

```
python3 verify_entity_consistency.py <data_dir> --output <report_dir>
```

**Execution environment:** Same portability note as `filter_inventory.py` (§5)
— copy the script and data to your working filesystem if you can't run it
directly on the project filesystem. No external dependencies beyond Python 3
stdlib.

This performs two passes:

1. **YAML cross-tier subset verification.** Confirms Small ⊂ Medium ⊂ Large
   ⊂ Enormous with byte-identical entity data (except documented re-areas).
   Catches drift from manual edits to derived tier YAMLs.

2. **NDJSON `target_entities` vs YAML verification.** For every test case in
   Enormous, confirms each `target_entities` value exists as an `entity_id`
   in the YAML inventory. Also checks whether erroneous forms leaked into
   `id` or `case_key` fields.

The script exits 0 if clean, 1 if mismatches found. Audit reports are written
to the output directory as markdown for review.

### Root cause: the lock `_lock` suffix bug

During initial seed case generation (Step 12.1), the lock domain test cases
were generated with `target_entities` values like `lock.front_door_lock`
instead of the correct `lock.front_door`. The YAML inventory had always been
correct — the error was exclusively in the NDJSON metadata.

The root cause was confabulation from the entity's friendly name: the entity
named "Front Door Lock" has entity_id `lock.front_door`, but it's natural to
assume the entity_id would be `lock.front_door_lock`. This pattern is
specifically dangerous for domains where the domain name is also a common
noun that might appear in the entity name (lock, light, switch, fan, cover,
valve).

**Mitigation for LLM-assisted generation:** When generating seed cases, the
YAML inventory file for the target domain should be included in the prompt
context, and the LLM should be instructed to copy entity_ids verbatim from
the YAML rather than constructing them from the friendly name. The
verification script is a safety net, not the primary defense.

### When to run

- After initial seed generation for any domain
- After seed expansion via mutation (Step 12.3)
- After manual edits to any NDJSON test case file
- After push-down to lower tiers (verify the generated lower-tier NDJSON)
- Before committing test data changes to the git repo
