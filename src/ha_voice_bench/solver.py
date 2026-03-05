"""Solver for HA voice benchmarking — assembles prompt and generates.

The solver is responsible for:
1. Reading sample metadata to find the right inventory
2. Assembling the HA-format system prompt
3. Calling generate() to get the model's response

Tool definitions are set separately via use_tools() in the task.
generate(tool_calls="none") captures tool calls without executing them.
"""

from inspect_ai.model import ChatMessageSystem, GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, solver

from .prompt import build_system_prompt


@solver
def ha_voice_solver(
    inventory: str,
    base_dir: str = ".",
    instructions: str | None = None,
    timeout: int | None = None,
    attempt_timeout: int | None = None,
    max_retries: int | None = None,
) -> Solver:
    """Assemble HA-style prompt with entity inventory and generate.

    Args:
        inventory: Repo-relative path to the HA entities YAML for this run.
        base_dir: Base directory for resolving the inventory path.
            Should be the repo root when running from CLI.
        instructions: Custom instruction text. If None, the default HA prompt is used.
        timeout: Total request timeout in seconds (including retries).
        attempt_timeout: Per-attempt timeout in seconds; exceeded attempts are retried.
        max_retries: Maximum retry attempts after a failed/timed-out attempt.
    """
    generate_config = GenerateConfig(
        timeout=timeout,
        attempt_timeout=attempt_timeout,
        max_retries=max_retries,
    )

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        system_prompt = build_system_prompt(inventory, base_dir, instructions=instructions)

        state.messages.insert(0, ChatMessageSystem(content=system_prompt))

        state = await generate(state, tool_calls="none", config=generate_config)

        return state

    return solve
