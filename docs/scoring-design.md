# Scoring Design

The benchmarking framework uses multi-dimensional scoring to provide detailed diagnostic information about model performance. Rather than a single pass/fail, each test case produces scores across several independent checks.

---

## Why Multi-Dimensional

A model that calls `HassTurnOn` instead of `HassLightSet` (wrong tool, right intent) is a different failure than one that calls `HassTurnOn` with `name: "Bathroom Light"` when the command was about the kitchen (right tool, wrong entity). A model that produces malformed JSON in the tool call arguments is different still.

Single-score benchmarks hide these distinctions. Multi-dimensional scoring exposes them, making it possible to:
- Identify systematic weaknesses (e.g., "this model struggles with area-based commands")
- Compare models on specific capabilities (e.g., "Model A is better at argument accuracy, Model B is better at tool selection")
- Track improvements across model versions on specific dimensions

---

## Tier 1 Scorer — Tool-Call Validation

The primary scorer. Compares the model's actual tool calls against expected tool calls from the test case.

### Score Dimensions

| Key | What It Checks | Values | When N/A |
|-----|---------------|--------|----------|
| `tool_name` | Correct intent tool(s) called | C / I | No expected calls (error/clarification case) |
| `args` | Arguments match expected values | C / I | No expected calls |
| `call_count` | Right number of tool calls | C / I | Never |
| `no_hallucinated_tools` | Only valid HA tools called | C / I | No actual calls |
| `format_valid` | Tool call is well-formed structured output | C / I | No actual calls |
| `response_type` | Correct handling mode | C / I | Unknown response type |

**C** = Correct, **I** = Incorrect, **N** = Not Applicable

`overall` (C/I) is derived: all applicable (non-N) dimensions must be C. It is the scalar `Score.value` used by `accuracy()` aggregation — not a separate dimension in the breakdown.

### Response Type Logic

| Expected Type | Model Should | Pass If |
|--------------|-------------|---------|
| `action_done` | Call action tool(s) | At least one tool call |
| `query_response` | Call a query tool | Called HassGetState, HassClimateGetTemperature, HassGetWeather, HassGetCurrentTime, or HassGetCurrentDate |
| `text_response` | Answer in plain text, no tool calls | Zero tool calls and non-empty text content |
| `error` | Refuse gracefully, no tool calls | Zero tool calls |
| `clarification` | Ask for more info, no tool calls | Zero tool calls |

### Valid Tool Names (MVP)

The `no_hallucinated_tools` check validates against the 11 MVP tools:

HassTurnOn, HassTurnOff, HassLightSet, HassSetPosition, HassGetState, HassClimateSetTemperature, HassClimateGetTemperature, HassGetCurrentTime, HassGetCurrentDate, HassGetWeather, HassNevermind.

This set expands as more intent tools are added in later milestones (the full HA inventory is 37 supported tools).

### Argument Matching

Arguments are compared with these rules:

1. **Case-insensitive string comparison** — `"Kitchen Light"` matches `"kitchen light"`
2. **`_any_of` flexible matching** — `name_any_of: ["Kitchen Light", "Kitchen Ceiling"]` accepts either value for the `name` argument
3. **Numeric tolerance** — Numbers match within ±0.01
4. **Array set comparison** — `["light"]` matches `["Light"]` (sorted, case-insensitive)
5. **Empty expected arguments** — No constraints; any arguments accepted
6. **Missing actual arguments** — If expected specifies a key and actual doesn't have it, that's a failure

### Multi-Call Matching

For test cases with multiple expected tool calls (e.g., "turn off the lights and lock the door"), matching is **order-independent**. The scorer finds the best permutation that satisfies all expected calls.

### Alternative Expected Call Sets

Some queries have more than one legitimately correct answer (e.g., `HassGetState` and `HassClimateGetTemperature` are both valid for "what's the temperature inside"). Test cases can specify a list of alternative acceptable call sets via `alternative_expected_tool_calls` in the NDJSON.

The scorer tries the primary `expected_tool_calls` first. If the primary fails, it iterates through each alternative set and scores C on the first match. The explanation notes which alternative was matched (e.g., `Checks (matched alternative 1):`). If no set matches, the sample scores I as usual.

See `test-data-format.md` for the field schema.

---

## Planned: Tier 2 Scorer — HA Compatibility

*Not yet implemented. Milestone 3.*

Validates that model responses would be accepted by HA's actual response parsing code. Catches responses that are semantically correct but would fail at the integration level.

**Checks:**
- `tool_call_id` present and non-empty
- `content` is null when `tool_calls` present
- `finish_reason` is `tool_calls` (not `stop`)
- `arguments` is valid JSON (not malformed string)
- Standard OpenAI tool-call structure followed

---

## Planned: Tier 3 Scorer — NL Quality

*Not yet implemented. Milestone 3.*

Uses an external LLM (Claude API) to evaluate the natural language response alongside tool calls. Scores brevity, naturalness, correctness, and whether error language appears in successful responses.

Runs as post-hoc re-scoring — not during the primary eval. Only scores samples that passed Tier 1.

---

## Interpreting Results

### In Inspect View

Each sample shows a C/I overall score (the `Score.value` scalar). The per-dimension breakdown is in the `explanation` field. Look for:
- **overall I** with `tool_name: C` — right tool, wrong arguments (common with area/entity confusion)
- **overall I** with `tool_name: I` — fundamentally wrong tool choice
- `format_valid: I` — model produced malformed tool calls (may indicate poor tool-calling fine-tuning)
- `no_hallucinated_tools: I` — model invented a tool that doesn't exist
- `response_type: I` — model called tools when it should have refused, or vice versa
- `Checks (matched alternative N):` in explanation — primary expected call failed but an alternative matched

### Across Configurations

Compare accuracy rates per dimension across model/quant/hardware configurations. Look for:
- Does quantization level affect argument accuracy more than tool selection?
- Does inventory size (entity count) degrade tool selection or argument accuracy first?
- Do CPU vs GPU runs produce different accuracy (they shouldn't, but verify)?

### Score Metadata

Each `Score` includes:
- `value` — Scalar C/I string (the `overall` result). Used by Inspect's `accuracy()` metric.
- `answer` — JSON array of actual tool calls (for debugging)
- `explanation` — Human-readable comparison of expected vs actual, with per-dimension C/I/N breakdown. Notes which alternative matched if applicable.
