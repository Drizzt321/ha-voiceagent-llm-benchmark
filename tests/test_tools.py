"""Tests for HA intent tool definitions."""

from ha_voice_bench.tools import ALL_TOOLS, get_ha_intent_tools


def test_tool_count():
    assert len(get_ha_intent_tools()) == 32


def test_all_tools_exported():
    assert len(ALL_TOOLS) == 32


def test_all_tools_have_names():
    for tool in ALL_TOOLS:
        assert tool.name is not None
        assert tool.name.startswith("Hass")


def test_all_tools_have_descriptions():
    for tool in ALL_TOOLS:
        assert tool.description is not None
        assert len(tool.description) > 0


def test_no_duplicate_tool_names():
    names = [t.name for t in ALL_TOOLS]
    assert len(names) == len(set(names)), "Duplicate tool names in ALL_TOOLS"


def test_toggle_present():
    names = {t.name for t in ALL_TOOLS}
    assert "HassToggle" in names


def test_toggle_has_entity_slots():
    tool = next(t for t in ALL_TOOLS if t.name == "HassToggle")
    assert {"name", "area", "domain"} <= set(tool.parameters.properties.keys())


def test_turn_on_has_entity_slots():
    tool = next(t for t in ALL_TOOLS if t.name == "HassTurnOn")
    assert {"name", "area", "domain"} <= set(tool.parameters.properties.keys())


def test_light_set_has_brightness():
    tool = next(t for t in ALL_TOOLS if t.name == "HassLightSet")
    assert "brightness" in tool.parameters.properties


def test_light_set_no_device_class():
    """HassLightSet has domain but not device_class (ServiceIntentHandler, no device_classes set)."""
    tool = next(t for t in ALL_TOOLS if t.name == "HassLightSet")
    assert "device_class" not in tool.parameters.properties
    assert "domain" in tool.parameters.properties


def test_climate_set_has_temperature():
    tool = next(t for t in ALL_TOOLS if t.name == "HassClimateSetTemperature")
    assert "temperature" in tool.parameters.properties


def test_media_tools_present():
    names = {t.name for t in ALL_TOOLS}
    for name in ("HassMediaPause", "HassMediaUnpause", "HassMediaNext", "HassMediaPrevious",
                 "HassSetVolume", "HassMediaPlayerMute", "HassMediaPlayerUnmute",
                 "HassSetVolumeRelative", "HassMediaSearchAndPlay"):
        assert name in names, f"{name} missing from ALL_TOOLS"


def test_household_tools_present():
    names = {t.name for t in ALL_TOOLS}
    for name in ("HassFanSetSpeed", "HassVacuumStart", "HassVacuumReturnToBase",
                 "HassLawnMowerStartMowing", "HassLawnMowerDock",
                 "HassListAddItem", "HassListCompleteItem",
                 "HassShoppingListAddItem", "HassShoppingListCompleteItem"):
        assert name in names, f"{name} missing from ALL_TOOLS"


def test_utility_tools_present():
    names = {t.name for t in ALL_TOOLS}
    assert "HassRespond" in names
    assert "HassBroadcast" in names


def test_set_volume_has_volume_level():
    tool = next(t for t in ALL_TOOLS if t.name == "HassSetVolume")
    assert "volume_level" in tool.parameters.properties


def test_media_search_has_search_query():
    tool = next(t for t in ALL_TOOLS if t.name == "HassMediaSearchAndPlay")
    assert "search_query" in tool.parameters.properties


def test_fan_set_speed_has_percentage():
    tool = next(t for t in ALL_TOOLS if t.name == "HassFanSetSpeed")
    assert "percentage" in tool.parameters.properties


def test_list_add_item_has_item_and_name():
    tool = next(t for t in ALL_TOOLS if t.name == "HassListAddItem")
    assert "item" in tool.parameters.properties
    assert "name" in tool.parameters.properties
