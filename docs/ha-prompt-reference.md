# Home Assistant Prompt & Tool Reference

This documents how Home Assistant constructs prompts and tool definitions for its LLM-based voice pipeline. Our benchmarking framework replicates this format to produce results that are directly applicable to real HA deployments.

**Sources:** HA core `homeassistant/helpers/llm.py`, `homeassistant/components/openai_conversation/entity.py`, and the `custom-conversation` Langfuse template.

---

## System Prompt Structure

HA assembles a system prompt from several parts:

### Default Instructions

From `helpers/llm.py` `DEFAULT_INSTRUCTIONS_PROMPT`:

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

Notable: "Use HassTurnOn to lock and HassTurnOff to unlock" — this is counterintuitive but matches HA's intent mapping.

### Location Context (optional)

If the voice satellite has a known location:
```
Your location is {area_name}.
```

This affects how commands like "turn on the lights" are resolved — they target the satellite's area.

### Timer Support (optional)

If the HA instance supports timers:
```
When the user wants to set a timer, use the HassStartTimer intent.
```

### Entity Inventory

The largest part of the prompt. Lists all exposed entities in a YAML-like format:

```
An overview of the areas and the devices in this smart home:
light.kitchen_ceiling:
  names: Kitchen Ceiling
  state: 'on'
  areas: Kitchen
  attributes:
    brightness: 128
    color_mode: brightness
light.office_desk_lamp:
  names: Desk Lamp
  state: 'off'
  areas: Office
  attributes:
    brightness:
```

**Format notes:**
- Entity ID is the top-level key (`domain.object_id`)
- `names:` is the friendly name (what the user would say)
- `state:` is always single-quoted
- `areas:` is the area name (not ID)
- `attributes:` includes domain-relevant attributes. Null values show the key with no value.

### Timestamp

```
Current time is 12:00:00.
Today's date is 2026-03-01.
```

**Our ordering:** We place the timestamp last (after entities) rather than first (HA's default). This is deliberate — it optimizes KV cache reuse when running many test cases against the same inventory. See `architecture.md` for rationale.

---

## Tool (Intent) Schema Format

HA exposes intent tools in OpenAI function-calling format. The `_format_tool()` method in `openai_conversation/entity.py` produces:

```json
{
  "type": "function",
  "function": {
    "name": "HassTurnOn",
    "description": "Turns on/opens a device or entity",
    "parameters": {
      "type": "object",
      "properties": {
        "name": {"type": "string", "description": "Name of the entity"},
        "area": {"type": "string", "description": "Name of the area"},
        "floor": {"type": "string", "description": "Name of the floor"},
        "domain": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Domain of the entity"
        },
        "device_class": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Device class of the entity"
        }
      }
    }
  }
}
```

**Key details:**
- `domain` and `device_class` are **arrays**, not strings
- For `HassTurnOn`/`HassTurnOff`, all parameters are optional
- Tools with required parameters (e.g., `HassSetPosition.position`) include a `required` array
- `HassLightSet` does **not** have `domain`/`device_class` — it's light-specific

---

## MVP Intent Tools (7)

These are the tools defined for Milestone 1 benchmarking:

| Intent | Description | Key Parameters |
|--------|-------------|---------------|
| HassTurnOn | Turn on / open / lock | name, area, floor, domain, device_class |
| HassTurnOff | Turn off / close / unlock | name, area, floor, domain, device_class |
| HassLightSet | Set light brightness/color | name, area, floor, brightness, color |
| HassSetPosition | Set cover/valve position | name, area, floor, domain, device_class, position* |
| HassGetState | Query entity state | name, area, floor, domain, device_class, state |
| HassClimateSetTemperature | Set thermostat | name, area, floor, temperature* |
| HassClimateGetTemperature | Read temperature | name, area, floor |

\* = required parameter

---

## Supported Intent Slot Combinations

For entity-targeting intents, HA supports these slot patterns:

| Pattern | Example |
|---------|---------|
| name only | "table light" |
| area only | "kitchen" |
| area + name | "living room reading light" |
| area + domain | "kitchen lights" |
| area + device_class | "bathroom humidity" |
| device_class + domain | "carbon dioxide sensors" |

Models should prefer `name + domain` for single devices and `area + domain` for area-wide commands, per the system prompt instructions.

---

## Full Intent Inventory

See `../scratch/research-ha-intent-tools.md` in the project planning files for the complete list of 37 supported intents with all parameters. The MVP uses the 7 most common intents listed above. Future milestones will expand coverage.
