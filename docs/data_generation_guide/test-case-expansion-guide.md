# Home Assistant Voice LLM Benchmark — Test Case Expansion Guide

**Purpose:** How to expand a structurally complete test suite with additional cases
that add variety, depth, and coverage of interaction patterns that structural cases
don't exercise. This guide assumes the structural generation pass
(`test-case-generation-principles.md`) is already complete.

**Status:** Draft / Untested. Written from analysis of blind generation experiments
and comparison against hand-crafted test cases. Subject to change after validation.

**Created:** 2026-03-02

---

## 1. When to Expand

Run the structural test suite through at least one benchmark evaluation first. Expansion
should be targeted at areas where the model struggles, not applied uniformly.

Expand when:
- Benchmark results show weak performance in a specific domain or tool
- A specific interaction pattern (indirect queries, colloquial commands) seems
  under-tested based on real usage patterns
- The structural cases all use similar phrasing and you want to test language robustness

Do not expand just to increase case count. Every expansion case must name the specific
dimension it adds beyond the structural case it builds on.

---

## 2. Expansion Dimensions

Each dimension below is a category of test value that structural cases don't cover.
When expanding, pick the dimensions most relevant to your evaluation goals.

### 2.1 Utterance Variety

**What it adds:** Different phrasings for the same structural test point. Tests that
the model's language understanding generalizes beyond the specific wording in the
structural case.

**Examples:**
- Structural: "turn off the living room fan" → Expansion: "shut off the ceiling fan",
  "kill the fan in the living room"
- Structural: "lock the front door" → Expansion: "make sure the front door is locked",
  "engage the deadbolt"
- Structural: "what's the temperature" → Expansion: "how warm is it", "how cold is it
  in here"

**Categories of variety:**
- Synonyms: "turn off" / "shut off" / "switch off" / "kill"
- Indirect commands: "make sure X is locked" instead of "lock X"
- Abbreviated references: "the garage" instead of "the garage door"
- Colloquial: "fire up the patio heater", "light the fireplace"
- Polite forms: "can you turn on the light", "please lock the door"

**Stopping rule:** 1-2 phrasing variants per structural case, maximum. Prioritize
cases where the variant tests a genuinely different language understanding challenge
(e.g., "make sure it's locked" requires different intent parsing than "lock the door"),
not trivial synonym substitution.

### 2.2 Idempotent / Already-in-State Commands

**What it adds:** Tests how the model handles commands on devices already in the
requested state. Users frequently issue commands without checking current state.

**Examples:**
- Turn on a light that's already on
- Dock a vacuum that's already docked
- Lock a door that's already locked
- Start mowing when the mower is already mowing

**Stopping rule:** 2-3 cases across different domains. The pattern is the same
regardless of domain — you're testing whether the model issues the tool call anyway
(correct) or refuses (wrong).

### 2.3 Indirect / Inferential Queries

**What it adds:** Utterances where the user's intent doesn't directly name the sensor
type or entity, requiring the model to reason about which entity answers the underlying
human question.

**Examples:**
- "is the dishwasher running" → check power sensor (low wattage = idle)
- "is the baby crying" → nursery sound detection sensor
- "has the mail been delivered" → mailbox contact sensor
- "is the car plugged in" → EV charger connected binary sensor
- "do I need an umbrella" → weather query

**Why this matters:** These are among the most realistic voice-assistant queries and the
hardest for a model to get right. They test intent-to-sensor reasoning, not just
keyword matching.

**Stopping rule:** One case per distinct inferential pattern in the inventory. If the
YAML doesn't have a sensor that supports the inference, don't force it.

### 2.4 Tool-Pair Phrasing Divergence

**What it adds:** Tests whether the on/off (or open/close, lock/unlock, start/dock)
directions of a tool pair resolve differently when disambiguation is involved.

**Examples:**
- "turn on the heater" might resolve to climate (natural phrasing for activating heat)
- "turn off the heater" might resolve to switch (natural phrasing for killing power)
- "turn on the TV" → media_player (wake from standby)
- "turn off the TV" → could go either media_player or switch

**Why this matters:** The structural cases test each direction of the pair, but the
*disambiguation profile* can differ between directions. "Turn on" implies activation
(climate domain feels natural), "turn off" implies power-kill (switch domain feels
natural).

**Stopping rule:** Only add these where the disambiguation genuinely differs between
directions. If both directions resolve the same way, one structural case per direction
is sufficient.

### 2.5 Multi-Entity Same-Type Queries

**What it adds:** Utterances that implicitly target multiple entities of the same type,
requiring the model to check more than one entity or use area targeting.

**Examples:**
- "is any window open in the living room" (multiple window contact sensors)
- "are all the doors locked" (multiple lock entities)
- "are any lights on upstairs" (multiple areas, multiple lights)

**Stopping rule:** 1-2 cases. This tests a specific model capability (multi-entity
awareness) that structural cases typically test with single entities.

### 2.6 Natural Language Value Mapping

**What it adds:** Varied ways of expressing numeric values, testing the model's ability
to translate natural language to specific parameters.

**Examples:**
- Brightness: "way down" (~10%), "half brightness" (50%), "a little brighter" (+10-20%)
- Fan speed: "low" (33%), "medium" (50-66%), "high" (100%), "turbo" (100%)
- Volume: "a little quieter" (-10), "much louder" (+20-30)
- Temperature: "make it warmer", "cool it down" (relative, no specific number)
- Cover position: "half open" (50%), "crack it open" (~10-20%)

**Stopping rule:** One case per value-mapping pattern that differs meaningfully from
the structural case. "Set to 50%" (structural) vs "half brightness" (expansion) tests
a different language skill. "Set to 40%" vs "set to 60%" does not.

---

## 3. Expansion Process

### Per case:

1. **Identify the structural case** you're expanding on (by case_key or description).
2. **Name the expansion dimension** from §2 that this case adds.
3. **Write the case** following the same NDJSON format as structural cases.
4. **In the notes field**, reference the structural case and state what's new:
   "Expansion of HassTurnOn×lock: indirect phrasing variant ('make sure it's locked')."

### File organization:

Expansion cases go in the same domain files as their structural counterparts. Do not
create separate expansion files — the test suite should be one unified set of NDJSON
files.

### ID convention:

Use sequence numbers that don't collide with structural cases. If the structural case
is `-001`, expansion cases are `-002`, `-003`, etc.

### Budget:

Target approximately 1.5-2x the structural case count after expansion. For a ~120-case
structural set, the expanded set should be ~180-240 total. If you're significantly
above 250, you're likely adding cases without clear structural or expansion rationale.

---

## 4. What NOT to Expand

- **Same HassGetState on a different entity of the same type.** If you have a
  temperature sensor query, adding another temperature sensor query on a different
  entity doesn't test anything new.
- **Trivial synonym substitution.** "Turn on" → "switch on" tests almost nothing
  different. Expand only when the phrasing requires different intent parsing.
- **Cases where the structural case already uses an interesting utterance.** If the
  structural case for HassMediaNext is "skip this song" (informal phrasing), don't
  add "next track" — the structural case already demonstrates language understanding.
- **Domain files that already have 8+ cases.** Check whether the additions genuinely
  test new dimensions or are padding.

---

## 5. Expansion Priorities (Recommended Order)

When expanding, work through these priorities in order:

1. **Indirect/inferential queries (§2.3)** — highest test value, most different from
   structural cases, most likely to reveal model weaknesses.
2. **Tool-pair phrasing divergence (§2.4)** — tests a subtle disambiguation pattern
   that structural cases miss by design.
3. **Natural language value mapping (§2.6)** — common in real voice usage, tests a
   different skill than explicit numeric commands.
4. **Utterance variety (§2.1)** — broad value but diminishing returns. Be selective.
5. **Idempotent commands (§2.2)** — quick to add, tests a specific edge.
6. **Multi-entity queries (§2.5)** — niche but valuable for completeness.

---

## 6. Validation

After expansion, run the same verification as structural generation:

```
python3 verify_entity_consistency.py <data_dir> --output <report_dir>
```

Additionally, review the expanded set for:
- [ ] Every expansion case names its dimension in the notes field
- [ ] No expansion case duplicates a structural dimension
- [ ] Total case count is within the ~1.5-2x budget
- [ ] Domain files haven't ballooned disproportionately (sensor and binary_sensor are
      the most likely to over-expand due to many device_classes)
