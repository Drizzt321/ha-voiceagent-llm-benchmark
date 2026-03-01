"""HA intent tool definitions for Inspect AI.

Defines ToolDef objects matching HA's _format_tool() output format.
These are registered via use_tools() so the model sees them in the API request,
but generate(tool_calls="none") means they're never executed.

Tool inventory sourced from:
  https://developers.home-assistant.io/docs/intent_builtin/

Note: parameters are passed as ToolParams (not plain dicts) so ToolDef skips
function-signature introspection — required because _noop uses **kwargs.

Tiers:
  mvp  — 7 core + 4 utility = 11 tools  (Milestone 1)
  full — mvp + Tier 2 media (9) + Tier 3 household (9) + Tier 5 utility (2) = 31 tools
"""

from inspect_ai.tool import ToolDef
from inspect_ai.tool._tool_params import ToolParams
from inspect_ai.util._json import JSONSchema


def _make_noop():
    """Return a unique async no-op per call.

    Inspect's tool registry keys entries by the handler function object.
    Sharing a single _noop across all ToolDefs causes every tool to overwrite
    the previous one — the last definition wins. Creating a new closure per
    tool gives each a distinct identity in the registry.
    """
    async def _noop(**kwargs):
        return "OK"
    return _noop


def _str(description: str) -> JSONSchema:
    return JSONSchema(type="string", description=description)


def _int(description: str) -> JSONSchema:
    return JSONSchema(type="integer", description=description)


def _num(description: str) -> JSONSchema:
    return JSONSchema(type="number", description=description)


def _str_array(description: str) -> JSONSchema:
    return JSONSchema(type="array", items=JSONSchema(type="string"), description=description)


# --- Common entity slots (reused across tools) ---

_ENTITY_SLOTS = ToolParams(
    properties={
        "name": _str("Name of the entity"),
        "area": _str("Name of the area"),
        "floor": _str("Name of the floor"),
        "domain": _str_array("Domain of the entity"),
        "device_class": _str_array("Device class of the entity"),
    }
)


# --- Core Device Control Tools ---

HASS_TURN_ON = ToolDef(
    tool=_make_noop(),
    name="HassTurnOn",
    description="Turns on/opens a device or entity",
    parameters=_ENTITY_SLOTS,
)

HASS_TURN_OFF = ToolDef(
    tool=_make_noop(),
    name="HassTurnOff",
    description="Turns off/closes a device or entity",
    parameters=_ENTITY_SLOTS,
)

HASS_LIGHT_SET = ToolDef(
    tool=_make_noop(),
    name="HassLightSet",
    description="Sets the brightness or color of a light",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "brightness": _int("Brightness percentage from 0 to 100"),
            "color": _str("Name of color"),
        }
    ),
)

HASS_SET_POSITION = ToolDef(
    tool=_make_noop(),
    name="HassSetPosition",
    description="Sets the position of an entity",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "device_class": _str_array("Device class of the entity"),
            "position": _int("Position from 0 to 100"),
        }
    ),
)

HASS_GET_STATE = ToolDef(
    tool=_make_noop(),
    name="HassGetState",
    description="Gets or checks the state of an entity",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "device_class": _str_array("Device class of the entity"),
            "state": _str("Name of state to match"),
        }
    ),
)

HASS_CLIMATE_SET_TEMPERATURE = ToolDef(
    tool=_make_noop(),
    name="HassClimateSetTemperature",
    description="Sets the desired indoor temperature",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "temperature": _num("Temperature in degrees"),
        }
    ),
)

HASS_CLIMATE_GET_TEMPERATURE = ToolDef(
    tool=_make_noop(),
    name="HassClimateGetTemperature",
    description="Gets the actual indoor temperature",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
        }
    ),
)


# --- Utility Intents ---

HASS_GET_CURRENT_TIME = ToolDef(
    tool=_make_noop(),
    name="HassGetCurrentTime",
    description="Gets the current time",
    parameters=ToolParams(),
)

HASS_GET_CURRENT_DATE = ToolDef(
    tool=_make_noop(),
    name="HassGetCurrentDate",
    description="Gets the current date",
    parameters=ToolParams(),
)

HASS_GET_WEATHER = ToolDef(
    tool=_make_noop(),
    name="HassGetWeather",
    description="Gets the current weather",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the weather entity"),
        }
    ),
)

HASS_NEVERMIND = ToolDef(
    tool=_make_noop(),
    name="HassNevermind",
    description="Cancels the current request",
    parameters=ToolParams(),
)


# --- Tier 2: Media Control ---

_MEDIA_SLOTS = ToolParams(
    properties={
        "name": _str("Name of the media player"),
        "area": _str("Name of the area"),
    }
)

HASS_MEDIA_PAUSE = ToolDef(
    tool=_make_noop(),
    name="HassMediaPause",
    description="Pauses a media player",
    parameters=_MEDIA_SLOTS,
)

HASS_MEDIA_UNPAUSE = ToolDef(
    tool=_make_noop(),
    name="HassMediaUnpause",
    description="Unpauses a media player",
    parameters=_MEDIA_SLOTS,
)

HASS_MEDIA_NEXT = ToolDef(
    tool=_make_noop(),
    name="HassMediaNext",
    description="Skips to the next item on a media player",
    parameters=_MEDIA_SLOTS,
)

HASS_MEDIA_PREVIOUS = ToolDef(
    tool=_make_noop(),
    name="HassMediaPrevious",
    description="Skips to the previous item on a media player",
    parameters=_MEDIA_SLOTS,
)

HASS_SET_VOLUME = ToolDef(
    tool=_make_noop(),
    name="HassSetVolume",
    description="Sets the volume of a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the media player"),
            "area": _str("Name of the area"),
            "volume_level": _int("Volume level from 0 to 100"),
        }
    ),
)

HASS_MEDIA_PLAYER_MUTE = ToolDef(
    tool=_make_noop(),
    name="HassMediaPlayerMute",
    description="Mutes a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the media player"),
        }
    ),
)

HASS_MEDIA_PLAYER_UNMUTE = ToolDef(
    tool=_make_noop(),
    name="HassMediaPlayerUnmute",
    description="Unmutes a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the media player"),
        }
    ),
)

HASS_SET_VOLUME_RELATIVE = ToolDef(
    tool=_make_noop(),
    name="HassSetVolumeRelative",
    description="Increases or decreases the volume of a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the media player"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "volume_step": _int("Volume step from -100 to 100 (negative to decrease)"),
        }
    ),
)

HASS_MEDIA_SEARCH_AND_PLAY = ToolDef(
    tool=_make_noop(),
    name="HassMediaSearchAndPlay",
    description="Searches for and plays media on a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the media player"),
            "area": _str("Name of the area"),
            "search_query": _str("Search query for the media to play"),
            "media_class": _str("Type of media (album, artist, track, playlist, etc.)"),
        }
    ),
)


# --- Tier 3: Household ---

HASS_FAN_SET_SPEED = ToolDef(
    tool=_make_noop(),
    name="HassFanSetSpeed",
    description="Sets the speed of a fan",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the fan"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "percentage": _int("Fan speed percentage from 0 to 100"),
        }
    ),
)

HASS_VACUUM_START = ToolDef(
    tool=_make_noop(),
    name="HassVacuumStart",
    description="Starts a vacuum cleaner",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the vacuum"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
        }
    ),
)

HASS_VACUUM_RETURN_TO_BASE = ToolDef(
    tool=_make_noop(),
    name="HassVacuumReturnToBase",
    description="Returns a vacuum cleaner to its base",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the vacuum"),
            "area": _str("Name of the area"),
        }
    ),
)

HASS_LAWN_MOWER_START_MOWING = ToolDef(
    tool=_make_noop(),
    name="HassLawnMowerStartMowing",
    description="Starts a lawn mower",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the lawn mower"),
        }
    ),
)

HASS_LAWN_MOWER_DOCK = ToolDef(
    tool=_make_noop(),
    name="HassLawnMowerDock",
    description="Sends a lawn mower to its dock",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the lawn mower"),
        }
    ),
)

HASS_LIST_ADD_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassListAddItem",
    description="Adds an item to a todo list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to add to the list"),
            "name": _str("Name of the todo list"),
        }
    ),
)

HASS_LIST_COMPLETE_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassListCompleteItem",
    description="Checks off an item on a todo list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to check off"),
            "name": _str("Name of the todo list"),
        }
    ),
)

HASS_SHOPPING_LIST_ADD_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassShoppingListAddItem",
    description="Adds an item to the shopping list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to add to the shopping list"),
        }
    ),
)

HASS_SHOPPING_LIST_COMPLETE_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassShoppingListCompleteItem",
    description="Checks off an item on the shopping list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to check off"),
        }
    ),
)


# --- Tier 5: Additional Utility ---

HASS_RESPOND = ToolDef(
    tool=_make_noop(),
    name="HassRespond",
    description="Returns a response to the user without taking any action",
    parameters=ToolParams(
        properties={
            "response": _str("The response text to return"),
        }
    ),
)

HASS_BROADCAST = ToolDef(
    tool=_make_noop(),
    name="HassBroadcast",
    description="Announces a message on other voice satellites",
    parameters=ToolParams(
        properties={
            "message": _str("The message to broadcast"),
        }
    ),
)


# --- Public API ---

MVP_TOOLS = [
    HASS_TURN_ON,
    HASS_TURN_OFF,
    HASS_LIGHT_SET,
    HASS_SET_POSITION,
    HASS_GET_STATE,
    HASS_CLIMATE_SET_TEMPERATURE,
    HASS_CLIMATE_GET_TEMPERATURE,
    HASS_GET_CURRENT_TIME,
    HASS_GET_CURRENT_DATE,
    HASS_GET_WEATHER,
    HASS_NEVERMIND,
]

FULL_TOOLS = MVP_TOOLS + [
    # Tier 2: Media
    HASS_MEDIA_PAUSE,
    HASS_MEDIA_UNPAUSE,
    HASS_MEDIA_NEXT,
    HASS_MEDIA_PREVIOUS,
    HASS_SET_VOLUME,
    HASS_MEDIA_PLAYER_MUTE,
    HASS_MEDIA_PLAYER_UNMUTE,
    HASS_SET_VOLUME_RELATIVE,
    HASS_MEDIA_SEARCH_AND_PLAY,
    # Tier 3: Household
    HASS_FAN_SET_SPEED,
    HASS_VACUUM_START,
    HASS_VACUUM_RETURN_TO_BASE,
    HASS_LAWN_MOWER_START_MOWING,
    HASS_LAWN_MOWER_DOCK,
    HASS_LIST_ADD_ITEM,
    HASS_LIST_COMPLETE_ITEM,
    HASS_SHOPPING_LIST_ADD_ITEM,
    HASS_SHOPPING_LIST_COMPLETE_ITEM,
    # Tier 5: Additional utility
    HASS_RESPOND,
    HASS_BROADCAST,
]


def get_ha_intent_tools(tier: str = "mvp") -> list[ToolDef]:
    """Return HA intent tools for the benchmarking eval.

    Args:
        tier: Which tool set — 'mvp' (11 tools) or 'full' (31 tools).
    """
    if tier == "mvp":
        return list(MVP_TOOLS)
    if tier == "full":
        return list(FULL_TOOLS)
    raise ValueError(f"Unknown tool tier: {tier}")
