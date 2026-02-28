"""Tests for the Tier 1 tool-call scorer."""

from ha_voice_bench.scorers.tool_call import (
    C,
    I,
    N,
    _check_arguments,
    _check_call_count,
    _check_format_validity,
    _check_no_hallucinated_tools,
    _check_response_type,
    _check_tool_names,
    _tool_call_matches,
)


class TestToolNameCheck:
    def test_single_match(self):
        exp = [{"name": "HassTurnOn", "arguments": {}}]
        act = [{"name": "HassTurnOn", "arguments": {}}]
        assert _check_tool_names(exp, act) == C

    def test_single_mismatch(self):
        exp = [{"name": "HassTurnOn", "arguments": {}}]
        act = [{"name": "HassTurnOff", "arguments": {}}]
        assert _check_tool_names(exp, act) == I

    def test_multi_match_order_independent(self):
        exp = [{"name": "HassTurnOff"}, {"name": "HassTurnOn"}]
        act = [{"name": "HassTurnOn"}, {"name": "HassTurnOff"}]
        assert _check_tool_names(exp, act) == C

    def test_no_expected_returns_na(self):
        assert _check_tool_names([], []) == N

    def test_expected_but_none_actual(self):
        exp = [{"name": "HassTurnOn"}]
        assert _check_tool_names(exp, []) == I


class TestArgumentCheck:
    def test_exact_match(self):
        exp = [{"name": "HassTurnOn", "arguments": {"name": "Kitchen Light", "domain": ["light"]}}]
        act = [{"name": "HassTurnOn", "arguments": {"name": "Kitchen Light", "domain": ["light"]}}]
        assert _check_arguments(exp, act) == C

    def test_case_insensitive(self):
        exp = [{"name": "HassTurnOn", "arguments": {"name": "kitchen light"}}]
        act = [{"name": "HassTurnOn", "arguments": {"name": "Kitchen Light"}}]
        assert _check_arguments(exp, act) == C

    def test_any_of_match(self):
        exp = [{"name": "HassTurnOn", "arguments": {"name_any_of": ["Kitchen Light", "Kitchen Ceiling"]}}]
        act = [{"name": "HassTurnOn", "arguments": {"name": "Kitchen Ceiling"}}]
        assert _check_arguments(exp, act) == C

    def test_any_of_miss(self):
        exp = [{"name": "HassTurnOn", "arguments": {"name_any_of": ["Kitchen Light", "Kitchen Ceiling"]}}]
        act = [{"name": "HassTurnOn", "arguments": {"name": "Bedroom Light"}}]
        assert _check_arguments(exp, act) == I

    def test_numeric_match(self):
        exp = [{"name": "HassLightSet", "arguments": {"brightness": 50}}]
        act = [{"name": "HassLightSet", "arguments": {"brightness": 50}}]
        assert _check_arguments(exp, act) == C

    def test_empty_expected_args(self):
        exp = [{"name": "HassTurnOff", "arguments": {}}]
        act = [{"name": "HassTurnOff", "arguments": {"name": "Anything"}}]
        assert _check_arguments(exp, act) == C

    def test_missing_actual_arg(self):
        exp = [{"name": "HassTurnOn", "arguments": {"name": "Light"}}]
        act = [{"name": "HassTurnOn", "arguments": {}}]
        assert _check_arguments(exp, act) == I

    def test_multi_call_order_independent(self):
        exp = [
            {"name": "HassTurnOff", "arguments": {"domain": ["light"]}},
            {"name": "HassTurnOn", "arguments": {"name": "Front Door Lock", "domain": ["lock"]}},
        ]
        act = [
            {"name": "HassTurnOn", "arguments": {"name": "Front Door Lock", "domain": ["lock"]}},
            {"name": "HassTurnOff", "arguments": {"domain": ["light"]}},
        ]
        assert _check_arguments(exp, act) == C


class TestCallCount:
    def test_match(self):
        assert _check_call_count([{"name": "A"}], [{"name": "B"}]) == C

    def test_mismatch(self):
        assert _check_call_count([{"name": "A"}], []) == I

    def test_both_empty(self):
        assert _check_call_count([], []) == C


class TestResponseType:
    def test_action_done_with_calls(self):
        assert _check_response_type("action_done", [{"name": "X"}], [{"name": "Y"}]) == C

    def test_action_done_no_calls(self):
        assert _check_response_type("action_done", [{"name": "X"}], []) == I

    def test_error_no_calls(self):
        assert _check_response_type("error", [], []) == C

    def test_error_with_calls(self):
        assert _check_response_type("error", [], [{"name": "X"}]) == I

    def test_clarification_no_calls(self):
        assert _check_response_type("clarification", [], []) == C

    def test_query_with_get_state(self):
        assert _check_response_type("query_response", [{}], [{"name": "HassGetState"}]) == C

    def test_query_with_get_time(self):
        assert _check_response_type("query_response", [{}], [{"name": "HassGetCurrentTime"}]) == C

    def test_text_response_no_calls(self):
        assert _check_response_type("text_response", [], []) == C

    def test_text_response_with_calls(self):
        assert _check_response_type("text_response", [], [{"name": "X"}]) == I


class TestFormatValidity:
    def test_valid(self):
        assert _check_format_validity([{"name": "X", "arguments": {}}]) == C

    def test_no_calls(self):
        assert _check_format_validity([]) == N

    def test_no_name(self):
        assert _check_format_validity([{"name": None}]) == I

    def test_unparseable_args(self):
        assert _check_format_validity([{"name": "X", "arguments": {"_raw": "bad"}}]) == I


class TestHallucinatedTools:
    def test_valid_tools(self):
        calls = [{"name": "HassTurnOn"}, {"name": "HassTurnOff"}]
        assert _check_no_hallucinated_tools(calls) == C

    def test_hallucinated(self):
        calls = [{"name": "MadeUpTool"}]
        assert _check_no_hallucinated_tools(calls) == I

    def test_no_calls(self):
        assert _check_no_hallucinated_tools([]) == N


class TestToolCallMatches:
    def test_name_mismatch(self):
        assert not _tool_call_matches({"name": "A"}, {"name": "B"})

    def test_no_arg_constraints(self):
        assert _tool_call_matches({"name": "A", "arguments": {}}, {"name": "A", "arguments": {"extra": "val"}})

    def test_numeric_tolerance(self):
        exp = {"name": "HassLightSet", "arguments": {"brightness": 75}}
        act = {"name": "HassLightSet", "arguments": {"brightness": 75.0}}
        assert _tool_call_matches(exp, act)

    def test_list_args_order_independent(self):
        exp = {"name": "HassTurnOn", "arguments": {"domain": ["light", "switch"]}}
        act = {"name": "HassTurnOn", "arguments": {"domain": ["switch", "light"]}}
        assert _tool_call_matches(exp, act)
