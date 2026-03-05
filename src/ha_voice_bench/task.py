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
    test_cases: str = "sample_test_data/small-test-cases.ndjson",
    inventory: str = "sample_test_data/small-ha-entities.yaml",
    base_dir: str = ".",
    instructions_file: str = "",
) -> Task:
    """HA voice intent benchmarking task.

    Args:
        test_cases: Path to NDJSON test case file (resolved relative to base_dir).
        inventory: Path to the HA entities YAML for this run (resolved relative to base_dir).
        base_dir: Base directory for resolving relative paths (relative paths are
            anchored to the repo root, not CWD, to survive Inspect's module loading).
        instructions_file: Optional repo-relative path to a plain-text file containing
            custom system prompt instructions. If empty, the default HA prompt is used.
    """
    instructions: str | None = None
    if instructions_file:
        instructions = (_REPO_ROOT / instructions_file).read_text()

    return Task(
        dataset=load_ha_test_cases(_resolve(base_dir, test_cases)),
        solver=[
            use_tools(*get_ha_intent_tools()),
            ha_voice_solver(
                inventory=str(_resolve(base_dir, inventory)),
                base_dir=str(_resolve(base_dir, "")),
                instructions=instructions,
            ),
        ],
        scorer=tool_call_scorer(),
    )
