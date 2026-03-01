"""Tests for HA intent tool definitions."""

import pytest

from ha_voice_bench.tools import FULL_TOOLS, MVP_TOOLS, get_ha_intent_tools


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
    """HassLightSet has domain but not device_class (ServiceIntentHandler, no device_classes set)."""
    tool = next(t for t in MVP_TOOLS if t.name == "HassLightSet")
    assert "device_class" not in tool.parameters.properties
    assert "domain" in tool.parameters.properties


def test_climate_set_has_temperature():
    tool = next(t for t in MVP_TOOLS if t.name == "HassClimateSetTemperature")
    assert "temperature" in tool.parameters.properties


def test_invalid_tier_raises():
    with pytest.raises(ValueError):
        get_ha_intent_tools("nonexistent")


# --- Full tier ---


def test_full_tool_count():
    tools = get_ha_intent_tools("full")
    assert len(tools) == 31


def test_full_tools_exported():
    assert len(FULL_TOOLS) == 31


def test_full_includes_mvp():
    mvp_names = {t.name for t in MVP_TOOLS}
    full_names = {t.name for t in FULL_TOOLS}
    assert mvp_names <= full_names


def test_full_tools_all_have_names_and_descriptions():
    for tool in FULL_TOOLS:
        assert tool.name is not None and tool.name.startswith("Hass")
        assert tool.description is not None and len(tool.description) > 0


def test_full_tier_media_tools_present():
    full_names = {t.name for t in FULL_TOOLS}
    for name in ("HassMediaPause", "HassMediaUnpause", "HassMediaNext", "HassMediaPrevious",
                 "HassSetVolume", "HassMediaPlayerMute", "HassMediaPlayerUnmute",
                 "HassSetVolumeRelative", "HassMediaSearchAndPlay"):
        assert name in full_names, f"{name} missing from FULL_TOOLS"


def test_full_tier_household_tools_present():
    full_names = {t.name for t in FULL_TOOLS}
    for name in ("HassFanSetSpeed", "HassVacuumStart", "HassVacuumReturnToBase",
                 "HassLawnMowerStartMowing", "HassLawnMowerDock",
                 "HassListAddItem", "HassListCompleteItem",
                 "HassShoppingListAddItem", "HassShoppingListCompleteItem"):
        assert name in full_names, f"{name} missing from FULL_TOOLS"


def test_full_tier_utility_additions_present():
    full_names = {t.name for t in FULL_TOOLS}
    assert "HassRespond" in full_names
    assert "HassBroadcast" in full_names


def test_set_volume_has_volume_level():
    tool = next(t for t in FULL_TOOLS if t.name == "HassSetVolume")
    assert "volume_level" in tool.parameters.properties


def test_media_search_has_search_query():
    tool = next(t for t in FULL_TOOLS if t.name == "HassMediaSearchAndPlay")
    assert "search_query" in tool.parameters.properties


def test_fan_set_speed_has_percentage():
    tool = next(t for t in FULL_TOOLS if t.name == "HassFanSetSpeed")
    assert "percentage" in tool.parameters.properties


def test_list_add_item_has_item_and_name():
    tool = next(t for t in FULL_TOOLS if t.name == "HassListAddItem")
    assert "item" in tool.parameters.properties
    assert "name" in tool.parameters.properties


def test_no_duplicate_tool_names():
    names = [t.name for t in FULL_TOOLS]
    assert len(names) == len(set(names)), "Duplicate tool names in FULL_TOOLS"
