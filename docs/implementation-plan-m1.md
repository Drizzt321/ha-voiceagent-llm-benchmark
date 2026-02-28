# Detailed Implementation Plan — Milestone 1

**Date:** 2026-02-28
**Status:** Ready for implementation
**Scope:** Milestone 1 (MVP) — Steps 1-8

> **⚠ Updates since original draft:**
> - Step 2 uses `uv sync` (not `python3 -m venv` + `pip`). Install: `uv sync --extra dev`. pyproject.toml uses hatchling build backend.
> - `requires-python = ">=3.13"` (environment is 3.13.5; original plan said `>=3.11`).
> - MVP tool count expanded from 7 → 11 (added HassGetCurrentTime, HassGetCurrentDate,
>   HassGetWeather, HassNevermind for utility/conversational test coverage)
> - New `text_response` response type added for general knowledge and conversational
>   cases where the model should answer in plain text without tool calls
> - `VALID_TOOL_NAMES` in scorer must include the 4 new tools
> - `_check_response_type()` needs a `text_response` branch (zero tool calls + non-empty text)
> - `query_response` check updated to also accept HassGetCurrentTime, HassGetCurrentDate
> - Test case count expanded from 10 → 25 (15 utility/conversational/knowledge cases added)
> - See `test-data-format.md` and `scoring-design.md` for updated schemas
>
> The code sketches below reflect the original 7-tool design. Implementers should
> incorporate the above changes during implementation.

---

