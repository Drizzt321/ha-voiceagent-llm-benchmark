# Home Assistant Synthetic Inventory — Generation Principles

**Purpose:** Everything needed to generate or regenerate the Enormous inventory tier
from scratch. YAML format, state rules, capability attributes, HA source references,
disambiguation scenarios, realism guidelines, naming diversity, light capability
distribution, finalization checklist, and the Enormous design record.

**Audience:** An LLM agent or human generating a synthetic HA home inventory dataset
for voice assistant benchmarking, without access to the original discussion history.

**Created:** 2026-03-01 (Step 10, M2)

**See also:**
- `generation-guide.md` — index and overview
- `derivation-guide.md` — deriving smaller tiers (Large/Medium/Small) from Enormous
- `reference/ha-domain-behavior-reference.md` — what each HA tool returns per entity type
- `reference/ha-domain-tool-coverage-matrix.md` — domain × tool coverage, disambiguation scenarios
- `reference/ha-test-generation-reasoning-guide.md` — quality judgment framework for test cases
- `reference/ha-voice-llm-research.md` — HA ↔ LLM interface research (prompt format, entity context)
- `reference/benchmarking-framework-research/research-ha-intent-tools.md` — full 37-tool inventory
- Porter's `home-assistant-synthetic-home`: https://github.com/allenporter/home-assistant-synthetic-home

---

## 1. YAML Format

The inventory follows Porter's `home-assistant-synthetic-home` YAML schema. This is the
community standard for synthetic HA test fixtures and is immediately recognizable to anyone
familiar with HA's entity model.

### areas.yaml

```yaml
areas:
  - name: Kitchen          # Human-readable, used in LLM prompt
    id: kitchen            # snake_case, referenced by entities
  - name: Living Room
    id: living_room
```

### Domain YAML files

Each domain file contains only an `entities:` list. Areas come from `areas.yaml`.

```yaml
entities:
  - entity_id: light.kitchen_ceiling
    name: Kitchen Ceiling Light
    area: kitchen                          # references area id, or null for unassigned
    domain: light
    state: "off"
    attributes:
      supported_color_modes: ["brightness", "color_temp"]
      color_mode: null                     # null when off
      supported_features: 0
```

### Naming conventions

- **entity_id:** `{domain}.{snake_case_descriptive_name}` — e.g., `light.kitchen_ceiling`,
  `sensor.living_room_temperature`, `binary_sensor.front_door_contact`
- **name (friendly name):** Title Case, descriptive — e.g., "Kitchen Ceiling Light",
  "Living Room Temperature", "Front Door Contact"
- **area:** References the `id` field from `areas.yaml`, or `null` for deliberately
  unassigned entities (used in disambiguation testing)

### What HA sends to the LLM

The entity context block in the LLM system prompt looks like this (from HA debug output):

```
An overview of the areas and the devices in this smart home:
light.kitchen_ceiling:
  names: Kitchen Ceiling Light
  state: 'off'
  areas: Kitchen
  attributes:
    brightness:
```

**The LLM sees:** entity_id, friendly name, current state, area, and a summary of
capability attributes. It does NOT see current attribute values (brightness level, media
title, temperature reading). Those are only accessible by calling tools (HassGetState, etc.).

**This means:**
- `state` field matters — the LLM sees it and may factor it into decisions
- Capability attributes matter — they tell the LLM what the entity can do
- Current value attributes do NOT matter — they aren't in the prompt

---

## 2. State Field — What to Generate and Why

### The principle

The `state` field is visible to the LLM in the system prompt. For the Enormous dataset,
**every non-transient state value that a domain can have should be represented by at least
one entity.** This ensures test cases can exercise LLM behavior for each state the model
would actually see.

### What counts as a state vs transient

- **States to cover:** Conditions that an entity would realistically sit in for minutes to
  hours. Examples: `docked`, `cleaning`, `locked`, `playing`, `heat`, `off`.
- **Transient states (document but skip):** Conditions that last seconds during a transition.
  Examples: `opening`, `closing`, `locking`, `unlocking`, `returning`. These are real HA
  states but impractical to represent in a static inventory. Document as gaps.
- **Meta-states (always include):** `unavailable` and `unknown` can apply to any domain.
  Include at least one entity per meta-state somewhere in the inventory for graceful
  degradation testing.

### When state influences tool selection

For most domains, the state value doesn't change which tool the LLM should call — "turn on
the light" calls HassTurnOn whether the light is currently on or off. But there are cases
where state matters:

| Domain | State affects tool selection? | Example |
|--------|------------------------------|---------|
| media_player | Yes | `playing` → HassMediaPause; `paused` → HassMediaUnpause |
| climate | Yes (for queries) | `heat` state answers "is the heater running?" |
| lock | Yes (for queries) | `locked`/`unlocked` answers "is the door locked?" |
| vacuum | Marginal | LLM might decline to start a vacuum in `error` state |
| Most others | No | Tool selection is the same regardless of current state |

### Per-domain state inventory

Generate entities with these states. Where entity count < state count, prioritize the
most operationally distinct states. Document gaps in the `inventories/README.md`.

| Domain | All possible states | Priority states to cover | Notes |
|--------|--------------------|--------------------------|----- |
| light | `on`, `off` | Both (trivial) | A plausible occupied-home snapshot might have 20-40% of lights on |
| switch | `on`, `off` | Both (trivial) | |
| binary_sensor | `on`, `off` | Both (trivial) | Semantic meaning varies by device_class |
| sensor | Numeric/string reading | Varied readings | State IS the sensor value |
| climate | `off`, `heat`, `cool`, `heat_cool`, `auto`, `dry`, `fan_only` | `off`, `heat`, `cool`, `auto`, `heat_cool` | `dry`, `fan_only` less common — note as gaps |
| cover | `open`, `closed`, `opening`, `closing` | `open`, `closed` | `opening`/`closing` are transient |
| lock | `locked`, `unlocked`, `locking`, `unlocking`, `jammed` | `locked`, `unlocked`, `jammed` | `locking`/`unlocking` are transient |
| media_player | `off`, `on`, `idle`, `playing`, `paused`, `buffering` | All 6 (enough entities to cover) | `buffering` is brief but not transient |
| fan | `on`, `off` | Both (trivial) | |
| vacuum | `cleaning`, `docked`, `returning`, `idle`, `paused`, `error` | `docked`, `cleaning`, `error` | 3 entities; `returning`/`idle`/`paused` noted as gaps |
| lawn_mower | `mowing`, `docked`, `paused`, `returning`, `error` | `docked`, `mowing`, `error` | 3 entities; `paused`/`returning` noted as gaps |
| weather | 15 conditions (see §domain notes) | `sunny`, `rainy`, `cloudy` | 3 entities; 12 other conditions noted as gaps |
| todo | Integer count of incomplete items | Varied counts (0, 3, 7) | State is the count, not a category |
| humidifier | `on`, `off` | Both if included | |
| valve | `open`, `closed`, `opening`, `closing`, `stopped` | `open`, `closed` | Transient states noted as gaps |
| water_heater | `eco`, `electric`, `performance`, `high_demand`, `heat_pump`, `gas`, `off` | `eco`, `off` if included | |

### Meta-states: unavailable and unknown

These apply to any domain. Include at least:
- One entity with `state: "unavailable"` (e.g., `sensor.garage_temperature`) — tests
  graceful handling of offline devices
- One entity with `state: "unknown"` (e.g., `binary_sensor.back_door_contact`) — tests
  graceful handling of uninitialized devices
- **At least one unavailable *actionable* entity** (light, switch, cover, fan, lock,
  etc. — not just a sensor). This enables testing whether the LLM correctly avoids
  issuing tool calls on entities it can see are offline. A sensor being unavailable
  only tests query behavior; an actionable entity being unavailable tests whether the
  model refrains from acting. This is required at every inventory tier — see
  `derivation-guide.md` for preservation rules during tier derivation.

These should be in areas where other working entities exist, so the LLM has context about
the area but must handle the broken entity.

---

## 3. Capability Attributes — What to Generate

### The principle

Include attributes that describe what the entity **can do** (its capabilities), not what
it's currently doing (its runtime values). The LLM sees capability summaries in the prompt
and uses them for tool selection. Current readings are only accessible via tool calls.

### What to include vs skip

| Include (capabilities) | Skip (runtime values) |
|------------------------|----------------------|
| `supported_color_modes` | `brightness` (current level) |
| `device_class` | `current_temperature` (current reading) |
| `supported_features` | `media_title` / `media_artist` |
| `hvac_modes` | `temperature` (current setpoint) |
| `preset_modes` | `rgb_color` (current color) |
| `fan_modes` | `volume_level` (current volume) |
| `source_list` | `current_cover_position` |
| `min_temp` / `max_temp` | `battery_level` |
| `min_mireds` / `max_mireds` | `media_duration` / `media_position` |

### Mixed capabilities within domains

**Critical design principle:** Within each domain, represent the realistic range of
capability profiles, not just the maximum-capability version. A real home has devices with
different feature sets from different manufacturers and eras.

This affects which tool arguments are valid per entity. For example, `HassLightSet` with
a `color` parameter only makes sense for RGB-capable lights. If the inventory only contains
full-RGB lights, the benchmark can't test whether the LLM correctly avoids sending color
commands to brightness-only lights.

**Domains with meaningful capability variation:**

| Domain | Capability profiles to mix | Example entities |
|--------|---------------------------|-----------------|
| light | onoff-only (smart switch on dumb bulb), brightness-only, color_temp (white spectrum), full RGB, RGBW | Garage light (onoff), bedroom lamp (brightness+color_temp), LED strip (rgb) |
| cover | Binary open/close only, position-capable (0-100), position + tilt | Garage door (binary), living room blinds (position+tilt), curtains (position only) |
| climate | Heat-only, cool-only, heat+cool+auto, with/without fan_mode, with/without preset | Baseboard heater (heat-only), central HVAC (full), portable heater (heat-only) |
| media_player | Basic (play/pause/volume), with source selection, with search, speaker groups | Smart TV (full), Bluetooth speaker (basic), speaker group (grouped) |
| fan | Speed-only, speed + presets, speed + oscillation + direction | Exhaust fan (on/off only), ceiling fan (speed + direction), smart fan (full) |
| lock | Basic lock/unlock, with OPEN feature (physical latch) | Deadbolt (basic), smart lock with latch (OPEN feature) |

**General principle:** For any domain, ask "do all real-world devices of this type have
the same capabilities?" If no, include a mix. Check `supported_features` bitmask values
in the HA developer docs for the domain to identify which features are optional.

---

## 4. HA Source References for Domain Attributes

When generating inventory data, consult these HA source locations for authoritative
attribute schemas per domain. All paths relative to the HA core repo
(`github.com/home-assistant/core`). These source locations contain authoritative domain
behavior details — consult them if you need to verify state values, attribute
structures, or supported features during generation.

### Where to find attribute definitions

| Domain | Source file | Key classes/constants |
|--------|-----------|----------------------|
| light | `homeassistant/components/light/__init__.py` | `ColorMode` enum, `LightEntityFeature`, `ATTR_*` constants |
| climate | `homeassistant/components/climate/__init__.py` | `HVACMode`, `HVACAction`, `ClimateEntityFeature`, `PRESET_*` |
| cover | `homeassistant/components/cover/__init__.py` | `CoverEntityFeature`, `CoverDeviceClass` |
| lock | `homeassistant/components/lock/__init__.py` | `LockEntityFeature` |
| media_player | `homeassistant/components/media_player/__init__.py` | `MediaPlayerEntityFeature`, `MediaPlayerState`, `MediaClass` |
| fan | `homeassistant/components/fan/__init__.py` | `FanEntityFeature` |
| sensor | `homeassistant/components/sensor/__init__.py` | `SensorDeviceClass` (60 classes), `SensorStateClass` |
| binary_sensor | `homeassistant/components/binary_sensor/__init__.py` | `BinarySensorDeviceClass` (29 classes) |
| vacuum | `homeassistant/components/vacuum/__init__.py` | `VacuumEntityFeature`, `VacuumActivity` |
| lawn_mower | `homeassistant/components/lawn_mower/__init__.py` | `LawnMowerEntityFeature`, `LawnMowerActivity` |
| weather | `homeassistant/components/weather/__init__.py` | Condition constants |
| todo | `homeassistant/components/todo/__init__.py` | `TodoListEntityFeature` |
| valve | `homeassistant/components/valve/__init__.py` | `ValveEntityFeature`, `ValveDeviceClass` |
| humidifier | `homeassistant/components/humidifier/__init__.py` | `HumidifierEntityFeature` |
| water_heater | `homeassistant/components/water_heater/__init__.py` | `WaterHeaterEntityFeature` |

### How to extract capability attributes for a domain

1. Open the domain's `__init__.py` in the HA core repo
2. Find the `EntityFeature` flags enum — these define optional capabilities
3. Find the entity class (e.g., `LightEntity`) and its `@property` methods — these
   define the attributes
4. Cross-reference with `_attr_*` defaults to know which attributes are optional
5. Check `supported_features` property documentation for bitmask values
6. Look at `PLATFORM_SCHEMA` or `vol.Schema` definitions for valid value ranges

### How to find valid state values

1. Check the domain's `__init__.py` for state enums or constants
2. For `sensor`: state is the reading value (numeric, string, date) — no fixed enum
3. For `binary_sensor`: always `on`/`off`, but semantics vary by `device_class`
   (see the 29-class mapping in `ha-domain-behavior-reference.md` §4)
4. For all domains: `unavailable` and `unknown` are meta-states that can apply anywhere

---

## 5. Disambiguation & LLM Confusion Scenarios

The inventory must include specific entity combinations to enable tool-selection
quality testing. These are documented in detail in
`reference/ha-domain-tool-coverage-matrix.md` §Disambiguation Scenarios.

### Core disambiguation scenarios

| # | Scenario | Why it matters |
|---|----------|---------------|
| 1 | Climate entity + temp sensor, same area | Tests domain-specific vs generic tool routing |
| 2 | Sensor with area-suggestive name but no area assignment | Tests name-based vs area-based resolution |
| 3 | Climate entity without area + sensor with area | Tests fallback when preferred entity type lacks area |
| 4 | 3+ lights in same area | Tests area-scoped vs individual entity control |
| 5 | Same friendly name across different areas | Tests cross-area name collision |
| 6 | Entity in `unavailable` state | Tests graceful degradation |
| 7 | Entity with no area, area-based query | Tests name-based fallback resolution |
| 8 | Entity in `unknown` state | Tests graceful handling of uninitialized devices |

### Broader LLM confusion patterns

Beyond the numbered disambiguation scenarios, real HA installs create many situations
where an LLM must make non-obvious choices. The inventory should include examples of
these patterns:

| Category | Examples | Why it's hard |
|----------|----------|---------------|
| Same device-type name, different areas | Floor Lamp ×3, Vanity Light ×3, Nightlight ×4 | "Turn on the nightlight" with no area context |
| Cross-domain collision, same area | climate + switch.space_heater; media_player.tv + switch.tv_plug; climate.thermostat + climate.wine_cooler | "Turn off the heater" / "turn off the TV" / "set the temperature" — which domain? which entity? |
| Cross-area name embedding | binary_sensor.kitchen_patio_door (area: kitchen); light.living_room_entry_lamp (area: living_room) | Area name in entity name doesn't match actual area |
| Moved-but-never-renamed | light.old_living_room_lamp (area: guest_bedroom) | Name says living room, entity is in guest bedroom |
| Brand names as identifiers | light.hue_kitchen_strip, media_player.sonos_bathroom | Users say "turn on the Hue" or "play on the Sonos" |
| Abbreviation vs spelled-out | media_player.living_room_tv ("TV") vs guest_bedroom_television ("Television") | Synonym matching across naming conventions |
| Generic/unhelpful names | switch.smart_plug_1/2/3, light.smart_bulb_e7a2 | No useful name signal — common with cheap devices |
| Companion entity pairs | binary_sensor.washer_running + sensor.washer_cycle_remaining | "Is the washer done?" — different answer per target |
| Substring area matching | Bedroom vs Master Bedroom vs Guest Bedroom; Bathroom vs Master Bathroom vs Upstairs Bathroom | Area name substrings compete |
| Unit system mixing | 3D printer temps in °C, room temps in °F | Tests whether LLM handles mixed units in same area |

**Generation principle:** These patterns should emerge naturally from realistic device
naming and placement, not be artificially constructed. A real HA install accumulates these
confusion patterns over time as devices are added, moved, renamed (or not renamed),
and replaced.

### Companion entity groups

Some physical devices expose multiple entities across different domains. These form
logical groups that create interesting disambiguation and query-routing challenges:

| Physical device | Entities | Disambiguation value |
|----------------|----------|---------------------|
| Aquarium | light (aquarium light), sensor (water temp), switch (filter pump) | "Turn off the aquarium" — which entity? |
| 3D printer | switch (power), sensor ×3 (nozzle temp, bed temp, progress) | "What's the temperature?" in office with 5 temp sources |
| Washer | binary_sensor (running), sensor (cycle remaining), sensor (power) | "Is the laundry done?" — status vs time remaining |
| Dryer | sensor (cycle remaining), sensor (power) | Pair with washer — "how long until the laundry?" disambiguates washer vs dryer timer |
| EV charger | switch (charger), binary_sensor (connected), sensor (energy, power) | "Is the car charging?" |
| UPS | sensor (battery level), sensor (load) | Battery level competes with Zigbee battery sensors |

**Generation principle:** Include 3-5 companion groups in larger inventories. They test
whether the LLM can reason about which entity within a device group best answers the
user's intent.

### Placement guidelines

- Place disambiguation entities in high-density areas (Kitchen, Living Room) where
  multiple entity types naturally coexist
- Unassigned entities (`area: null`) should still have area-suggestive names to test
  whether the LLM falls back to name-matching
- Each scenario needs at least one test case in Step 12 — note during inventory creation
  which entities serve which scenario
- Cross-domain collisions work best in areas with diverse device types
- Companion entity groups work best in areas that already have high entity density,
  amplifying the disambiguation challenge

---

## 6. Realism Guidelines

### Do

- Assign entities to rooms where they'd physically exist (no vacuum in attic)
- Use device names that reflect real products/locations ("Kitchen Ceiling Light", not "Light 47")
- Mix device ages/capabilities (not every light is a full-RGB smart bulb)
- Include outdoor devices appropriate to the area (irrigation in yards, porch light at entry)
- Have higher entity density in common rooms (kitchen, living room) vs utility spaces
- Include integration-realistic entities (Zigbee sensors alongside WiFi smart plugs)

### Don't

- Don't put every device type in every room
- Don't use sequential/artificial naming ("Sensor 1", "Sensor 2")
- Don't give all entities the maximum capability profile
- Don't exceed realistic device counts for rare domains (see state coverage rules for
  allowable inflation)
- Don't assign areas to entities that are conceptually portable or location-independent
  (e.g., a portable heater used for disambiguation testing)

### "Tech hub" rooms

A room occupied by a technical hobbyist (home office, garage workshop) naturally
accumulates unusual devices: server rack temp sensors, 3D printer entities, aquarium
setups, UPS monitors. These create excellent disambiguation challenges because they
place many sensors of the same device_class (temperature, power) in one area. This is
realistic for the target demographic (smart home enthusiasts) and more interesting than
spreading devices uniformly across rooms.

**Principle:** Designate 1-2 areas as "tech hubs" with higher-than-average entity density
and unusual device types. These areas anchor the hardest disambiguation test cases.

### Unusual but real devices

Some devices use HA domains in non-obvious ways. These are valuable because they test
whether an LLM over-relies on domain-name heuristics:

| Entity | Domain | Why valuable |
|--------|--------|--------------|
| Standing desk | cover | "Raise the desk" maps to cover.set_position — not obvious |
| Pet door | cover | Disambiguation with lock + door contact in same area |
| Wine cooler | climate | Same-domain collision with HVAC thermostat; unusual temp range |
| Aquarium light | light | Unusual device in a high-density area |
| Holiday lights | light (not switch) | Could be either domain; tests real integration variance |

**Principle:** Include 3-5 unusual domain mappings per inventory. They expose whether
an LLM has learned rigid domain→device-type associations.

### Entity count inflation for state coverage

For domains with more states than realistic device count, the entity count may exceed
what a real home would have. This is acceptable for the Enormous dataset. Document the
inflation reason in `inventories/README.md`. The smaller tier datasets (Large, Medium,
Small) use realistic counts and accept the state coverage gaps — see `derivation-guide.md`
for details.

---

## 7. Device & Naming Diversity

A synthetic inventory's value for LLM benchmarking comes not from having many entities,
but from having entities that exercise *different reasoning paths*. This section covers
the principles behind generating diversity that matters.

### Naming archaeology

A real HA install is an archaeological record of decisions, mistakes, and evolving
conventions over months or years. The inventory should simulate this accumulated history
rather than presenting a clean, uniform naming scheme.

**The underlying principle:** LLMs trained on HA data will encounter naming inconsistency
in production. If the benchmark inventory uses perfectly consistent naming, it tests an
unrealistically easy scenario and overstates model accuracy.

Categories of naming inconsistency to include:

- **Brand names as identifiers.** Users who set up a Hue bridge or Sonos system often
  leave the brand in the entity name because it was auto-generated. A user might say
  "turn on the Hue" rather than "turn on the kitchen LED strip." This tests whether the
  LLM can resolve brand references to entities.
- **Generic auto-generated names.** Cheap smart plugs and bulbs often register with
  names like "Smart Plug 1" or "Smart Bulb E7A2" that the user never bothered to
  customize. These are legitimate entities with no useful name signal — the LLM must
  fall back to area or domain context.
- **Moved-but-never-renamed.** When a device is physically moved to a new room, the
  entity_id and friendly name often retain the old location. This creates a direct
  conflict between the entity name and its area assignment that the LLM must navigate.
- **Abbreviation inconsistency.** Different integrations or setup sessions may produce
  "TV" vs "Television", "Temp" vs "Temperature", "BR" vs "Bedroom". A user's phrasing
  may match one convention but not the other.
- **Integration-specific naming.** Different HA integrations (Zigbee2MQTT vs ZHA vs WiFi
  native) produce different naming patterns. Some prepend the integration name, some use
  the manufacturer's label, some auto-generate from the device model. An inventory that
  looks like it came from a single integration is unrealistically clean.

**Guidance for quantity:** These should be sprinkled throughout the inventory at a
realistic frequency — a handful of each category, not a systematic exhaustive set.
In a real install, most entities have reasonable names and a minority have problematic
ones. The goal is to ensure the problematic ones exist, not to maximize them.

### Device_class breadth over depth

For domains with many possible `device_class` values (binary_sensor has 29, sensor
has 60+), **breadth of coverage matters more than depth.** Each device_class potentially
changes the semantic meaning of a state or the appropriate response to a user query.

**The underlying principle:** A `binary_sensor` with `device_class: motion` in state `on`
means "motion detected." The same domain with `device_class: door` in state `on` means
"door is open." The LLM must understand these semantic differences to generate correct
natural language responses. If the benchmark only tests 3-4 common device_classes, it
can't evaluate this understanding.

For sensor entities specifically, the distribution should reflect a real home's sensor
ecosystem:

- **High frequency (many instances):** temperature, humidity, battery — cheap Zigbee
  sensors in every room, every wireless device reports battery level
- **Moderate frequency:** power/energy monitoring (smart plugs with metering),
  illuminance (outdoor and room sensors), moisture (leak detectors, soil sensors)
- **Long tail (1-2 instances each):** CO2, UV index, data rate, duration, atmospheric
  pressure, and specialized types — individually rare but collectively important for
  testing the LLM's ability to handle unfamiliar sensor types

**Guidance:** Don't force coverage of every possible device_class — many are exotic
(e.g., `sensor.device_class: nitrogen_dioxide`). But aim for at least 10-15 distinct
sensor device_classes and 10+ binary_sensor device_classes to test breadth. The uncommon
ones (tamper, gas, vibration, sound, presence) are individually more valuable than adding
a 6th motion sensor.

### Cross-domain device identity

When a physical device can reasonably be represented in multiple HA domains, the inventory
should include at least one such multi-representation device. This tests whether the LLM
understands that user intent maps to a specific domain even when the device spans several.

**The underlying principle:** A user saying "turn off the TV" might mean
`media_player.turn_off` (standby) or `switch.turn_off` (kill power). The LLM must
disambiguate based on likely intent, not just string matching. Similarly, "turn off the
water" could target an irrigation switch, a valve, or a fountain — all legitimate but
with different implications.

Common cross-domain patterns in real HA installs:
- **TV:** media_player (content control) + switch (power plug)
- **Space heater:** climate (temperature control) + switch (power)
- **Irrigation:** switch (zone valve) + valve (main shutoff or drip line)
- **Washer/dryer:** binary_sensor (running/vibration) + sensor (power, cycle remaining)
- **3D printer:** switch (power) + sensor (temps, progress)

**Guidance:** Include at least 2-3 cross-domain devices. Place them in areas with other
entities of the same domains to maximize the disambiguation surface.

### Unusual domain mappings

HA's domain system maps devices to domains based on the integration's implementation,
not on human intuition about what a device "is." Some mappings are non-obvious. Including
a few of these tests whether the LLM has learned rigid domain→device-type associations
that break on real-world edge cases.

**The underlying principle:** An LLM might learn "covers are window blinds" and fail to
route "raise the desk" to the cover domain. Or it might learn "climate means HVAC" and
not consider that a wine cooler is also a climate entity. These biases are invisible if
the inventory only contains conventional devices.

**Guidance:** Think about what HA domains *could* contain that a user wouldn't expect,
and include a few. The specific devices will vary by house profile — a standing desk is
realistic in a home office, a wine cooler in a kitchen, a pet door wherever there's a
mudroom. The principle is: "what real devices would surprise someone who thinks
`{domain}` always means `{obvious thing}`?"

---

## 8. Light Capability Distribution

Lights are the highest-volume domain and the one with the most capability variation.
When generating light entities, target this realistic distribution:

| Capability | Target % | Real-world examples |
|------------|----------|--------------------|
| onoff-only | ~15% | Smart switches on dumb bulbs, simple outdoor fixtures |
| brightness-only | ~25% | Basic smart bulbs, dimmable fixtures |
| color_temp (white spectrum) | ~35% | Most common smart bulb type (warm/cool white range) |
| RGB (full color) | ~20% | Color bulbs, LED strips |
| RGBW (color + dedicated white) | ~5% | Premium LED strips |

This distribution reflects a realistic home where most smart lighting is white-spectrum,
with some color-capable lights in accent/entertainment areas and basic on/off switches
on fixtures that predate the smart home build-out.

**Color temperature ranges should vary.** Not all color_temp bulbs have the same range.
Cheaper bulbs might do 2700K-5000K; premium ones do 2000K-6500K. Mix the
`min_color_temp_kelvin` / `max_color_temp_kelvin` values.

---

## 9. Checklist Before Finalizing

After generating all domain files for a tier:

**Core coverage:**
- [ ] Every intent tool from the 37-tool inventory has at least one targetable entity
- [ ] Every required disambiguation scenario (§5) has its entity combinations present
- [ ] Every non-transient state per domain has at least one entity (Enormous only)
- [ ] State coverage gaps are documented in README
- [ ] Mixed capability profiles within domains with meaningful variation
- [ ] `unavailable` and `unknown` meta-state entities exist (at least one each)
- [ ] At least one unavailable entity is *actionable* (light, switch, cover, etc.),
      not just a sensor — required for Step 8d test case generation

**Device & naming diversity (§7):**
- [ ] Naming archaeology: at least a few brand-name, generic, and moved-but-never-renamed entities
- [ ] Device_class breadth: 10+ distinct sensor device_classes, 10+ binary_sensor device_classes
- [ ] Cross-domain devices: at least 2-3 physical devices represented in multiple domains
- [ ] Unusual domain mappings: at least 2-3 non-obvious domain assignments
- [ ] Companion entity groups: at least 2-3 multi-entity device groups

**Format & consistency:**
- [ ] Entity naming follows HA conventions
- [ ] Area assignments are realistic (no vacuum in attic, irrigation outdoors)
- [ ] Entity_ids use `{domain}.{snake_case}` format
- [ ] No duplicate entity_ids across domain files
- [ ] Areas referenced by entities exist in areas.yaml

**Post-generation verification (after test case NDJSON exists):**
- [ ] Run `verify_entity_consistency.py` — confirms YAML cross-tier subset integrity
      and NDJSON `target_entities` match YAML entity_ids (see `derivation-guide.md` §10)
- [ ] All `target_entities` values are copied verbatim from YAML, not constructed from
      entity friendly names (common LLM confabulation: "Front Door Lock" → `lock.front_door_lock`
      instead of correct `lock.front_door`)

---

## 10. Enormous Tier — Design Record

This section captures the specific design decisions, entity counts, and lessons learned
from generating the Enormous tier. It serves as both a reference for regeneration and a
starting point for deriving smaller tiers (see `derivation-guide.md`).

### House profile

**Concept:** Large 2-floor suburban house with generous outdoor space. 20 areas total.
Designed to hold enough entities to cover every HA domain, every non-transient state,
and every disambiguation scenario without artificial padding.

**First floor (10 areas):** Kitchen, Dining Room, Living Room, Entry, Mudroom, Hallway,
Office, Laundry Room, Bathroom, Garage

**Second floor (7 areas):** Master Bedroom, Master Bathroom, Bedroom (kid/teen),
Guest Bedroom, Nursery, Upstairs Hallway, Upstairs Bathroom

**Outdoor (3 areas):** Patio (covered), Front Yard, Back Yard

### Area design rationale

- **Hallway split (first floor + upstairs):** Creates the same-name entity collision
  test (both have a "Hallway Light") naturally from the house layout.
- **Nursery instead of a third generic bedroom:** Unique device needs (warm-only light,
  sound machine, baby monitor sensor, temp/humidity). Different from bedrooms in which
  devices are realistic.
- **Mudroom as second entry point:** Common in larger houses. Gives a second lock point
  and a utilitarian space for smart plugs.
- **No Basement or Attic:** A 2-floor house with generous outdoor space doesn't need them
  for device variety. Sparse areas add entity count without testing value.
- **Office as tech hub:** 5 temperature sensors in one room (room, server rack, aquarium,
  3D printer nozzle, 3D printer bed). Realistic for a smart home enthusiast's home office.
  Creates the hardest disambiguation challenge in the inventory.
- **Kitchen dual climate:** Both an HVAC thermostat and a wine cooler (both climate domain).
  Same-domain same-area collision that tests value-based reasoning (55°F makes sense for
  wine, not HVAC).

### Entity count targets vs actuals

| Domain | Target | Actual | Notes |
|--------|--------|--------|-------|
| light | ~120 ±15 | 130 | Includes aquarium, christmas, Hue brand-name, generic smart_bulb, moved-but-never-renamed |
| binary_sensor | ~80 ±10 | 87 | 17+ device_classes for maximum variety |
| sensor | ~80 ±10 | 89 | Includes 3D printer temps (°C), UPS, aquarium, server rack |
| switch | ~60 ±10 | 61 | 6 irrigation zones, pool pump/heater, fountain, 3D printer, 3 generic smart plugs |
| cover | ~20 ±5 | 20 | Includes standing desk and pet door (unusual domain mappings) |
| media_player | ~15 ±3 | 18 | All 6 non-transient states covered. Projector, Sonos brand-name, whole-home audio group |
| fan | ~15 ±3 | 14 | Exhaust (on/off), ceiling (speed+direction), smart (full features) |
| lock | ~10 ±2 | 10 | 5 locked, 4 unlocked, 1 jammed. Mixed OPEN feature support |
| climate | ~8 ±2 | 9 | Portable heater (null area), wine cooler (unusual range). States: 3 heat, 2 off, 2 cool, 1 auto, 1 heat_cool |
| vacuum | 3 exact | 3 | States: docked, cleaning, error |
| lawn_mower | 3 exact | 3 | States: docked, mowing, error |
| weather | 3 exact | 3 | Home (sunny), parents house (rainy), vacation cabin (cloudy) |
| todo | 3 exact | 3 | Shopping list, household tasks, grocery list |
| valve | ~3 | 3 | Water main, gas main, drip irrigation zone |
| **TOTAL** | **~500-550** | **453** | Below aggregate target but all per-domain targets met |

**Why 453 < 500-550:** The original aggregate was a rough sum of generous per-domain ranges.
Every individual domain hit its target range and all quality criteria were met. Additional
entities would be padding that doesn't improve test coverage. The per-domain targets are
the real constraint; the aggregate was an estimate.

### Key judgment calls

1. **3D printer °C vs °F:** 3D printer temperatures use °C (industry standard) while all
   room temperatures use °F (US home). Tests unit awareness — "what's the temperature in
   the office?" returns mixed units.

2. **Holiday lights as light (not switch):** Could go either way. Some integrate as switch
   (smart plug), some as light (smart LED string). Made it a light entity for domain diversity.

3. **Vacuum/lawn mower count inflation:** 3 entities each where a real home has 1-2.
   Justified for state coverage (docked, active, error). Documented as acceptable inflation.

4. **Separate climate entities per area (not shared HVAC zones):** Real homes share
   thermostats across zones. For benchmarking, separate entities per area gives cleaner
   test targeting. Chose testability over physical realism.

5. **Wine cooler as climate entity:** Real wine coolers do integrate as climate in HA.
   The unusual temperature range (45-65°F) creates a same-domain same-area collision where
   the LLM must use value context to route correctly.

6. **Valve domain inclusion:** Valve is relatively new in HA but needed for HassSetPosition
   tool coverage (covers and valves share that tool). Without valve entities, that tool path
   is untestable for this domain. Irrigation zone as valve (vs switch) also creates cross-domain
   disambiguation.

### Irrigation design

The Enormous tier has 6 irrigation zone switches (3 front yard, 3 back yard) plus
1 valve-domain drip irrigation zone, companion soil moisture sensors, and a back yard
fountain. This creates the "turn off the water" disambiguation challenge (fountain +
irrigation switches + water main valve all in play).

### HVAC / Climate distribution

Not every area has a climate entity — that would be unrealistic. Climate entities exist
in areas with dedicated thermostats or HVAC zones: Kitchen, Living Room, Office,
Master Bedroom, Bedroom, Nursery (baby comfort), plus portable heater (null area)
and wine cooler (kitchen). No climate in hallways, bathrooms, garage, or outdoor areas.

### Outdoor areas

- **Front Yard:** Landscape lighting (pathway, spotlights, garden), irrigation zones 1-3,
  soil moisture sensors, driveway motion sensor, holiday lights.
- **Back Yard:** Landscape lighting, irrigation zones 4-6, soil moisture sensors,
  pool pump/heater, fountain, lawn mower. Drip irrigation valve. Wind speed sensor
  (common weather station addition alongside temperature and humidity).
- **Patio:** Covered outdoor living space. Ceiling fan, outdoor speaker (media_player),
  string lights, bug zapper, patio heater.

### Per-domain generation notes

These capture the specific diversity decisions made for each domain in the Enormous tier.
They illustrate the general principles in §7 and serve as a reference for regeneration
or verification. The specific entities are suggestions based on experience, not rigid
requirements — a regeneration should apply the same principles but may arrive at
different specific devices.

**Light (130 entities):**
The largest domain by count. Distribution targets: ~15% onoff-only, ~25% brightness,
~35% color_temp, ~20% RGB, ~5% RGBW (see §8 for rationale). Naming edge cases
included: Hue brand-name strip (`light.hue_kitchen_strip`), generic auto-generated
bulb (`light.smart_bulb_e7a2`), moved-but-never-renamed lamp (`light.old_living_room_lamp`
in guest_bedroom), Christmas/holiday lights as light domain (not switch). Duplicate
friendly-name patterns: Floor Lamp ×3, Vanity Light ×3, Desk Lamp ×2, Nightlight ×4
across areas — creates "which nightlight?" ambiguity. Hallway areas should have
higher light density than might seem obvious — a 2-story house hallway realistically
has 5-6 light entities: overhead, 1-2 wall sconces, stairwell light, under-stair or
closet light. This density makes area-wide commands ("turn off hallway lights") more
interesting for testing.

**Sensor (89 entities):**
Most heterogeneous domain. Device_class distribution follows the real sensor ecosystem:
20+ temperature (cheap Zigbee sensors everywhere), 17+ battery (every wireless device),
14+ humidity, 9+ power, 6 moisture, 5+ illuminance, 3 energy, 2 CO2, 2 data_rate,
2 duration, plus one-offs (atmospheric_pressure, UV index). Long-tail device_classes
are individually rare but collectively exercise whether the LLM can handle unfamiliar
sensor types. Unusual sensors: 3D printer nozzle/bed temp (°C in a °F home), server
rack temp, aquarium water temp, UPS battery level (competes with Zigbee sensor
batteries for "battery level" queries), UPS load.

**Binary sensor (87 entities):**
High device_class variety: 17+ distinct classes. Common classes (motion, door, window,
moisture) have many instances across areas. Uncommon classes included for breadth:
tamper (gate), presence (car in garage), running (washer), connectivity (internet),
plug (EV charger), vibration (washer/dryer), sound (nursery baby monitor), gas (garage),
battery (lock low battery). Cross-area naming: `binary_sensor.kitchen_patio_door`
assigned to kitchen area (name embeds "patio" — misleading).

*Occupancy sensor placement:* Include 5-7 occupancy sensors in rooms where sustained
presence triggers automations — kitchen, living room, office, bedrooms, bathrooms.
Occupancy sensors (mmWave, PIR presence) detect sustained presence and are distinct
from motion sensors, which detect transient movement. Use motion sensors for
transitional spaces like hallways and entries. Carbon monoxide detectors should have
at least 3 instances — one per habitable floor plus near the garage — to reflect
building code requirements.

**Switch (61 entities):**
Includes appliance types that real users struggle to voice-control: garbage disposal,
boot dryer, electric blanket. Irrigation zones (6 total, 3 per yard) with companion
soil moisture sensors. Pool equipment (pump + heater — cross-entity: "turn off the
pool"). Fountain in back yard creates the "turn off the water" disambiguation with
irrigation zones and water main valve. Generic smart plugs (×3, two with area, one
without) — worst-case naming. TV plug alongside media_player.tv for cross-domain
collision.

**Cover (20 entities):**
Capability variation: garage doors (binary open/close only), blinds (position + tilt),
curtains (position only), shades (position only), awning (position only). Unusual
domain mappings: standing desk (`cover.office_standing_desk` — position control maps
to cover domain) and pet door (`cover.mudroom_pet_door` — disambiguation with lock
and door contact sensor in same area).

**Media player (18 entities):**
All 6 non-transient states covered across entities. Device types: TVs, soundbar,
speakers, speaker groups, smart display, projector. Naming edge cases: Sonos brand-name
(`media_player.sonos_bathroom`), "TV" vs "Television" abbreviation inconsistency,
"whole home audio" group entity. Projector alongside TV in living room creates "watch
a movie" / "turn on the TV" disambiguation — projector or TV?

**Climate (9 entities):**
States: 3 heat, 2 off, 2 cool, 1 auto, 1 heat_cool. Portable heater with null area
(disambiguation scenario 3). Wine cooler in kitchen alongside thermostat — same domain,
same area, but radically different temperature ranges (45-65°F wine vs 60-85°F HVAC).
Capability variation: heat-only (portable heater), heat+cool (bedroom), full HVAC with
fan modes and presets (kitchen, living room).

**Lock (10 entities):**
States: 5 locked, 4 unlocked, 1 jammed. Mixed `supported_features`: some with OPEN
feature (physical latch release), some basic lock/unlock only. Front door has both a
lock and a deadbolt — "lock the front door" is ambiguous.

**Fan (14 entities):**
Capability spectrum: exhaust fans (on/off only, no speed), ceiling fans (speed +
direction), tower/desk fans (full: speed + oscillation + direction + presets). This
tests whether the LLM correctly avoids sending speed commands to exhaust fans that
only support on/off.

**Vacuum (3), Lawn mower (3):**
Entity count inflated from realistic 1-2 to cover 3 states each (docked, active, error).
Documented as acceptable inflation. Each entity has different `supported_features` to
test capability variation.

**Weather (3), Todo (3):**
Weather: 3 locations (home, parents house, vacation cabin) for "what's the weather?"
disambiguation. Todo: 3 lists with different item counts (0, 3, 7) — tests
HassListAddItem routing.

**Valve (3 entities):**
Needed for HassSetPosition tool coverage — covers and valves share that tool path.
Water main shutoff (garage), gas main shutoff (garage), drip irrigation zone (back yard).
The irrigation valve creates cross-domain disambiguation with irrigation switches.

### Edge cases by design intent

This table maps the specific edge case entities in the Enormous tier back to the
general principles they illustrate (see §7). When regenerating, use this as a
*suggestion list* — the specific devices may change, but each principle should have at
least one illustration. An LLM regenerating this inventory should read the principles,
consider whether these specific choices still make sense, and feel free to substitute
equivalent devices that serve the same principle.

| Principle | Enormous implementation | Why this specific choice |
|-----------|----------------------|------------------------|
| Brand-name identifiers | light.hue_kitchen_strip, media_player.sonos_bathroom | Hue and Sonos are the most common brand-name integrations in real HA installs |
| Generic/auto-generated names | switch.smart_plug_1/2/3, light.smart_bulb_e7a2 | Hex suffix simulates auto-discovery; numbered plugs simulate lazy setup |
| Moved-but-never-renamed | light.old_living_room_lamp (area: guest_bedroom) | "Old" prefix makes the history visible; guest bedroom is a common destination for hand-me-down lamps |
| Abbreviation inconsistency | media_player.living_room_tv vs media_player.guest_bedroom_television | Tests whether LLM treats TV/Television as synonyms |
| Cross-domain collision | media_player.living_room_tv + switch.living_room_tv_plug | Most common real-world instance of this pattern |
| Cross-domain collision | climate.office_thermostat + switch.office_space_heater | "Turn off the heater" — which domain? |
| Same-domain collision | climate.kitchen_thermostat + climate.kitchen_wine_cooler | Forces value-based reasoning (temperature ranges differ) |
| Unusual domain mapping | cover.office_standing_desk | Tests "cover means blinds" bias |
| Unusual domain mapping | cover.mudroom_pet_door | Triple disambiguation: cover + lock + door contact in same area |
| Unit system mixing | sensor.3d_printer_nozzle_temp (°C), sensor.office_temperature (°F) | 3D printing universally uses °C regardless of locale |
| Companion device group | 3D printer: switch + sensor ×3 | Creates 5 temp sensors in office — hardest disambiguation in inventory |
| Companion device group | Aquarium: light + sensor + switch | "Turn off the aquarium" — 3 possible targets |
| Long-tail sensor type | sensor.ups_battery_level | Competes with all Zigbee battery sensors for "battery" queries |
| Long-tail sensor type | sensor.3d_printer_progress | device_class: none — unusual enough to test generalization |
| Cross-area name embedding | binary_sensor.kitchen_patio_door (area: kitchen) | "Patio" in name but entity is in kitchen area |
| Substring area competition | Bedroom, Master Bedroom, Guest Bedroom all coexist | "Turn off the bedroom light" — which bedroom? |
| Semantic state variation | binary_sensor device_classes: motion, door, window, moisture, smoke, tamper... | Same on/off states mean completely different things |
| Water disambiguation cluster | switch.irrigation_zone_*, switch.back_yard_fountain, valve.water_main, valve.back_yard_drip_zone | "Turn off the water" has 4+ possible targets |
| Entertainment disambiguation | media_player.living_room_tv + media_player.living_room_projector | "Watch a movie" — TV or projector? |
| Seasonal naming | light.front_yard_christmas_lights | Tests whether LLM handles seasonal device references |
