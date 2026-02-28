"""HA intent tool definitions for Inspect AI.

Defines ToolDef objects matching HA's _format_tool() output format.
These are registered via use_tools() so the model sees them in the API request,
but generate(tool_calls="none") means they're never executed.

Tool inventory sourced from:
  https://developers.home-assistant.io/docs/intent_builtin/

Note: parameters are passed as ToolParams (not plain dicts) so ToolDef skips
function-signature introspection — required because _noop uses **kwargs.
"""

from inspect_ai.tool import ToolDef
from inspect_ai.tool._tool_params import ToolParams
from inspect_ai.util._json import JSONSchema


async def _noop(**kwargs):
    """Dummy handler — never called with tool_calls='none'."""
    return "OK"


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
    tool=_noop,
    name="HassTurnOn",
    description="Turns on/opens a device or entity",
    parameters=_ENTITY_SLOTS,
)

HASS_TURN_OFF = ToolDef(
    tool=_noop,
    name="HassTurnOff",
    description="Turns off/closes a device or entity",
    parameters=_ENTITY_SLOTS,
)

HASS_LIGHT_SET = ToolDef(
    tool=_noop,
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
    tool=_noop,
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
    tool=_noop,
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
    tool=_noop,
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
    tool=_noop,
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
    tool=_noop,
    name="HassGetCurrentTime",
    description="Gets the current time",
    parameters=ToolParams(),
)

HASS_GET_CURRENT_DATE = ToolDef(
    tool=_noop,
    name="HassGetCurrentDate",
    description="Gets the current date",
    parameters=ToolParams(),
)

HASS_GET_WEATHER = ToolDef(
    tool=_noop,
    name="HassGetWeather",
    description="Gets the current weather",
    parameters=ToolParams(
        properties={
            "name": _str("Name of the weather entity"),
        }
    ),
)

HASS_NEVERMIND = ToolDef(
    tool=_noop,
    name="HassNevermind",
    description="Cancels the current request",
    parameters=ToolParams(),
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


def get_ha_intent_tools(tier: str = "mvp") -> list[ToolDef]:
    """Return HA intent tools for the benchmarking eval.

    Args:
        tier: Which tool set — 'mvp' (11 tools) or 'full' (added in Milestone 2).
    """
    if tier == "mvp":
        return list(MVP_TOOLS)
    raise ValueError(f"Unknown tool tier: {tier}")
