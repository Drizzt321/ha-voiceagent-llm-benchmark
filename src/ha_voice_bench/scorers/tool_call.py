"""Tier 1 Scorer: Tool-call validation for HA voice benchmarking.

Compares the model's actual tool calls against expected tool calls
from the test case target. Produces multi-dimensional scores.
"""

import json
import logging
from typing import Any

from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState

logger = logging.getLogger(__name__)

# Valid HA intent tool names (MVP set: 7 core + 4 utility = 11)
VALID_TOOL_NAMES = {
    "HassTurnOn",
    "HassTurnOff",
    "HassLightSet",
    "HassSetPosition",
    "HassGetState",
    "HassClimateSetTemperature",
    "HassClimateGetTemperature",
    "HassGetCurrentTime",
    "HassGetCurrentDate",
    "HassGetWeather",
    "HassNevermind",
}

C = "C"  # Correct
I = "I"  # Incorrect
N = "N"  # Not applicable


@scorer(metrics=[accuracy()])
def tool_call_scorer() -> Scorer:
    """Score model tool calls against expected tool calls."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            expected_calls = json.loads(target.text)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Could not parse target: %s", target.text)
            return _error_score("Target parse error")

        actual_calls = _extract_tool_calls(state)
        expected_type = state.metadata.get("expected_response_type", "action_done")

        results = _score_dimensions(expected_calls, actual_calls, expected_type)
        applicable = {k: v for k, v in results.items() if v != N}
        overall = C if all(v == C for v in applicable.values()) else I

        # If primary fails, try each alternative expected call set.
        match_quality = "optimal"
        match_reason = ""
        if overall == I:
            raw = state.metadata.get("alternative_expected_tool_calls", [])
            alternatives: list[dict | list] = json.loads(raw) if isinstance(raw, str) else raw
            for alt in alternatives:
                if isinstance(alt, dict):
                    alt_calls: list[dict] = alt.get("tool_calls", [])
                    alt_quality: str = alt.get("quality", "acceptable")
                    alt_reason: str = alt.get("reason", "")
                else:
                    # Legacy flat-array format
                    alt_calls = alt
                    alt_quality = "acceptable"
                    alt_reason = ""
                alt_results = _score_dimensions(alt_calls, actual_calls, expected_type)
                alt_applicable = {k: v for k, v in alt_results.items() if v != N}
                if all(v == C for v in alt_applicable.values()):
                    overall = C
                    results = alt_results
                    match_quality = alt_quality
                    match_reason = alt_reason
                    break

        explanation = _build_explanation(expected_calls, actual_calls, results, match_quality, match_reason)

        return Score(
            value=overall,
            answer=json.dumps(_serialize_actual_calls(actual_calls)),
            explanation=explanation,
        )

    return score


def _score_dimensions(
    expected_calls: list[dict],
    actual_calls: list[dict],
    expected_type: str,
) -> dict[str, str]:
    """Run all dimension checks and return a results dict."""
    return {
        "response_type": _check_response_type(expected_type, expected_calls, actual_calls),
        "format_valid": _check_format_validity(actual_calls),
        "call_count": _check_call_count(expected_calls, actual_calls),
        "tool_name": _check_tool_names(expected_calls, actual_calls),
        "args": _check_arguments(expected_calls, actual_calls),
        "no_hallucinated_tools": _check_no_hallucinated_tools(actual_calls),
    }


def _extract_tool_calls(state: TaskState) -> list[dict]:
    """Extract tool calls from the model's response.

    Returns list of dicts with 'name' and 'arguments' keys.
    """
    # Primary: last assistant message in conversation
    if state.messages:
        last_msg = state.messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return [_tc_to_dict(tc) for tc in last_msg.tool_calls]

    # Fallback: state.output.choices (in case messages don't carry tool_calls)
    if state.output and state.output.choices:
        msg = state.output.choices[0].message
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            return [_tc_to_dict(tc) for tc in msg.tool_calls]

    return []


def _tc_to_dict(tc: Any) -> dict:
    """Convert an Inspect ToolCall to our internal {name, arguments} dict."""
    args = tc.arguments if isinstance(tc.arguments, dict) else {}
    if getattr(tc, "parse_error", None):
        args = {"_raw": str(tc.arguments)}
    return {"name": tc.function, "arguments": args}


def _check_response_type(
    expected_type: str,
    expected_calls: list[dict],
    actual_calls: list[dict],
) -> str:
    """Check if the model's response matches the expected response type."""
    if expected_type == "action_done":
        return C if actual_calls else I
    if expected_type == "query_response":
        query_tools = {
            "HassGetState",
            "HassClimateGetTemperature",
            "HassGetWeather",
            "HassGetCurrentTime",
            "HassGetCurrentDate",
        }
        return C if any(c.get("name") in query_tools for c in actual_calls) else I
    if expected_type == "text_response":
        return C if not actual_calls else I
    if expected_type in {"error", "clarification"}:
        return C if not actual_calls else I
    return N


def _check_format_validity(actual_calls: list[dict]) -> str:
    """Check if all tool calls are well-formed."""
    if not actual_calls:
        return N
    for call in actual_calls:
        if not call.get("name"):
            return I
        if "_raw" in call.get("arguments", {}):
            return I
    return C


def _check_call_count(expected_calls: list[dict], actual_calls: list[dict]) -> str:
    """Check if the number of tool calls matches."""
    if not expected_calls and not actual_calls:
        return C
    return C if len(expected_calls) == len(actual_calls) else I


def _check_tool_names(expected_calls: list[dict], actual_calls: list[dict]) -> str:
    """Check if the correct tool(s) were called (order-independent)."""
    if not expected_calls:
        return N
    if not actual_calls:
        return I
    expected_names = sorted(c["name"] for c in expected_calls)
    actual_names = sorted(c.get("name") for c in actual_calls)
    return C if expected_names == actual_names else I


def _check_arguments(expected_calls: list[dict], actual_calls: list[dict]) -> str:
    """Check if arguments match expected values.

    Uses order-independent matching for multi-call cases.
    Supports _any_of suffix for flexible matching.
    """
    if not expected_calls:
        return N
    if len(expected_calls) != len(actual_calls):
        return I

    unmatched = list(range(len(actual_calls)))
    for exp in expected_calls:
        matched = False
        for i in unmatched:
            if _tool_call_matches(exp, actual_calls[i]):
                unmatched.remove(i)
                matched = True
                break
        if not matched:
            return I
    return C


def _tool_call_matches(expected: dict, actual: dict) -> bool:
    """Check if an actual tool call matches an expected one."""
    if expected.get("name") != actual.get("name"):
        return False

    exp_args = expected.get("arguments", {})
    if not exp_args:
        return True

    act_args = actual.get("arguments", {})
    for key, exp_value in exp_args.items():
        if key.endswith("_any_of"):
            base_key = key[:-7]
            act_value = act_args.get(base_key)
            if act_value is None:
                return False
            if isinstance(exp_value, list):
                if not any(_normalize(act_value) == _normalize(v) for v in exp_value):
                    return False
            continue

        act_value = act_args.get(key)
        if act_value is None:
            return False

        if isinstance(exp_value, (int, float)) and isinstance(act_value, (int, float)):
            if abs(exp_value - act_value) > 0.01:
                return False
        elif isinstance(exp_value, list) and isinstance(act_value, list):
            if sorted(str(v).lower() for v in exp_value) != sorted(str(v).lower() for v in act_value):
                return False
        else:
            if _normalize(act_value) != _normalize(exp_value):
                return False

    return True


def _normalize(value: Any) -> str:
    """Normalize a value for case-insensitive string comparison."""
    return str(value).strip().lower()


def _check_no_hallucinated_tools(actual_calls: list[dict]) -> str:
    """Check that only valid HA intent tools were called."""
    if not actual_calls:
        return N
    for call in actual_calls:
        name = call.get("name")
        if name and name not in VALID_TOOL_NAMES:
            return I
    return C


def _serialize_actual_calls(actual_calls: list[dict]) -> list[dict]:
    """Serialize actual calls for the Score.answer field."""
    return [{"name": c.get("name"), "arguments": c.get("arguments", {})} for c in actual_calls]


def _build_explanation(
    expected_calls: list[dict],
    actual_calls: list[dict],
    results: dict[str, str],
    match_quality: str = "optimal",
    match_reason: str = "",
) -> str:
    """Build a human-readable explanation of the scoring."""
    lines = [
        f"MATCH_QUALITY: {match_quality}",
    ]
    if match_reason:
        lines.append(f"MATCH_REASON: {match_reason}")
    lines += [
        f"Expected {len(expected_calls)} call(s):",
        *[f"  {c.get('name', '?')}({c.get('arguments', {})})" for c in expected_calls],
        f"Got {len(actual_calls)} call(s):",
        *[f"  {c.get('name', '?')}({c.get('arguments', {})})" for c in actual_calls],
        "",
        "Checks:",
        *[f"  {'C' if v == C else ('I' if v == I else '-')} {k}: {v}" for k, v in results.items()],
    ]
    return "\n".join(lines)


def _error_score(message: str) -> Score:
    """Return an error score when scoring fails."""
    return Score(
        value=I,
        answer="",
        explanation=f"Scoring error: {message}",
    )
