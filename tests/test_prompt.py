"""Tests for prompt assembly."""

from pathlib import Path

from ha_voice_bench.prompt import (
    DEFAULT_INSTRUCTIONS,
    FIXED_DATE,
    FIXED_TIME,
    build_system_prompt,
    clear_inventory_cache,
)

REPO_ROOT = Path(__file__).parent.parent
SAMPLE_DATA = REPO_ROOT / "sample_test_data"


def setup_function():
    clear_inventory_cache()


def test_prompt_contains_instructions():
    prompt = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    assert "voice assistant for Home Assistant" in prompt


def test_prompt_contains_entity_context():
    prompt = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    assert "An overview of the areas" in prompt


def test_prompt_contains_timestamp():
    prompt = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    assert FIXED_TIME in prompt
    assert FIXED_DATE in prompt


def test_prompt_timestamp_at_end():
    """Timestamp should be the last section (cache-friendly)."""
    prompt = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    last_line = prompt.strip().split("\n")[-1]
    assert "current time" in last_line.lower() or "date" in last_line.lower()


def test_prompt_no_timestamp():
    prompt = build_system_prompt(
        "sample_test_data/sample_inventory.yaml",
        base_dir=".",
        include_timestamp=False,
    )
    assert FIXED_TIME not in prompt


def test_entity_format_matches_ha():
    """Entities should be formatted in HA's YAML-like style."""
    prompt = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    assert "names:" in prompt
    assert "state:" in prompt


def test_inventory_caching():
    """Loading same inventory twice should use cache."""
    p1 = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    p2 = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    assert p1 == p2


def test_instructions_ordering():
    """Static instructions must appear before entity context (cache-friendly)."""
    prompt = build_system_prompt("sample_test_data/sample_inventory.yaml", base_dir=".")
    instr_pos = prompt.find("voice assistant for Home Assistant")
    entity_pos = prompt.find("An overview of the areas")
    assert instr_pos < entity_pos
