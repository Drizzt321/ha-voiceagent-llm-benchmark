"""HA intent tool definitions for Inspect AI.

Defines ToolDef objects matching HA's _format_tool() output format.
These are registered via use_tools() so the model sees them in the API request,
but generate(tool_calls="none") means they're never executed.

Verified against HA core release 2026.2.3
(commit 9c640fe0fa008d6e80aa4cc88c9c1734605fb3e0).

Slot schemas derived from homeassistant/helpers/intent.py (ServiceIntentHandler,
DynamicServiceIntentHandler) and per-component intent.py files.

Mapping conventions:
- vol.Any("name", "area", "floor") key in HA schemas → all three listed as
  optional here; HA enforces "at least one required" at runtime, which cannot
  be expressed cleanly in JSON Schema.
- preferred_area_id / preferred_floor_id slots are internal system slots
  filled by HA's conversation layer; not exposed to the LLM.
- HassMediaPlayerMute/Unmute: is_volume_muted slot is set by the handler, not
  the LLM; not exposed here.
- ServiceIntentHandler with device_classes set → device_class slot present.
- ServiceIntentHandler without device_classes → no device_class slot.

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


# --- Common entity slot sets ---

# Full entity targeting: used by ServiceIntentHandler with device_classes set.
# Covers HassTurnOn/Off and media player service tools.
_ENTITY_SLOTS = ToolParams(
    properties={
        "name": _str("Name of the entity"),
        "area": _str("Name of the area"),
        "floor": _str("Name of the floor"),
        "domain": _str_array("Domain of the entity"),
        "device_class": _str_array("Device class of the entity"),
    }
)

# Service entity targeting: used by ServiceIntentHandler without device_classes.
# Covers fan, vacuum, lawn_mower tools.
_SERVICE_SLOTS = ToolParams(
    properties={
        "name": _str("Name of the entity"),
        "area": _str("Name of the area"),
        "floor": _str("Name of the floor"),
        "domain": _str_array("Domain of the entity"),
    }
)


# --- Core Device Control Tools ---

HASS_TURN_ON = ToolDef(
    tool=_make_noop(),
    name="HassTurnOn",
    description=(
        "Turns on/opens/presses a device or entity. For locks, this performs a 'lock' "
        "action. Use for requests like 'turn on', 'activate', 'enable', or 'lock'."
    ),
    parameters=_ENTITY_SLOTS,
)

HASS_TURN_OFF = ToolDef(
    tool=_make_noop(),
    name="HassTurnOff",
    description=(
        "Turns off/closes a device or entity. For locks, this performs an 'unlock' "
        "action. Use for requests like 'turn off', 'deactivate', 'disable', or 'unlock'."
    ),
    parameters=_ENTITY_SLOTS,
)

HASS_LIGHT_SET = ToolDef(
    tool=_make_noop(),
    name="HassLightSet",
    description="Sets the brightness percentage or color of a light",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "brightness": _int(
                "The brightness percentage of the light between 0 and 100, "
                "where 0 is off and 100 is fully lit"
            ),
            "color": _str("Name of color"),
            "temperature": _int("Color temperature in Kelvin"),
        }
    ),
)

HASS_SET_POSITION = ToolDef(
    tool=_make_noop(),
    name="HassSetPosition",
    description="Sets the position of a device or entity",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "device_class": _str_array("Device class of the entity"),
            "position": _int("Position from 0 to 100"),
        },
        required=["position"],
    ),
)

HASS_GET_STATE = ToolDef(
    tool=_make_noop(),
    name="HassGetState",
    description="Gets or checks the state of a device or entity",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "device_class": _str_array("Device class of the entity"),
            "state": _str_array("State or states to match"),
        }
    ),
)

HASS_CLIMATE_SET_TEMPERATURE = ToolDef(
    tool=_make_noop(),
    name="HassClimateSetTemperature",
    description="Sets the target temperature of a climate device or entity",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "temperature": _num("Temperature in degrees"),
        },
        required=["temperature"],
    ),
)

HASS_CLIMATE_GET_TEMPERATURE = ToolDef(
    tool=_make_noop(),
    name="HassClimateGetTemperature",
    description="Gets the current temperature of a climate device or entity",
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
    description="Cancels the current request and does nothing",
    parameters=ToolParams(),
)


# --- Tier 2: Media Control ---

# HassMediaPause/Unpause/Next/Previous/SetVolume/Mute/Unmute are registered via
# ServiceIntentHandler with device_classes={MediaPlayerDeviceClass}, giving the
# full entity targeting schema (name, area, floor, domain, device_class).

HASS_MEDIA_PAUSE = ToolDef(
    tool=_make_noop(),
    name="HassMediaPause",
    description="Pauses a media player",
    parameters=_ENTITY_SLOTS,
)

HASS_MEDIA_UNPAUSE = ToolDef(
    tool=_make_noop(),
    name="HassMediaUnpause",
    description="Resumes a media player",
    parameters=_ENTITY_SLOTS,
)

HASS_MEDIA_NEXT = ToolDef(
    tool=_make_noop(),
    name="HassMediaNext",
    description="Skips a media player to the next item",
    parameters=_ENTITY_SLOTS,
)

HASS_MEDIA_PREVIOUS = ToolDef(
    tool=_make_noop(),
    name="HassMediaPrevious",
    description="Replays the previous item for a media player",
    parameters=_ENTITY_SLOTS,
)

HASS_SET_VOLUME = ToolDef(
    tool=_make_noop(),
    name="HassSetVolume",
    description="Sets the volume percentage of a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "device_class": _str_array("Device class of the entity"),
            "volume_level": _int("The volume percentage of the media player"),
        },
        required=["volume_level"],
    ),
)

HASS_MEDIA_PLAYER_MUTE = ToolDef(
    tool=_make_noop(),
    name="HassMediaPlayerMute",
    description="Mutes a media player",
    parameters=_ENTITY_SLOTS,
)

HASS_MEDIA_PLAYER_UNMUTE = ToolDef(
    tool=_make_noop(),
    name="HassMediaPlayerUnmute",
    description="Unmutes a media player",
    parameters=_ENTITY_SLOTS,
)

# HassSetVolumeRelative uses a custom handler (not ServiceIntentHandler) with its
# own slot_schema: name/area/floor for targeting (no domain/device_class) and
# volume_step as a required union of "up"/"down" strings or an integer percentage.
HASS_SET_VOLUME_RELATIVE = ToolDef(
    tool=_make_noop(),
    name="HassSetVolumeRelative",
    description="Increases or decreases the volume of a media player",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "volume_step": JSONSchema(
                anyOf=[
                    JSONSchema(type="string", enum=["up", "down"]),
                    JSONSchema(type="integer"),
                ],
                description="Volume change: 'up', 'down', or a percentage from -100 to 100",
            ),
        },
        required=["volume_step"],
    ),
)

# HassMediaSearchAndPlay uses a custom handler with its own slot_schema:
# name/area/floor for targeting (no domain/device_class), search_query required,
# media_class optional with fixed enum values from MediaClass.
HASS_MEDIA_SEARCH_AND_PLAY = ToolDef(
    tool=_make_noop(),
    name="HassMediaSearchAndPlay",
    description="Searches for media and plays the first result",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "search_query": _str("Search query for the media to play"),
            "media_class": JSONSchema(
                type="string",
                enum=[
                    "album", "app", "artist", "channel", "composer",
                    "contributing_artist", "directory", "episode", "game",
                    "genre", "image", "movie", "music", "playlist", "podcast",
                    "season", "track", "tv_show", "url", "video",
                ],
                description="Type of media",
            ),
        },
        required=["search_query"],
    ),
)


# --- Tier 3: Household ---

# HassFanSetSpeed, HassVacuumStart/ReturnToBase, HassLawnMowerStartMowing/Dock
# are all registered via ServiceIntentHandler without device_classes, giving
# the service targeting schema: name, area, floor, domain.

HASS_FAN_SET_SPEED = ToolDef(
    tool=_make_noop(),
    name="HassFanSetSpeed",
    description="Sets a fan's speed by percentage",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the entity"),
            "area": _str("Name of the area"),
            "floor": _str("Name of the floor"),
            "domain": _str_array("Domain of the entity"),
            "percentage": _int("The speed percentage of the fan"),
        },
        required=["percentage"],
    ),
)

HASS_VACUUM_START = ToolDef(
    tool=_make_noop(),
    name="HassVacuumStart",
    description="Starts a vacuum",
    parameters=_SERVICE_SLOTS,
)

HASS_VACUUM_RETURN_TO_BASE = ToolDef(
    tool=_make_noop(),
    name="HassVacuumReturnToBase",
    description="Returns a vacuum to base",
    parameters=_SERVICE_SLOTS,
)

HASS_LAWN_MOWER_START_MOWING = ToolDef(
    tool=_make_noop(),
    name="HassLawnMowerStartMowing",
    description="Starts a lawn mower",
    parameters=_SERVICE_SLOTS,
)

HASS_LAWN_MOWER_DOCK = ToolDef(
    tool=_make_noop(),
    name="HassLawnMowerDock",
    description="Sends a lawn mower to dock",
    parameters=_SERVICE_SLOTS,
)

# HassListAddItem/CompleteItem: custom handlers with item and name both required.
HASS_LIST_ADD_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassListAddItem",
    description="Add item to a todo list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to add to the list"),
            "name": _str("Name of the todo list"),
        },
        required=["item", "name"],
    ),
)

HASS_LIST_COMPLETE_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassListCompleteItem",
    description="Complete item on a todo list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to check off"),
            "name": _str("Name of the todo list"),
        },
        required=["item", "name"],
    ),
)

# HassShoppingListAddItem/CompleteItem: custom handlers, item required (bare key
# in voluptuous schema = vol.Required by default).
HASS_SHOPPING_LIST_ADD_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassShoppingListAddItem",
    description="Adds an item to the shopping list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to add to the shopping list"),
        },
        required=["item"],
    ),
)

HASS_SHOPPING_LIST_COMPLETE_ITEM = ToolDef(
    tool=_make_noop(),
    name="HassShoppingListCompleteItem",
    description="Marks an item as completed on the shopping list",
    parameters=ToolParams(
        properties={
            "item": _str("The item to mark as completed"),
        },
        required=["item"],
    ),
)


# --- Tier 5: Additional Utility ---

HASS_RESPOND = ToolDef(
    tool=_make_noop(),
    name="HassRespond",
    description="Returns the provided response with no action.",
    parameters=ToolParams(
        properties={
            "response": _str("The response text to return"),
        }
    ),
)

HASS_BROADCAST = ToolDef(
    tool=_make_noop(),
    name="HassBroadcast",
    description="Broadcast a message through the home",
    parameters=ToolParams(
        properties={
            "message": _str("The message to broadcast"),
        },
        required=["message"],
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
