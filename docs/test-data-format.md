# Test Data Format

This documents the NDJSON test case format and YAML inventory format used by the benchmarking framework.

---

## Test Cases — NDJSON Format

Each line in an NDJSON file is one test case. The dataset loader reads these into Inspect AI `Sample` objects.

### Schema

```json
{
  "id": "string — unique correlation ID",
  "utterance": "string — what the user said",
  "expected_tool_calls": [
    {
      "name": "string — intent tool name",
      "arguments": {
        "key": "value — expected argument"
      }
    }
  ],
  "expected_response_type": "string — action_done|query_response|text_response|error|clarification",
  "inventory_tier": "string — small|medium|large|enormous",
  "inventory_file": "string — repo-relative path to inventory YAML",
  "metadata": {
    "intent_type": "string — e.g. light_control, climate, state_query",
    "difficulty": "string — basic|intermediate|advanced",
    "description": "string — human-readable description of what's being tested"
  }
}
```

### Required Fields

All of `id`, `utterance`, `expected_tool_calls`, `expected_response_type`, `inventory_tier`, `inventory_file`.

### Field Details

**`id`** — Structured correlation ID. Format: `{tier}-{tool}-{domain}-{entity}-{seq}`
Example: `small-HassTurnOn-light-kitchen_ceiling-001`

**`utterance`** — The voice command text. This is what faster-whisper would produce after STT — no punctuation normalization, natural phrasing.

**`expected_tool_calls`** — Array of tool calls the model should make. Empty array `[]` for error/clarification cases. Order doesn't matter (scorer matches order-independently).

**`alternative_expected_tool_calls`** *(optional)* — List of alternative acceptable call sets. Each element is an array of tool calls (same format as `expected_tool_calls`). If the model's response doesn't match the primary `expected_tool_calls` but matches any alternative set, the sample scores C. Use when multiple tool choices are legitimately correct.

```json
"alternative_expected_tool_calls": [
  [{"name": "HassGetState", "arguments": {}}]
]
```

**`expected_response_type`** — How the model should respond:
- `action_done` — Model should call tool(s) to perform an action
- `query_response` — Model should call a query tool (HassGetState, HassClimateGetTemperature, HassGetWeather, HassGetCurrentTime, HassGetCurrentDate)
- `text_response` — Model should answer in plain text without calling any tools (general knowledge, conversational, greetings)
- `error` — Model should refuse gracefully (no tool calls) — e.g., entity doesn't exist
- `clarification` — Model should ask for more info (no tool calls) — e.g., ambiguous command

**`inventory_tier`** — Which inventory size this case is designed for. Cases from larger tiers can be run against smaller inventories (they'll likely fail on missing entities — that's expected and informative).

**`inventory_file`** — Repo-relative path to the inventory YAML. Always starts with `sample_test_data/`.

**`metadata`** — Optional bag for categorization. Not used by the scorer, but useful for filtering and analysis. Common keys: `intent_type`, `difficulty`, `description`, `tags`.

### Argument Matching Conventions

**Exact match:** `"name": "Kitchen Ceiling"` — the model must produce this exact value (case-insensitive).

**Flexible match (`_any_of`):** `"name_any_of": ["Kitchen Ceiling", "Kitchen Light"]` — the model can produce any value from the list. Use when multiple entity names could reasonably satisfy the command.

The `_any_of` suffix is stripped during matching: `name_any_of` checks the model's `name` argument against the list.

**Empty arguments:** `"arguments": {}` — no argument constraints. The model can pass any arguments as long as the tool name is correct. Use for cases where multiple argument combinations are valid.

**Numeric tolerance:** Numeric arguments match within ±0.01. So `brightness: 50` matches `50`, `50.0`, etc.

**Array matching:** Arrays are compared as sorted sets (case-insensitive). `"domain": ["light"]` matches `["light"]` and `["Light"]`.

---

## Inventory — YAML Format

Inventories define the smart home entities available in a test scenario. They're loaded by `prompt.py` and formatted into the HA-style entity context in the system prompt.

### Schema

```yaml
areas:
  - id: kitchen        # snake_case identifier
    name: Kitchen      # Human-readable name (used in prompt)

  - id: living_room
    name: Living Room

entities:
  - entity_id: light.kitchen_ceiling   # domain.object_id format
    name: Kitchen Ceiling              # Friendly name (what users say)
    area: kitchen                      # References areas[].id
    state: "on"                        # Current state string
    attributes:                        # Domain-specific attributes
      brightness: 128
      color_mode: brightness
      supported_color_modes:
        - brightness

  - entity_id: lock.front_door
    name: Front Door Lock
    area: entry
    state: locked
    attributes:
      device_class: lock
```

### Field Details

**`areas[].id`** — Snake_case identifier. Referenced by `entities[].area`.

**`areas[].name`** — Human-readable. Appears in the system prompt as `areas: Kitchen`.

**`entities[].entity_id`** — HA entity ID format: `domain.object_id`. The domain prefix (before the dot) determines which intents can target this entity.

**`entities[].name`** — Friendly name. This is what users say in voice commands and what appears in `names:` in the system prompt.

**`entities[].area`** — References an area ID. Determines which area commands ("turn off the kitchen lights") affect this entity.

**`entities[].state`** — Current state as a string. Domain-dependent: lights use "on"/"off", locks use "locked"/"unlocked", covers use "open"/"closed", sensors use numeric values.

**`entities[].attributes`** — Domain-specific. The prompt serializer includes all non-null attributes. Common attributes by domain:

| Domain | Common Attributes |
|--------|------------------|
| light | brightness, color_mode, supported_color_modes, color_temp_kelvin |
| climate | temperature, current_temperature, hvac_modes, hvac_action |
| cover | current_position, device_class (blind, curtain, garage_door) |
| lock | device_class |
| sensor | device_class, unit_of_measurement |
| binary_sensor | device_class (motion, door, window, smoke) |
| media_player | volume_level, source, media_title |
| fan | percentage, preset_modes |

### Inventory Tiers

| Tier | Entities | Areas | Purpose |
|------|----------|-------|---------|
| Small | ~8-15 | ~6 | MVP testing, fast iteration |
| Medium | ~40-60 | ~12 | Moderate complexity |
| Large | ~150-200 | ~20 | Stress testing |
| Enormous | ~500 | ~20 | Maximum scale, community benchmark |

Smaller tiers are strict subsets of larger ones. The same entity always has the same name and attributes across tiers.
