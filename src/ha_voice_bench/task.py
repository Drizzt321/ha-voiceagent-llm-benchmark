"""Inspect AI task definition for HA voice benchmarking."""

from inspect_ai import Task, task
from inspect_ai.scorer import match
from inspect_ai.solver import use_tools

from .dataset import load_ha_test_cases
from .solver import ha_voice_solver
from .tools import get_ha_intent_tools


@task
def ha_voice_benchmark(
    test_data: str = "sample_test_data/small_test_cases.ndjson",
    base_dir: str = ".",
    tool_tier: str = "mvp",
) -> Task:
    """HA voice intent benchmarking task.

    Args:
        test_data: Path to NDJSON test case file.
        base_dir: Base directory for resolving relative paths.
        tool_tier: Which tool set to expose — 'mvp' or 'full'.
    """
    return Task(
        dataset=load_ha_test_cases(test_data),
        solver=[
            use_tools(*get_ha_intent_tools(tool_tier)),
            ha_voice_solver(base_dir=base_dir),
        ],
        scorer=match(),  # PLACEHOLDER — replaced in Step 7
    )
