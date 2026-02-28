"""Dataset loader for HA voice benchmarking test cases."""

import json
from pathlib import Path

from inspect_ai.dataset import Dataset, MemoryDataset, Sample

REQUIRED_FIELDS = {
    "id",
    "utterance",
    "expected_tool_calls",
    "expected_response_type",
    "inventory_tier",
    "inventory_file",
}


def load_ha_test_cases(
    file_path: str | Path,
    inventory_tier: str | None = None,
) -> Dataset:
    """Load HA voice test cases from an NDJSON file.

    Args:
        file_path: Path to the NDJSON test case file.
        inventory_tier: Optional filter — only load cases matching this tier.

    Returns:
        Inspect Dataset of Sample objects.

    Raises:
        FileNotFoundError: If file_path doesn't exist.
        ValueError: On malformed JSON, missing required fields, or empty result set.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Test case file not found: {file_path}")

    samples = []
    with open(file_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                case = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num} of {file_path}: {e}")

            missing = REQUIRED_FIELDS - set(case.keys())
            if missing:
                raise ValueError(f"Missing fields {missing} on line {line_num} of {file_path}")

            if inventory_tier and case["inventory_tier"] != inventory_tier:
                continue

            metadata: dict = {
                "inventory_tier": case["inventory_tier"],
                "inventory_file": case["inventory_file"],
                "expected_response_type": case["expected_response_type"],
            }
            if "alternative_expected_tool_calls" in case:
                metadata["alternative_expected_tool_calls"] = json.dumps(
                    case["alternative_expected_tool_calls"]
                )
            if "metadata" in case and isinstance(case["metadata"], dict):
                for k, v in case["metadata"].items():
                    metadata[f"meta/{k}"] = v

            samples.append(
                Sample(
                    id=case["id"],
                    input=case["utterance"],
                    target=json.dumps(case["expected_tool_calls"]),
                    metadata=metadata,
                )
            )

    if not samples:
        tier_msg = f" (filter: tier={inventory_tier})" if inventory_tier else ""
        raise ValueError(f"No test cases loaded from {file_path}{tier_msg}")

    return MemoryDataset(samples=samples, name=f"ha-voice-{file_path.stem}")
