# Home Assistant Voice LLM Benchmark — Test Case Generation Principles

**Purpose:** Everything needed to generate structurally complete NDJSON test cases for
the HA voice LLM benchmark. Format specification, structural coverage derivation,
reasoning methodology, utterance design, tool call construction, entity_id safety
rules, and worked examples.

**Audience:** An LLM agent or human creating test cases against a synthetic HA inventory,
without access to the original discussion history.

**Created:** 2026-03-02 (M2 Step 12)
**Revised:** 2026-03-02 — rewritten around structural coverage derivation model.
**Revised:** 2026-03-02 — Steps 3, 8 strengthened; Steps 9 (implicit intent), 10
(tool limitation probes) added. Budget updated to ~110-150.

**See also:**
- `generation-principles.md` — how the YAML entity inventories were generated
- `derivation-guide.md` — how YAML tiers were derived (Large/Medium/Small from Enormous)
- `test-case-derivation-guide.md` — how to derive test cases downward to smaller tiers
- `test-case-expansion-guide.md` — how to expand structural test cases with variety
- `verify_entity_consistency.py` — post-generation verification tool

---

## 1. NDJSON Format Specification (v2)

Each test case is a single JSON object on one line (newline-delimited JSON). All fields
are required unless noted.

### Schema

```json
{
  "id": "string",
  "utterance": "string",
  "expected_tool_calls": [],
  "alternative_expected_tool_calls": [],
  "expected_response_type": "string",
  "inventory_tier": "string",
  "inventory_file": "string or null",
  "metadata": {}
}
```

### Field Definitions

**`id`** — Structured correlation ID.
Format: `{inventory_tier}-{tool_or_category}-{target_type}-{target_id}-{seq}`

Examples:
- `enormous-HassTurnOn-light-kitchen_ceiling-001` — device control
- `enormous-multi-lights_lock-001` — multi-action (category = "multi")
- `all-HassBroadcast-utility-none-001` — inventory-independent utility
- `all-text-conversational-none-001` — no-tool-call conversational
- `all-text-out_of_scope-none-001` — out-of-scope behavioral probe

For cases with empty `expected_tool_calls`, use `text` as the tool component.
Use `none` as the target_id when there's no specific entity target.

**`utterance`** — Natural language voice command as STT would produce it. This becomes
the user message in the LLM prompt. Should be realistic transcription output:
lowercase, minimal punctuation, natural spoken phrasing. See §4 for design principles.

**`expected_tool_calls`** — Array of expected tool call objects. Empty `[]` for cases
where no tool call is appropriate (conversational, out-of-scope, edge cases).

Each entry:
```json
{
  "name": "HassTurnOn",
  "arguments": {
    "name": "Kitchen Ceiling Light",
    "domain": ["light"]
  }
}
```

- `name`: The HA intent tool name (e.g., HassTurnOn, HassGetState).
- `arguments`: Expected parameter key-value pairs. Use `{}` when only the tool name
  matters.

Multi-action ordering is not significant — the scorer compares order-independently.

**`_any_of` convention:** An argument key ending in `_any_of` means the scorer accepts
any listed value. Use when multiple entities are equally valid targets and any one
would be a correct response:
```json
{"name_any_of": ["Kitchen Ceiling Light", "Kitchen Counter Light"], "domain": ["light"]}
```

**`alternative_expected_tool_calls`** (optional) — Alternative tool call sets with
quality ratings. Include only when a reasonable evaluator might consider the alternative
a correct response. If the primary tool call is clearly the best answer and
alternatives are strictly inferior, omit the field or use an empty array `[]`. Reserve
alternatives for genuine disambiguation (multiple valid entities) or equivalent tool
paths (e.g., HassTurnOff vs HassSetPosition(0) for covers).

Each entry:
```json
{
  "tool_calls": [{"name": "HassGetState", "arguments": {"name": "...", "domain": ["sensor"]}}],
  "quality": "acceptable",
  "reason": "Dedicated sensor returns accurate reading"
}
```

Quality tiers:
- `equivalent` — equally good as primary; different path, same quality answer.
- `acceptable` — works well enough; user gets reasonable answer, some richness missing.
- `degraded` — technically executes; wrong data type or significantly incomplete.

Primary `expected_tool_calls` is implicitly `optimal` (no label needed). Failures
(wrong answer, user confused) are NOT listed as alternatives — they score as Incorrect.

Do not string together multiple small quotes from a single source or include multiple
alternatives that differ only trivially.

**`expected_response_type`** — What kind of response is acceptable:

| Value | Meaning | Tool calls expected? | When to use |
|-------|---------|---------------------|-------------|
| `action_done` | Execute a device action | Yes (1+) | Device control commands |
| `query_response` | Query state/data via tool | Yes (1+) | State/value questions |
| `text_response` | Respond in NL only | No | Out-of-scope (explain what can't be done), general knowledge, greetings, conversational |
| `clarification` | Ask user for more info | No | Incomplete commands, ambiguous non-actionable input |
| `error` | Refuse or explain inability | No | Malformed or contradictory requests (dim a lock, set position on binary sensor) |

Key boundary: `text_response` for requests outside HA scope where the model should
respond conversationally. `error` for requests that are technically malformed or apply
an action to an incompatible entity type. `clarification` for requests that could
become valid with more information.

**`inventory_tier`** — One of: `enormous`, `large`, `medium`, `small`, `all`.
`all` means inventory-independent (utility, conversational) — included in every tier.

**`inventory_file`** — Always `test_data/inventories/{tier}/combined.yaml` for tier-specific cases.
`null` for `all`-tier cases. Do not use per-domain YAML paths — always reference the
combined inventory file to ensure each test case points to the full entity context
needed for disambiguation evaluation.

**`metadata`** — Required object with these fields (all required):

- `intent_type` (string): Categorization. Values include: `light_control`,
  `climate_control`, `climate_query`, `cover_control`, `lock_control`,
  `media_control`, `fan_control`, `vacuum_control`, `lawn_mower_control`,
  `valve_control`, `todo`, `weather`, `switch_control`, `state_query`,
  `area_command`, `multi_action`, `utility`, `general_knowledge`, `conversational`,
  `out_of_scope`, `incomplete_command`, `gibberish`, `edge_case`, `disambiguation`,
  `implicit_intent`, `tool_limitation`.
- `complexity` (string): One of the following, with concrete definitions:
  - `simple` — One entity, one tool, entity name clearly matches utterance.
    Example: "turn on the kitchen ceiling light" → HassTurnOn on Kitchen Ceiling Light.
  - `moderate` — Requires inference: area → entity mapping, informal name → formal
    name, implied domain, natural language value → numeric conversion.
    Example: "set the bedroom fan to medium" → HassFanSetSpeed with percentage.
  - `complex` — Multiple tools, cross-domain targeting, multi-area commands.
    Example: "lock the door and turn off the kitchen lights" → two tool calls.
  - `ambiguous` — Multiple valid targets where a human might need clarification.
    Example: "turn on the bedroom light" with 2+ lights in bedroom.
  - `edge_case` — Unusual entity states (jammed, unavailable, error, unknown),
    unsupported actions on valid entities, nonexistent entities.
    Example: "dim the front door lock" → unsupported action.
- `target_entities` (array of strings): Entity IDs this case targets. Empty for area
  commands, conversational, and no-entity cases. **Must be copied verbatim from YAML
  inventory** — see §7 for entity_id safety rules.
- `target_areas` (array of strings): Area names relevant to this case. Empty when no
  area is relevant.
- `case_key` (string): Tier-independent case identity. Derived from `id` by stripping
  the tier prefix. Format: `{tool_or_category}-{target_type}-{target_id}-{seq}`.
  Used for cross-tier and cross-run comparison.
- `notes` (string): What this test case exercises and why it matters. Include
  evaluation hooks where relevant: "T3 analysis: does model communicate the abnormal
  state appropriately?" for edge cases involving unusual states.

---

## 2. Structural Coverage — Deriving Test Cases from YAML Inventories

A structurally complete test suite has **one case per structural dimension**. This
section defines how to derive the complete list of structural dimensions from the YAML
inventory files and tool mapping tables. The result is a finite, enumerable coverage
target — not a vague "generate cases" instruction.

### Inputs required

1. All domain YAML files for the target tier (light.yaml, climate.yaml, etc.)
2. `areas.yaml` for the target tier
3. The tool mapping table (§2.1 below)

### 2.1 Tool × Domain Mapping Table

This table defines which tools apply to which domains. Each cell where a tool applies
to a domain is one structural dimension requiring one test case.

| Tool | Domains |
|------|---------|
| HassTurnOn | light, switch, fan, cover (=open), lock (=lock), climate, media_player, valve (=open) |
| HassTurnOff | light, switch, fan, cover (=close), lock (=unlock), climate, media_player, valve (=close) |
| HassToggle | light, switch, fan, cover |
| HassGetState | light, switch, fan, cover, lock, climate, media_player, sensor, binary_sensor, vacuum, lawn_mower, valve |
| HassSetPosition | cover |
| HassLightSet | light (brightness), light (color), light (color_temp) |
| HassClimateSetTemperature | climate |
| HassClimateGetTemperature | climate |
| HassFanSetSpeed | fan |
| HassSetVolume | media_player |
| HassSetVolumeRelative | media_player |
| HassMediaPause | media_player |
| HassMediaUnpause | media_player |
| HassMediaNext | media_player |
| HassMediaPrevious | media_player |
| HassMediaPlayerMute | media_player |
| HassMediaPlayerUnmute | media_player |
| HassMediaSearchAndPlay | media_player |
| HassVacuumStart | vacuum |
| HassVacuumReturnToBase | vacuum |
| HassLawnMowerStartMowing | lawn_mower |
| HassLawnMowerDock | lawn_mower |
| HassListAddItem | todo |
| HassListCompleteItem | todo |
| HassGetWeather | weather |
| HassBroadcast | (inventory-independent) |
| HassGetCurrentTime | (inventory-independent) |
| HassGetCurrentDate | (inventory-independent) |
| HassNevermind | (inventory-independent) |

**Updating this table:** When Home Assistant adds new intents or domains, add rows/columns.
The structural derivation algorithm (§2.2) will automatically require cases for the
new cells.

### 2.2 Structural Derivation Algorithm

For a given inventory tier, walk through these steps. Each step produces structural
dimensions; each dimension gets exactly one test case.

**Step 1: Tool × domain cells.** For each cell in the tool mapping table (§2.1) where
the domain has entities in this tier's YAML, generate one case. This is the foundation.

Example: Lock YAML has entities → generate one case each for HassTurnOn×lock,
HassTurnOff×lock, HassGetState×lock. HassLightSet doesn't apply to lock → skip.

Count estimate: ~45-55 cells for a full-domain inventory.

**Step 2: Device subtypes.** Within each domain, scan the YAML for distinct device
subtypes (indicated by `device_class`, `supported_features`, or qualitative
differences in how the device works). If a subtype behaves differently enough that
the tool call or utterance design would meaningfully change, add one case.

Examples of distinct subtypes:
- Cover: blinds (position-capable) vs garage door (binary open/close) vs awning vs standing desk
- Fan: ceiling fan (multi-speed) vs exhaust fan (binary on/off)
- Binary sensor: motion vs door vs moisture vs smoke vs presence vs sound vs connectivity
- Sensor: temperature vs humidity vs power vs battery vs CO2 vs duration vs data_rate vs progress
- Climate: thermostat vs wine cooler vs space heater vs mini-split
- Switch: appliance vs smart plug vs virtual/automation switch vs irrigation zone
- Media player: TV vs speaker vs soundbar vs projector vs speaker group

Rule: if the subtype is already covered by a Step 1 case (i.e., the Step 1 entity
happened to be that subtype), don't duplicate. Only add when a *different* subtype
needs its own case.

Count estimate: ~15-25 additional cases depending on inventory diversity.

**Step 3: Disambiguation scenarios.** Scan the YAML for situations where an ambiguous
utterance could resolve to multiple entities. For each scenario found, **don't stop at
the first conflict pair** — continue scanning to find ALL entities that could match the
same natural query. The goal is to document the full conflict set, even if the test case
only picks one primary tool call.

Sources of disambiguation (scan in all three directions):

a) **Within-area conflicts.** Multiple entities of the same measurement type, keyword,
   or device function in one area.
   - Example: "what's the temperature in the office" — an office might contain: room
     temperature sensor, server rack temperature sensor, aquarium temperature sensor,
     3D printer nozzle temp, 3D printer bed temp, AND a climate entity. That's a 6-way
     conflict. All six belong in `target_entities` and notes, even though the primary
     tool call targets one.
   - Example: Kitchen has 12 lights — "turn on the kitchen light" is ambiguous.
   - Generate one case per distinct conflict cluster.

b) **Cross-area conflicts.** Same name or keyword matches entities in different areas.
   - Example: "turn on the hallway light" — Hallway and Upstairs Hallway both have
     ceiling lights whose names contain "hallway".
   - Generate one case per name collision.

c) **Arealess-to-area conflicts.** Entity with `area: null` semantically matches a
   query about a specific area.
   - Example: `climate.portable_heater` has no area. "Turn on the heater" while in
     the bedroom creates ambiguity between the portable heater (arealess) and
     `climate.bedroom_thermostat` (area: bedroom). The arealess entity is invisible
     to area-based targeting but a valid name match.
   - Generate one case per arealess entity that a user might naturally reference.

d) **Cross-domain device overlap.** Same physical device or function exposed in
   multiple domains.
   - Example: "turn off the TV" — media_player (graceful standby) vs switch (hard
     power kill). "Turn off the heater" — climate vs switch.
   - Generate one case per overlap.

**Stopping heuristic:** For each disambiguation scenario, enumerate all entities
sharing a measurement type, keyword, or device function within the relevant scope.
The office temperature example illustrates the boundary: all temperature-related
entities in the office belong in the conflict set, but motion sensors in the same
office do not — they wouldn't match a "temperature" query. Use judgment guided by
"would a natural utterance plausibly match this entity?" Stop when the answer is no.

YAML comments often flag disambiguation scenarios explicitly — scan for them.

Count estimate: ~10-15 cases depending on inventory complexity. The deeper search
mostly enriches existing cases (fuller `alternative_expected_tool_calls` and metadata)
rather than adding new ones.

**Step 4: Unusual entity states.** Scan the YAML for entities in non-standard states:
`unavailable`, `unknown`, `jammed`, `error`, or other abnormal values. Generate one
case per distinct state type (not per entity — one "unavailable" test is sufficient).

Count estimate: ~3-5 cases.

**Step 5: Area-scoped commands.** For each domain that has multiple entities in at
least one area, generate one area+domain command. This tests that the model can use
`area` + `domain` targeting instead of naming specific entities.

Applicable domains: light, switch, fan, cover, lock (where multiple exist in an area).
Not all domains will qualify in every tier.

Count estimate: ~4-6 cases.

**Step 6: No-tool-call categories.** These are inventory-independent and use
`inventory_tier: "all"`. Generate one case per category:

a) **Out-of-scope requests** — things HA can't do (web search, SMS, reminders, alarms,
   shopping). Target: 3-4 cases covering distinct out-of-scope types.
b) **Conversational** — greetings, meta questions ("what can you do"), acknowledgments,
   identity questions. Target: 3-4 cases.
c) **General knowledge** — factual questions with no HA relevance. Target: 2-3 cases.
d) **Incomplete commands** — truncated or missing-target utterances. Target: 2-3 cases.
e) **Gibberish** — keyboard mash, STT noise, disfluent mumbling. Target: 1-2 cases.
f) **Ambiguous intent** — utterances that could be conversational or command (e.g.,
   "the kitchen is too hot"). Target: 1-2 cases.

Count estimate: ~15-20 cases (these are fixed, not derived from YAML size).

**Step 7: Multi-action commands.** Generate cases combining tools across domains:

a) Two unrelated actions: "lock the door and turn off the lights"
b) Two actions in same area: "close the blinds and dim the lights in the bedroom"
c) Broad area command: "turn off everything in the office" (no domain filter)

Count estimate: ~3-5 cases.

**Step 8: Edge cases.** Generate one case per distinct failure mode identified. Scan
this checklist — each represents a structurally different error condition:

a) **Nonexistent entity** — utterance references something not in the inventory
   (swimming pool lights, basement light). Expected: no tool call, error response.
b) **Unsupported action on valid entity** — entity exists but action doesn't apply
   to it at all (dim a lock, set position on a binary sensor). Expected: no tool call,
   error response.
c) **Wrong action type for domain** — entity exists, action *type* exists in the system
   for other domains, but doesn't apply to this domain (set lock to 50% —
   position/percentage is a valid concept for covers but not locks). Subtly different
   from (b): the action exists, just not for this entity type. Expected: no tool call,
   error response.
d) **Action on unavailable entity** — entity exists but its state is `unavailable`.
   The model can see this in the inventory context and should recognize it cannot
   act on an offline entity. Expected: **no tool call**. T3 analysis evaluates whether
   the model communicated helpfully (e.g., "the kitchen light appears to be offline"
   vs. silent inaction). **Dependency:** requires at least one unavailable *actionable*
   entity (light, switch, cover, etc.) in the YAML inventory.

Count estimate: one case per failure mode the inventory supports. Typically 3-4 cases.
If the inventory lacks an unavailable actionable entity, (d) cannot be generated —
note the gap.

**Step 9: Implicit intent / scene commands.** Generate cases where the user expresses
a *goal or context* rather than naming specific actions. These are utterances that
imply multiple actions through situational meaning.

Examples:
- "goodnight" → lock doors, turn off common-area lights, maybe lower thermostat
- "I'm leaving" → lock doors, turn off lights, set away mode
- "movie time" → dim living room lights, close blinds, turn on TV/projector

**How to identify scene contexts:** Scan the inventory for clusters of entities that
logically group into a real-world scenario: bedroom devices for sleep, living room
AV equipment for movie night, entry-area devices for leaving/arriving, outdoor
devices for entertaining. Each distinct scene context gets one case.

**Handling ambiguity:** These are inherently ambiguous — there is no single "correct"
action set for "goodnight." The expected_tool_calls captures one reasonable
interpretation. Use alternative_expected_tool_calls liberally with `equivalent` or
`acceptable` ratings for other valid action sets. Both `action_done` and
`clarification` are acceptable response types.

**Scoring scope:** At T1/T2, the expectation is simply "did the model do something
reasonable or ask for clarification?" We are not scoring whether the model chose the
optimal combination of actions. Real evaluation of intent understanding quality is
deferred to T3 analysis.

Count estimate: one case per distinct scene-like context identified in the inventory.
The count is an output of the analysis, not a target. If you're finding more than
~8-10, pause and re-evaluate whether each is a truly distinct scene context or a
variation of one you've already covered.

**Step 10: Tool limitation probes.** Generate cases where the *tool call is correct*
but the *information returned is incomplete or doesn't fully answer the question*.
The tool call itself is the right one to make — the test probes whether the model
communicates the gap in what the tool can provide.

Examples:
- HassGetState on a cover returns "open"/"closed" but NOT position percentage.
  "How open are the kitchen blinds?" → correct tool call, but the model should
  relay that it can only report open/closed, not a precise percentage.
- HassGetWeather returns current conditions only. "What's the forecast for tomorrow?"
  → correct tool call, but can't fully answer the question.
- HassClimateGetTemperature returns the thermostat's reading, which may differ from
  ambient room temperature. "What's the actual room temperature?" when only a
  thermostat exists.

**How to identify limitations:** For each domain-specific query tool (HassGetState,
HassClimateGetTemperature, HassGetWeather, etc.), ask: "what information would a
user commonly *expect* from this query that the tool *doesn't provide*?" Write a case
for each genuine gap you find. Action tools (HassTurnOn, etc.) generally don't have
this issue — focus on query tools.

**Scoring scope:** At T1/T2, the tool call is Correct — the model *should* call the
tool. The limitation is in what comes back and how the model handles it. T3 analysis
evaluates whether the model communicated the gap helpfully.

Count estimate: one case per query tool with a meaningful limitation you identify.
The count is an output of the analysis, not a target. If you're finding more than
~8-10, pause and re-evaluate whether each represents a truly distinct limitation or
variations of the same gap.

### 2.3 Total Budget

Following this algorithm, a structurally complete set for a full-domain inventory
(like Enormous) should produce approximately **110-150 test cases**. The breakdown:

| Step | Description | Estimated count |
|------|-------------|-----------------|
| 1 | Tool × domain cells | 45-55 |
| 2 | Device subtypes | 15-25 |
| 3 | Disambiguation scenarios | 10-15 |
| 4 | Unusual states | 3-5 |
| 5 | Area-scoped commands | 4-6 |
| 6 | No-tool-call categories | 15-20 |
| 7 | Multi-action commands | 3-5 |
| 8 | Edge cases | 3-4 |
| 9 | Implicit intent / scene commands | varies |
| 10 | Tool limitation probes | varies |
| **Total** | | **~110-150** |

Steps 9 and 10 have variable counts because the number of cases is an output of
analysis (how many distinct scene contexts exist? how many query tools have meaningful
limitations?) rather than a fixed target.

If your count falls significantly outside this range, review:
- Below 100: likely missing tool×domain cells, device subtypes, or skipping Steps 9-10
- Above 170: likely duplicating structural dimensions (two cases testing the same cell)

### 2.4 Stopping Rule

A domain file is complete when:
1. Every applicable tool from §2.1 has exactly one case
2. Every distinct device subtype has one case (if not already covered by step 1)
3. Every YAML-documented disambiguation scenario has one case, with the full conflict
   set documented (not just the first pair found)
4. Every unusual state in the YAML has one case (across all domain files, not per domain)

The cross-domain file is complete when:
5. Every edge case failure mode supported by the inventory has one case (Step 8)
6. Every distinct implicit intent / scene context has one case (Step 9)
7. Every query tool with a meaningful information limitation has one case (Step 10)

If you can't articulate which structural dimension a case covers, don't add it.

---

## 3. How to Reason About a Test Case

For each test case, the reasoning process follows three steps.

### Step 1: What tool(s) should be called?

Read the utterance. Identify the intent (action vs. query vs. conversational). Map it
to the HA tool that handles that intent for that domain. Key considerations:

- Which tool handles this action for this domain?
- Does the utterance imply a specific entity (by name) or a group (by area + domain)?
- Are there multiple valid tool paths? If so, which is optimal vs. acceptable?

### Step 2: What arguments should the tool receive?

Determine the correct arguments by examining the YAML inventory. See §5 for argument
patterns and the name-vs-area decision tree.

### Step 3: Are there quality-differentiated alternatives?

Think about what else a model might reasonably do:

- Different tool, same outcome → `equivalent`
- Different tool, acceptable but less precise → `acceptable`
- Different tool, technically works but loses information → `degraded`
- Wrong tool, wrong entity, hallucinated tool → Incorrect (don't list)

Only include alternatives when a reasonable evaluator might consider them correct.

---

## 4. Utterance Design Principles

### Style for structural cases

Structural test cases use **direct voice-assistant style**: clear, minimal commands or
questions as a person would naturally speak to a voice assistant. No filler words
(please, hey, can you), no excessive politeness, no overly verbose constructions.

- Good: "turn on the kitchen light"
- Good: "what's the temperature in the living room"
- Good: "is the front door locked"
- Avoid: "hey can you please turn on the kitchen light for me"
- Avoid: "I would like you to activate the illumination device in the kitchen area"

Save phrasing variety (synonyms, colloquial, indirect, polite forms) for the expansion
pass — see `test-case-expansion-guide.md`.

### Realism

Utterances should sound like realistic STT transcription output:
- Lowercase throughout
- Minimal punctuation (contractions are fine: what's, it's, don't)
- No quotes around spoken values
- Natural spoken word order

### Complexity spectrum

The structural cases will naturally span a range of complexity based on what they test:

- Simple: "turn on the kitchen ceiling light" (Step 1 cell)
- Moderate: "set the bedroom fan to medium" (Step 2 subtype, value mapping)
- Complex: "lock the door and turn off the kitchen lights" (Step 7 multi-action)
- Ambiguous: "turn on the bedroom light" (Step 3 disambiguation)
- Edge case: "dim the front door lock" (Step 8 unsupported action)

This variety emerges naturally from the structural derivation — don't force it.

---

## 5. Tool Call Construction

### Argument patterns by tool type

**HassTurnOn / HassTurnOff / HassToggle (generic tools):**
- By name: `{"name": "Kitchen Ceiling Light", "domain": ["light"]}`
- By area: `{"area": "Kitchen", "domain": ["light"]}`
- By area, all domains: `{"area": "Office"}`

**HassLightSet:**
- Brightness: `{"name": "...", "brightness": 50}`
- Color: `{"name": "...", "color": "red"}`
- Color temp: `{"name": "...", "color_temp": "warm white"}`

**HassClimateSetTemperature:**
- `{"name": "Living Room Thermostat", "temperature": 72}`
- Or by area: `{"area": "Living Room", "temperature": 72}`

**HassClimateGetTemperature:**
- `{"name": "Living Room Thermostat"}`
- Or by area: `{"area": "Living Room"}`

**HassGetState:**
- `{"name": "Front Door", "domain": ["binary_sensor"]}`
- `{"name": "Kitchen Humidity", "domain": ["sensor"]}`

**HassSetPosition:**
- `{"name": "Office Left Blinds", "position": 40}`

**HassSetVolume / HassSetVolumeRelative:**
- `{"name": "Kitchen Speaker", "volume_level": 40}`
- `{"name": "Kitchen Speaker", "volume_level_relative": -10}`

**HassMediaPause / HassMediaUnpause / HassMediaNext / HassMediaPrevious:**
- `{"name": "Living Room TV"}`

**HassMediaPlayerMute / HassMediaPlayerUnmute:**
- `{"name": "Living Room TV"}`

**HassMediaSearchAndPlay:**
- `{"name": "Living Room Smart Speaker", "search_query": "jazz"}`

**HassFanSetSpeed:**
- `{"name": "Living Room Ceiling Fan", "percentage": 50}`

**HassVacuumStart / HassVacuumReturnToBase:**
- `{"name": "Downstairs Robot Vacuum"}`

**HassLawnMowerStartMowing / HassLawnMowerDock:**
- `{"name": "Back Yard Robot Mower"}`

**HassBroadcast:**
- `{"message": "Dinner is ready"}`

**HassListAddItem / HassListCompleteItem:**
- `{"item": "milk", "name": "Shopping List"}`

**HassGetWeather:**
- `{}` (default weather entity)
- `{"name": "Vacation Cabin Weather"}` (named entity)

### Domain argument heuristic

**Domain-specific tools** (HassClimateSetTemperature, HassClimateGetTemperature,
HassVacuumStart, HassVacuumReturnToBase, HassLawnMowerStartMowing, HassLawnMowerDock,
HassLightSet, HassFanSetSpeed, HassSetPosition, HassSetVolume, HassSetVolumeRelative,
HassMediaPause/Unpause, HassMediaNext/Previous, HassMediaPlayerMute/Unmute,
HassMediaSearchAndPlay, HassListAddItem/CompleteItem, HassGetWeather) do not need a
`domain` argument — the domain is implicit in the tool name.

**Generic tools** (HassTurnOn, HassTurnOff, HassToggle, HassGetState) use `domain` to
constrain entity resolution. Always include `domain` for generic tools unless the
intent is explicitly all-domain (e.g., "turn off everything in the office").

### Name vs. area targeting — decision tree

1. Does the utterance name a specific entity? ("the kitchen ceiling light", "the
   front door lock") → Use `name`. Match the entity's `name` field from the YAML.

2. Does the utterance target all entities of a type in an area? ("the lights in the
   kitchen", "turn off everything in the office") → Use `area` + optional `domain`.

3. Is the utterance generic within an area? ("turn on the bedroom light" where bedroom
   has multiple lights) → Prefer `area` + `domain` as primary. A specific `name`
   targeting one entity is an acceptable alternative.

4. Does the utterance reference an arealess entity? (entity has `area: null`) →
   Must use `name`. Area targeting won't find it.

---

## 6. HA Domain Knowledge — Where to Look

When generating test cases, you need to know what states, features, and behaviors are
valid for each domain. Rather than encoding all domain knowledge here (it changes with
HA releases), here's where to find it:

### Source code (home-assistant/core repo, `dev` branch)

The pattern is consistent across domains:

- **Valid states:** `homeassistant/components/<domain>/const.py` — look for `StrEnum`
  classes like `HVACMode`, `HVACAction`, `LockState`, `CoverState`,
  `MediaPlayerState`, `VacuumActivity`. Simple toggle domains (light, fan, switch)
  use `STATE_ON`/`STATE_OFF` from `homeassistant/const.py`.

- **Supported features:** Same `const.py` files — look for `IntFlag` classes like
  `ClimateEntityFeature`, `CoverEntityFeature`, `FanEntityFeature`,
  `MediaPlayerEntityFeature`, `LockEntityFeature`. These bitmasks control what
  capabilities an entity exposes.

- **Device classes:** `homeassistant/components/<domain>/const.py` or `__init__.py` —
  `SensorDeviceClass`, `BinarySensorDeviceClass`, `CoverDeviceClass`, etc. These
  define what "kind" of entity it is (temperature sensor vs. humidity sensor, garage
  door vs. window blind).

- **Intent handlers:** `homeassistant/components/<domain>/intent.py` — the registered
  intent handler classes with their slot schemas (what arguments each tool accepts).

- **LLM tool bridge:** `homeassistant/helpers/llm.py` — the `AssistAPI` class that
  converts intent handlers into LLM-callable tool definitions.

### Intents repository (home-assistant/intents)

- **Master intent schema:** `intents.yaml` at repo root — canonical definition of every
  intent's slots, types, required/optional flags.
- **Slot value definitions:** `sentences/en/_common.yaml` — lists like `color` values,
  `brightness` ranges, etc.
- **Voice sentence templates:** `sentences/en/<domain>_<IntentName>.yaml` — how natural
  language maps to intents.
- **Test fixtures:** `tests/en/_fixtures.yaml` — fake entities/areas used in HA's own
  testing.

### Developer documentation

- **Built-in intent reference:** `developers.home-assistant.io/docs/intent_builtin/` —
  auto-generated page listing all intent schemas.
- **Entity docs:** `developers.home-assistant.io/docs/core/entity/<domain>/` — per-domain
  entity documentation with state machines and feature descriptions.
- **LLM API docs:** `developers.home-assistant.io/docs/core/llm/` — how intents are
  exposed as tools to LLMs.

### Key domain behaviors to be aware of

Some behaviors are not obvious from the source alone. These are the gotchas that matter
most for test case generation:

- **Lock uses HassTurnOn/HassTurnOff:** "Lock" = HassTurnOn, "unlock" = HassTurnOff.
  This is counter-intuitive but is the standard HA mapping.
- **Cover open/close:** "Open" = HassTurnOn, "close" = HassTurnOff OR
  HassSetPosition(position: 0). Both are valid.
- **Valve open/close:** Same as cover — "Open" = HassTurnOn, "close" = HassTurnOff.
- **Climate tool selection:** HassClimateGetTemperature returns the thermostat's
  current temperature reading. HassGetState on a climate entity returns the HVAC
  mode/action. HassGetState on a sensor returns a sensor value. "What's the
  temperature" could map to any of these.
- **Fan speed:** HassFanSetSpeed takes a percentage (0-100), not named speeds.
  "Set to medium" requires the model to translate natural language to a percentage.
- **Media player state ambiguity:** "Turn off the TV" could target
  media_player (graceful standby) or a switch (hard power kill) if both exist.
- **HassGetState returns limited cover info:** Covers report "open"/"closed" but NOT
  their position percentage via HassGetState. This is a known limitation.
- **Binary sensor state semantics:** on/off mean different things per device_class.
  "on" for a door sensor means "open", for motion means "detected", for moisture
  means "wet". The model should translate these.

---

## 7. Entity ID Safety — The Confabulation Problem

**CRITICAL:** When populating `metadata.target_entities`, always copy entity_ids
character-for-character from the YAML inventory files. NEVER construct entity_ids from
the entity's friendly name.

### Why this matters

LLMs generating test cases will naturally confabulate entity_ids from friendly names.
The entity named "Front Door Lock" has entity_id `lock.front_door`, but it's natural
to assume it would be `lock.front_door_lock`. This error is invisible during generation
(both look plausible) but breaks downstream processing:

- Push-down derivation uses `target_entities` to check tier applicability
- Cohort analysis groups by entity_id
- A wrong entity_id silently excludes the case from cross-tier comparisons

### High-risk domains

Domains where the domain name is also a common noun in device names are most vulnerable:
lock, light, switch, fan, cover, valve. For example:

- "Front Door Lock" → `lock.front_door` (NOT `lock.front_door_lock`)
- "Kitchen Ceiling Light" → `light.kitchen_ceiling` (NOT `light.kitchen_ceiling_light`)
- "Pool Pump Switch" → `switch.pool_pump` (NOT `switch.pool_pump_switch`)

### Mitigation

1. **Include the domain's YAML file in your context** when generating test cases for
   that domain. Copy entity_ids from the YAML, don't construct them.
2. **Run `verify_entity_consistency.py`** after every generation session. It checks all
   `target_entities` values against the YAML inventory.
3. **Review the "Likely correct" suggestions** in the audit report if mismatches are
   found — the script uses superstring matching to identify confabulation patterns.

---

## 8. File Organization

### Per-domain NDJSON files

Each domain present in the YAML inventory gets its own NDJSON file in the tier
directory. Also include cross-domain and utility files:

```
{tier}/
├── light_test_cases.ndjson
├── climate_test_cases.ndjson
├── sensor_test_cases.ndjson
├── binary_sensor_test_cases.ndjson
├── cover_test_cases.ndjson
├── lock_test_cases.ndjson
├── media_player_test_cases.ndjson
├── fan_test_cases.ndjson
├── vacuum_test_cases.ndjson
├── lawn_mower_test_cases.ndjson
├── todo_test_cases.ndjson
├── weather_test_cases.ndjson
├── switch_test_cases.ndjson
├── valve_test_cases.ndjson
├── cross_domain_test_cases.ndjson      ← multi-domain, disambiguation, edge cases
└── utility_test_cases.ndjson           ← inventory-independent (tier: "all")
```

### What goes where

**Domain files** contain Step 1 (tool×domain cells), Step 2 (device subtypes), Step 4
(unusual states for that domain), and Step 5 (area commands for that domain).

**`cross_domain_test_cases.ndjson`** contains Step 3 (disambiguation scenarios that
span domains), Step 7 (multi-action commands), and Step 8 (edge cases). If a case's
primary purpose is testing disambiguation between entities across domains or areas, it
goes here — not in a domain file.

**`utility_test_cases.ndjson`** contains Step 6 (no-tool-call categories) and
inventory-independent tools (HassBroadcast, HassGetCurrentTime, HassGetCurrentDate,
HassNevermind). All cases use `inventory_tier: "all"` and `inventory_file: null`.

If a domain-specific tool needs one seed case but has no natural home in its domain
file (e.g., gap-filling a tool that applies to multiple domains), it can go in the
utility file with a note: "Gap-filling: [ToolName] coverage."

### Format

Each line is a complete, valid JSON object. No trailing commas, no wrapping array.
The file is NOT a JSON array — it's newline-delimited JSON (NDJSON). All test case
files use the `*_test_cases.ndjson` naming convention.

---

## 9. Generation Process — Step by Step

### Preparation

1. Load all YAML inventory files for the target tier (all domain YAMLs + areas.yaml).
2. Read the tool mapping table (§2.1) to identify which tools apply to which domains.

### Structural derivation pass

Walk through the algorithm in §2.2, generating cases for each structural dimension:

**Pass 1 — Per-domain files (Steps 1, 2, 4, 5):**

For each domain YAML:

1. List the entities — note entity_ids, names, areas, states, device_classes,
   supported_features.
2. From §2.1, identify which tools apply to this domain.
3. Generate one case per applicable tool (Step 1). Choose entities that are
   straightforward — save disambiguation for Step 3.
4. Scan for device subtypes not already covered by Step 1 cases. Generate one case per
   distinct subtype (Step 2).
5. Check for entities in unusual states (unavailable, unknown, jammed, error). Generate
   one case per state type encountered (Step 4). Distribute across domain files — don't
   put all unusual-state cases in one domain.
6. If the domain has multiple entities in any area, generate one area+domain command
   (Step 5).

**Pass 2 — Cross-domain file (Steps 3, 7, 8, 9, 10):**

After all domain files are done:

1. Scan across YAMLs for disambiguation scenarios (Step 3): within-area conflicts
   (scan for full conflict depth), cross-area name collisions, arealess-to-area
   conflicts, cross-domain device overlaps.
2. Generate multi-action commands combining tools from different domains (Step 7).
3. Generate edge cases: walk the failure mode checklist — nonexistent entity,
   unsupported action, wrong domain action, action on unavailable entity (Step 8).
4. Scan inventory for implicit intent / scene contexts: entity clusters that map to
   real-world scenarios like bedtime, leaving, movie time (Step 9).
5. Review query tools for information limitation gaps: what does each query tool
   *not* return that a user might expect? (Step 10).

**Pass 3 — Utility file (Step 6 + inventory-independent tools):**

1. Generate cases for inventory-independent tools: HassBroadcast, HassGetCurrentTime,
   HassGetCurrentDate, HassNevermind, HassGetWeather (default/no-name).
2. Generate no-tool-call cases: out-of-scope, conversational, general knowledge,
   incomplete commands, gibberish, ambiguous intent.
3. All cases use `inventory_tier: "all"`, `inventory_file: null`.

### Verification

After generating all files:

```
python3 verify_entity_consistency.py <data_dir> --output <report_dir>
```

Fix any entity_id mismatches before considering the data ready.

---

## 10. Worked Example — Lock Domain (Step 1)

Starting from the lock YAML:

```yaml
entities:
  - entity_id: lock.front_door
    name: Front Door Lock
    area: entry
    state: "locked"
    attributes:
      supported_features: 1
```

**Step 1: Identify applicable tools.** Lock domain supports: HassTurnOn (= lock),
HassTurnOff (= unlock), HassGetState. Three cells → three cases.

**Construct one case (HassTurnOn × lock):**

```json
{
  "id": "enormous-HassTurnOn-lock-front_door-001",
  "utterance": "lock the front door",
  "expected_tool_calls": [
    {"name": "HassTurnOn", "arguments": {"name": "Front Door Lock", "domain": ["lock"]}}
  ],
  "expected_response_type": "action_done",
  "inventory_tier": "enormous",
  "inventory_file": "test_data/inventories/enormous/combined.yaml",
  "metadata": {
    "intent_type": "lock_control",
    "complexity": "moderate",
    "target_entities": ["lock.front_door"],
    "target_areas": ["Entry"],
    "case_key": "HassTurnOn-lock-front_door-001",
    "notes": "Counter-intuitive mapping: lock = HassTurnOn per HA default instructions. Key instruction-following test."
  }
}
```

Note: `target_entities` uses `lock.front_door` (copied from YAML), NOT
`lock.front_door_lock` (confabulated from the friendly name "Front Door Lock").

---

## 11. Worked Example — Cross-Domain Disambiguation (Step 3)

The Enormous inventory has both `climate.living_room_thermostat` (area: living_room)
and `sensor.living_room_temperature` (area: living_room) — both can answer "what's the
temperature in the living room". This is a Step 3 disambiguation scenario.

```json
{
  "id": "enormous-HassClimateGetTemperature-cross-living_room_temp-001",
  "utterance": "what's the temperature in the living room",
  "expected_tool_calls": [
    {"name": "HassClimateGetTemperature", "arguments": {"area": "Living Room"}}
  ],
  "alternative_expected_tool_calls": [
    {
      "tool_calls": [{"name": "HassGetState", "arguments": {"name": "Living Room Temperature", "domain": ["sensor"]}}],
      "quality": "acceptable",
      "reason": "Dedicated sensor returns accurate ambient reading. Domain-specific climate tool is the designed path but both give a temperature number."
    },
    {
      "tool_calls": [{"name": "HassClimateGetTemperature", "arguments": {"name": "Living Room Thermostat"}}],
      "quality": "equivalent",
      "reason": "Targeting by name instead of area is equally valid when only one climate entity exists in the area."
    }
  ],
  "expected_response_type": "query_response",
  "inventory_tier": "enormous",
  "inventory_file": "test_data/inventories/enormous/combined.yaml",
  "metadata": {
    "intent_type": "disambiguation",
    "complexity": "moderate",
    "target_entities": ["climate.living_room_thermostat", "sensor.living_room_temperature"],
    "target_areas": ["Living Room"],
    "case_key": "HassClimateGetTemperature-cross-living_room_temp-001",
    "notes": "Disambiguation: climate + sensor in same area. Both have area assignments. HassClimateGetTemperature is optimal path. T3 analysis: does model choose the right tool?"
  }
}
```

---

## 12. Checklist Before Finalizing

After generating all test case files for a tier:

**Structural coverage (§2):**
- [ ] Every tool × domain cell from §2.1 (where domain has entities) has a case
- [ ] Every distinct device subtype has a case (if not covered by tool×domain cases)
- [ ] Every YAML-documented disambiguation scenario has a case
- [ ] Every unusual entity state type (unavailable, unknown, jammed, error) has a case
- [ ] Every domain with multi-entity areas has an area+domain command case
- [ ] No-tool-call cases cover: out-of-scope, conversational, general knowledge,
      incomplete, gibberish, ambiguous intent
- [ ] Multi-action cases span at least 2 different domain combinations
- [ ] Edge cases cover all supported failure modes: nonexistent entity, unsupported
      action, wrong domain action, action on unavailable entity (if inventory supports)
- [ ] Implicit intent / scene commands cover each distinct scene context in inventory
- [ ] Tool limitation probes cover each query tool with a meaningful information gap

**Quality:**
- [ ] Alternatives have quality ratings and reasons (only where genuinely defensible)
- [ ] Notes explain what structural dimension each case tests
- [ ] Notes include T3 evaluation hooks for edge cases with unusual states
- [ ] Utterances are direct voice-assistant style (no filler words in structural cases)

**Format & consistency:**
- [ ] All required fields present in every case
- [ ] `id` follows the naming convention
- [ ] `case_key` matches `id` minus the tier prefix
- [ ] `inventory_file` is `test_data/inventories/{tier}/combined.yaml` for tier-specific, `null` for all
- [ ] Valid JSON on every line (no trailing commas, proper escaping)
- [ ] Domain-specific tools don't include redundant `domain` argument
- [ ] Generic tools (HassTurnOn/Off, HassToggle, HassGetState) include `domain`

**Entity ID safety (§7):**
- [ ] All `target_entities` values copied verbatim from YAML, not constructed from
      friendly names
- [ ] `verify_entity_consistency.py` passes with 0 errors
- [ ] No `_lock`, `_light`, `_switch`, `_fan` suffixes that echo the domain name

**Budget check:**
- [ ] Total cases fall within ~110-150 range for full-domain inventory
- [ ] Each case maps to a specific structural dimension (if you can't name it, remove it)

---

## 13. Known Gaps / Follow-up Items

1. **Expansion guide status:** `test-case-expansion-guide.md` (companion document)
   covers how to add variety on top of the structural cases. Marked as untested/draft.
   The structural cases should be validated through a benchmark run before investing
   heavily in expansion.

2. **Self-sufficiency validation:** A blind generation test using an earlier version of
   this guide produced correct tool mappings and entity IDs across all domains. The
   structural derivation algorithm (§2) was added to address calibration issues
   (quantity, scope) found in that test. A subsequent triple-comparison analysis
   (NEW vs ORIG vs PREV) validated completeness but identified depth gaps, leading
   to the Step 3/8 revisions and new Steps 9/10. The updated algorithm (with all
   10 steps) has not yet been blind-tested.

3. **Tool table maintenance:** The tool × domain mapping table (§2.1) must be updated
   when Home Assistant adds new intents or domains. The table should be verified
   against the current `intents.yaml` in the home-assistant/intents repo before each
   generation run.

4. **YAML inventory dependency for Step 8d:** Step 8d (action on unavailable entity)
   requires at least one unavailable *actionable* entity in the YAML inventory. This
   constraint has been added to `generation-principles.md` (§2 meta-states + §9
   checklist) and `derivation-guide.md` (§3 selection principles + §6 degradation
   tracking). If the current inventory lacks such an entity, the step should note
   the gap rather than silently skip it.

5. **Step 10 dependency on tool semantics:** Step 10 (tool limitation probes) requires
   knowledge of what each query tool actually returns, which goes beyond what the YAML
   inventory provides. Generators may need to consult §6 (HA Domain Knowledge) sources
   or supplementary documentation about tool return values. Consider adding a concise
   "tool return value summary" table in a future revision.

6. **HA Scenes & Automations (future scope):** User-created Scenes and Automations can
   be exposed as callable entities (e.g., `scene.turn_on` on a "Good Night" scene).
   This would simplify Step 9 significantly — implicit intent maps to a single scene
   tool call instead of multi-action inference. Tracked as backlog for future YAML
   inventory expansion and test case evolution, not current scope.
