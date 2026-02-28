"""HA system prompt assembly for the benchmarking Solver.

Assembles prompts matching HA's conversation agent format.
Uses cache-friendly ordering: static instructions first, variable content last.

Prompt format verified against:
  docs/ha-prompt-reference.md
"""

from pathlib import Path

import yaml

# Module-level cache for loaded inventories (keyed by absolute path)
_inventory_cache: dict[str, str] = {}

# Fixed for benchmarking determinism + KV cache optimization
FIXED_TIME = "12:00:00"
FIXED_DATE = "2026-03-01"

# HA's DEFAULT_INSTRUCTIONS_PROMPT — from helpers/llm.py
DEFAULT_INSTRUCTIONS = (
    "You are a voice assistant for Home Assistant.\n"
    "Answer questions about the world truthfully.\n"
    "Answer in plain text. Keep it simple and to the point.\n"
    "When controlling Home Assistant always call the intent tools.\n"
    "Use HassTurnOn to lock and HassTurnOff to unlock a lock.\n"
    "When controlling a device, prefer passing just name and domain.\n"
    "When controlling an area, prefer passing just area name and domain.\n"
    "When a user asks to turn on all devices of a specific type, "
    "ask user to specify an area, unless there is only one device of that type."
)


def build_system_prompt(
    inventory_file: str,
    base_dir: str = ".",
    include_timestamp: bool = True,
) -> str:
    """Assemble the full HA system prompt with entity inventory.

    Order is cache-friendly: static instructions → entity inventory →
    variable timestamp (at end, minimizes KV cache invalidation).

    Args:
        inventory_file: Relative path to inventory YAML file.
        base_dir: Base directory for resolving relative paths.
        include_timestamp: Whether to include date/time (default True).

    Returns:
        Complete system prompt string.
    """
    entity_context = _load_and_format_inventory(inventory_file, base_dir)

    parts = [
        DEFAULT_INSTRUCTIONS,
        "",
        "An overview of the areas and the devices in this smart home:",
        entity_context,
    ]

    if include_timestamp:
        parts.append("")
        parts.append(f"The current time is {FIXED_TIME}. Today's date is {FIXED_DATE}.")

    return "\n".join(parts)


def _load_and_format_inventory(inventory_file: str, base_dir: str) -> str:
    """Load inventory YAML and format as HA-style entity context.

    Matches the YAML-like format from HA's entity serialization:
      entity_id:
        names: Friendly Name
        state: 'current_state'
        areas: Area Name
        attributes:
          key: value
    """
    full_path = str((Path(base_dir) / inventory_file).resolve())

    if full_path in _inventory_cache:
        return _inventory_cache[full_path]

    with open(full_path) as f:
        inventory = yaml.safe_load(f)

    area_names: dict[str, str] = {}
    for area in inventory.get("areas", []):
        area_names[area["id"]] = area["name"]

    lines = []
    for entity in inventory.get("entities", []):
        lines.append(f"{entity['entity_id']}:")
        lines.append(f"  names: {entity['name']}")
        lines.append(f"  state: '{entity.get('state', 'unknown')}'")

        area_id = entity.get("area")
        if area_id and area_id in area_names:
            lines.append(f"  areas: {area_names[area_id]}")

        attrs = entity.get("attributes", {})
        if attrs:
            lines.append("  attributes:")
            for key, value in attrs.items():
                if value is not None:
                    lines.append(f"    {key}: {value}")
                else:
                    lines.append(f"    {key}:")

    formatted = "\n".join(lines)
    _inventory_cache[full_path] = formatted
    return formatted


def clear_inventory_cache() -> None:
    """Clear the cached inventories (useful for testing)."""
    _inventory_cache.clear()
