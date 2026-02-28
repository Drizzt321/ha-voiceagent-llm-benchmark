"""Tests for HA intent tool definitions."""

import pytest

from ha_voice_bench.tools import MVP_TOOLS, get_ha_intent_tools


def test_mvp_tool_count():
    tools = get_ha_intent_tools("mvp")
    assert len(tools) == 11


def test_all_tools_have_names():
    for tool in MVP_TOOLS:
        assert tool.name is not None
        assert tool.name.startswith("Hass")


def test_all_tools_have_descriptions():
    for tool in MVP_TOOLS:
        assert tool.description is not None
        assert len(tool.description) > 0


def test_turn_on_has_entity_slots():
    tool = next(t for t in MVP_TOOLS if t.name == "HassTurnOn")
    param_names = set(tool.parameters.properties.keys())
    assert {"name", "area", "domain"} <= param_names


def test_light_set_has_brightness():
    tool = next(t for t in MVP_TOOLS if t.name == "HassLightSet")
    assert "brightness" in tool.parameters.properties


def test_light_set_no_device_class():
    """HassLightSet doesn't have domain/device_class slots."""
    tool = next(t for t in MVP_TOOLS if t.name == "HassLightSet")
    assert "device_class" not in tool.parameters.properties
    assert "domain" not in tool.parameters.properties


def test_climate_set_has_temperature():
    tool = next(t for t in MVP_TOOLS if t.name == "HassClimateSetTemperature")
    assert "temperature" in tool.parameters.properties


def test_invalid_tier_raises():
    with pytest.raises(ValueError):
        get_ha_intent_tools("nonexistent")
