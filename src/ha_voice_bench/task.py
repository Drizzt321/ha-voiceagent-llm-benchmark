"""Inspect AI task definition for HA voice benchmarking."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import use_tools

from ha_voice_bench.dataset import load_ha_test_cases
from ha_voice_bench.scorers.tool_call import tool_call_scorer
from ha_voice_bench.solver import ha_voice_solver
from ha_voice_bench.tools import get_ha_intent_tools

# Inspect may change CWD when loading task files, so anchor relative paths to
# the repo root (three levels above src/ha_voice_bench/task.py) rather than CWD.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(base_dir: str, rel_path: str) -> Path:
    """Resolve rel_path under base_dir, anchoring relative base_dirs to the repo root."""
    base = Path(base_dir) if Path(base_dir).is_absolute() else _REPO_ROOT / base_dir
    return base / rel_path


@task
def ha_voice_benchmark(
    test_data: str = "sample_test_data/small_test_cases.ndjson",
    base_dir: str = ".",
    tool_tier: str = "mvp",
) -> Task:
    """HA voice intent benchmarking task.

    Args:
        test_data: Path to NDJSON test case file (resolved relative to base_dir).
        base_dir: Base directory for resolving relative paths (relative paths are
            anchored to the repo root, not CWD, to survive Inspect's module loading).
        tool_tier: Which tool set to expose — 'mvp' or 'full'.
    """
    return Task(
        dataset=load_ha_test_cases(_resolve(base_dir, test_data)),
        solver=[
            use_tools(*get_ha_intent_tools(tool_tier)),
            ha_voice_solver(base_dir=str(_resolve(base_dir, ""))),
        ],
        scorer=tool_call_scorer(),
    )
