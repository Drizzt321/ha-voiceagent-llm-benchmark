# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

<!-- Describe what this project does, in 2-3 sentences. Include the main technologies, its purpose, and any notable patterns (e.g. actor model, event-driven, etc.). -->

[PROJECT DESCRIPTION]

---

## Commands

<!-- Pick the block matching your language stack and delete the rest. -->

### Python (uv + ruff + pyright + pytest/tox)

```sh
# Install dependencies
uv sync

# Run all tests and linters in isolated environments
tox

# Run tests only
pytest

# Run tests with coverage
pytest --cov

# Lint
ruff check .

# Format  (always run this before tox — tox checks format but won't auto-fix)
ruff format .

# Type check
pyright src/
```

<!-- Other language stacks: add a named block here with equivalent install / test / lint / format / typecheck commands. -->

---

## Architecture

<!-- Map the source tree to responsibilities. One bullet per file/module, stating: what it owns, key classes/functions, and any non-obvious invariants. -->

### Source: `src/<package>/`

- `__init__.py` — [Extension/entry-point class. What it registers. Config schema.]
- `[module].py` — [Responsibility, key class, thread-safety notes if relevant.]

### Tests: `tests/`

- `[test_file].py` — [What is tested, what is mocked.]
- `conftest.py` — [Shared fixtures and any module-level mocking (e.g. C extensions).]

---

## Code Quality

<!-- State the linter/formatter/type-checker and key configuration decisions. -->

### Python

- Ruff targets Python 3.13, enables ALL lint rules with specific exclusions (docstrings, logging
  f-strings, TODO author requirements, formatting conflicts).
- Tests have relaxed rules: `ANN`, `ARG`, `D`, `PLR2004`, `S101`, `S105`, `SLF001` ignored.
- Pyright in standard mode; `reportMissingTypeStubs` disabled for libraries lacking type stubs.
- pytest configured to fail on warnings from project source code (`filterwarnings = error`).

---

## Common Type Suppression Patterns

<!-- Document suppressions that are known-good and intentional so Claude doesn't try to "fix" them. -->

### Python

<!-- Example entries — replace with project-specific ones: -->
- Lazy imports in `setup()` / `on_start()` — use `# noqa: PLC0415`
- Class variables mistyped as instance vars in base class — use `# type: ignore[assignment]  # noqa: RUF012`
- Base class method with narrower return type than implementation — use `# type: ignore[override]`
- Third-party library with strict generic variance — use `# pyright: ignore[reportArgumentType]`

---

## Environment Notes

<!-- Anything true of the dev/runtime environment that isn't obvious from the code. -->

- Python >= 3.13
- Uses `uv` for dependency management.
- [Any system-level runtime dependencies, e.g. native libs, plugins.]
- [Any known version conflicts, e.g. "Library X requires setuptools<82".]
- Always check OS version at runtime (`cat /etc/os-release`) rather than inferring from training
  data — distro release names and stable/testing status change over time.

---

## Workflow Preferences

<!-- How Claude should behave in this repo. These are standing instructions. -->

### Do

- Read a file before proposing changes to it.
- Keep changes minimal and focused on the task. Do not refactor surrounding code unless asked.
- Prefer editing existing files over creating new ones.
- Write tests for new behavior. Mock external I/O (HTTP, WebSocket, filesystem).
- When a type suppression comment is needed, document *why* inline.
- On shutdown paths, ensure all resources (file descriptors, threads, connections) are closed in
  the correct order to avoid hangs or crashes.
- Consider error handling for scenarios that might be rare or unlikely; describe the scenario, your
  reasoning for not handling it, and let me decide whether to handle it.
- **When investigating an issue, surface any other bugs or improvement opportunities found along
  the way — even if unrelated to the original task. List them explicitly as candidates for a future
  fix list.**
- **Before reverting any changes, explicitly call it out: explain what will be reverted and why,
  and get confirmation before proceeding. Never silently revert as part of a larger change.**
- **After completing a plan or implementation, provide a summary table: file → description of what
  changed.**
- **At the end of a feature, milestone, or coding session, ask if I want to push commits to
  origin.**
- **When triaging issues, state both (a) the severity class (crash, race condition, memory leak,
  data loss, UX bug, etc.) and (b) the realistic exposure — how likely it is to be hit given
  actual usage patterns. A severe but near-impossible-to-trigger bug may rank below a moderate
  but common one. Always explain both dimensions explicitly.**
- Use `uv` for all Python dependency operations.

### Do Not

- Do not add docstrings, comments, or type annotations to code that wasn't changed.
- Do not create helpers or abstractions for one-time operations.
- Do not introduce backwards-compatibility shims unless explicitly asked.
- Do not commit or push unless explicitly instructed.
- Do not amend existing commits; create new ones when a pre-commit hook fails and must be retried.
- Do not use `--no-verify` or other hook-bypass flags.
- Do not force-push to `main` or `master`.
- Do not add emojis unless explicitly asked.

### Git Safety

- Stage specific files by name rather than `git add -A` or `git add .`.
- Treat merge conflicts as something to resolve, not discard.
- Investigate unexpected files/branches before deleting or overwriting them.

---

## Decisions Already Made

<!-- Prevent Claude from re-litigating past design decisions or offering unsolicited alternatives. -->

<!-- Example entries — replace with project-specific ones: -->
- [OAuth approach: e.g. HTTP callback, not device code or manual token pasting.]
- [URI naming conventions already settled: e.g. `scheme:home`, not `scheme:root`.]
- [Default view behaviour: what appears at root, sort order, etc.]
- [Threading model: which objects are actor-owned vs. module-level.]
