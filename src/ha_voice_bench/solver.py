"""Solver for HA voice benchmarking — assembles prompt and generates.

The solver is responsible for:
1. Reading sample metadata to find the right inventory
2. Assembling the HA-format system prompt
3. Calling generate() to get the model's response

Tool definitions are set separately via use_tools() in the task.
generate(tool_calls="none") captures tool calls without executing them.
"""

from inspect_ai.model import ChatMessageSystem
from inspect_ai.solver import Generate, Solver, TaskState, solver

from .prompt import build_system_prompt


@solver
def ha_voice_solver(
    inventory: str,
    base_dir: str = ".",
    instructions: str | None = None,
) -> Solver:
    """Assemble HA-style prompt with entity inventory and generate.

    Args:
        inventory: Repo-relative path to the HA entities YAML for this run.
        base_dir: Base directory for resolving the inventory path.
            Should be the repo root when running from CLI.
        instructions: Custom instruction text. If None, the default HA prompt is used.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        system_prompt = build_system_prompt(inventory, base_dir, instructions=instructions)

        state.messages.insert(0, ChatMessageSystem(content=system_prompt))

        state = await generate(state, tool_calls="none")

        return state

    return solve
