#!/usr/bin/env python3
"""Assemble per-tier benchmark dataset files for the HA voice benchmark.

Reads per-domain source files and writes two output files ready for the
Inspect AI benchmark pipeline:

  test_data/{tier}-ha-entities.yaml    — merged inventory (areas + entities)
  test_data/{tier}-test-cases.ndjson   — merged test cases

Usage:
    uv run scripts/assemble_tier.py --tier enormous
    uv run scripts/assemble_tier.py --tier large --domains light,lock,climate
    uv run scripts/assemble_tier.py --tier enormous --validate

Inclusion rules for test cases:
  - Domain-specific cases: included when their source domain file is selected.
  - Cross-domain cases (inventory_tier != "all"): included when ALL target
    entity domains appear in the selected domain set. Cross-domain cases
    with no target_entities are included unconditionally.
  - All-tier cases (inventory_tier == "all"): always included regardless of
    --domains. These are inventory-independent (utility, conversational,
    out-of-scope) and may have empty target_entities intentionally.

Validation (--validate):
  Cross-checks target_entities and target_areas in test case metadata
  against the assembled inventory. Reports unresolved references and
  exits non-zero.

  Intentionally skipped during validation:
  - Cases with inventory_tier == "all": inventory-independent by design;
    empty target_entities is expected and normal for these cases.
  - Cases with absent or empty target_entities / target_areas: no
    constraint to validate (e.g. general-knowledge or conversational).

---

FUTURE — Inspect Pipeline Changes
==================================
When hooking these assembled files into the Inspect pipeline, the following
source files need updating. Do NOT make these changes until the assembled
files are verified against a live benchmark run.

task.py:
  - Rename 'test_data' param → 'test_cases' (path to NDJSON).
  - Add 'inventory' param (path to HA entities YAML).
  - CLI invocation becomes:
      -T test_cases=test_data/small-test-cases.ndjson
      -T inventory=test_data/small-ha-entities.yaml
  - Pass both paths down to load_ha_test_cases() and ha_voice_solver().

dataset.py (load_ha_test_cases):
  - Remove "inventory_file" from REQUIRED_FIELDS once the pipeline no
    longer reads it from per-sample metadata.
  - Stop storing inventory_file in sample metadata (solver gets it from
    the task-level 'inventory' param instead).
  - Optional load-time compatibility validation: cross-check each case's
    metadata.target_entities against the loaded inventory entity list.
    Edge cases to skip:
      * inventory_tier == "all": inventory-independent; target_entities
        is intentionally empty for utility/conversational/OOS cases.
      * No target_entities field in metadata: treat as no constraint
        (older format or general-knowledge cases without entity refs).

solver.py (ha_voice_solver):
  - Accept inventory path as a constructor param rather than reading
    state.metadata["inventory_file"] per sample.
  - New signature: ha_voice_solver(inventory: str, base_dir: str = ".")
  - The inventory can be loaded (and cached) at solver construction
    rather than once per sample.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEST_DATA = _REPO_ROOT / "test_data"
_INVENTORIES = _TEST_DATA / "inventories"
_TEST_CASES = _TEST_DATA / "test_cases"

_KNOWN_DOMAINS: frozenset[str] = frozenset({
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "lawn_mower",
    "light",
    "lock",
    "media_player",
    "sensor",
    "switch",
    "todo",
    "vacuum",
    "valve",
    "weather",
})


def _load_areas(tier_inv_dir: Path) -> list[dict]:
    path = tier_inv_dir / "areas.yaml"
    if not path.exists():
        sys.exit(f"Error: areas.yaml not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("areas", [])


def _load_domain_entities(tier_inv_dir: Path, domains: set[str]) -> list[dict]:
    entities: list[dict] = []
    for domain in sorted(domains):
        domain_path = tier_inv_dir / f"{domain}.yaml"
        if not domain_path.exists():
            continue
        with open(domain_path) as f:
            data = yaml.safe_load(f)
        entities.extend(data.get("entities", []))
    return entities


def _filter_areas_to_active(areas: list[dict], entities: list[dict]) -> list[dict]:
    """Return only areas referenced by at least one entity."""
    used_area_ids = {e.get("area") for e in entities if e.get("area")}
    return [a for a in areas if a.get("id") in used_area_ids]


def _load_ndjson(path: Path) -> list[dict]:
    cases: list[dict] = []
    with open(path) as f:
        for line_num, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                cases.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                sys.exit(f"Error: invalid JSON on line {line_num} of {path}: {exc}")
    return cases


def _entity_domains(entity_ids: list[str]) -> set[str]:
    """Extract domain prefixes from a list of HA entity IDs."""
    return {eid.split(".")[0] for eid in entity_ids if "." in eid}


def _collect_test_cases(
    tier_tc_dir: Path,
    domains: set[str],
) -> list[dict]:
    """Merge test cases from per-domain and cross-domain NDJSON files.

    Three-pass collection to maintain a clean inclusion hierarchy:

    Pass 1 — Domain-specific files:
        {domain}_test_cases.ndjson for each selected domain.
        Skips lines with inventory_tier == "all" (handled in pass 3).

    Pass 2 — Cross-domain file:
        cross_domain_test_cases.ndjson. A cross-domain case is included
        only when ALL domains of its target_entities are in the selected
        set. Cases with no target_entities are included unconditionally.
        Skips "all"-tier lines (handled in pass 3).

    Pass 3 — All-tier cases:
        Scans every *.ndjson in the tier directory for lines with
        inventory_tier == "all". Included unconditionally regardless of
        --domains. Deduplication via seen_ids handles any files that mix
        "all"-tier lines alongside domain-specific ones.
    """
    seen_ids: set[str] = set()
    cases: list[dict] = []

    def _add(case: dict) -> None:
        if case["id"] not in seen_ids:
            seen_ids.add(case["id"])
            cases.append(case)

    # Pass 1: domain-specific files
    for domain in sorted(domains):
        tc_path = tier_tc_dir / f"{domain}_test_cases.ndjson"
        if not tc_path.exists():
            continue
        for case in _load_ndjson(tc_path):
            if case.get("inventory_tier") != "all":
                _add(case)

    # Pass 2: cross-domain file
    cross_path = tier_tc_dir / "cross_domain_test_cases.ndjson"
    if cross_path.exists():
        for case in _load_ndjson(cross_path):
            if case.get("inventory_tier") == "all":
                continue  # collected in pass 3
            target_entities = case.get("metadata", {}).get("target_entities", [])
            target_domains = _entity_domains(target_entities)
            if target_domains and not target_domains.issubset(domains):
                continue  # references a domain outside the selected set
            _add(case)

    # Pass 3: all-tier cases from every file in the tier directory
    for ndjson_path in sorted(tier_tc_dir.glob("*.ndjson")):
        for case in _load_ndjson(ndjson_path):
            if case.get("inventory_tier") == "all":
                _add(case)

    return cases


def _validate(
    cases: list[dict],
    entity_ids: set[str],
    area_names: set[str],
) -> list[str]:
    """Return warning strings for unresolved entity/area references.

    Skips:
    - Cases with inventory_tier == "all" (inventory-independent by design).
    - Cases with absent or empty target_entities / target_areas.
    """
    warnings: list[str] = []
    for case in cases:
        if case.get("inventory_tier") == "all":
            continue
        cid = case["id"]
        meta = case.get("metadata", {})
        for eid in meta.get("target_entities", []):
            if eid not in entity_ids:
                warnings.append(f"  [{cid}] target entity not in inventory: {eid!r}")
        for area_name in meta.get("target_areas", []):
            if area_name not in area_names:
                warnings.append(f"  [{cid}] target area not in inventory: {area_name!r}")
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble tier-level inventory and test case files for the HA voice benchmark.\n\n"
            "Reads per-domain source files from BASE_DIR/inventories/{tier}/ and\n"
            "BASE_DIR/test_cases/{tier}/, then writes two output files to BASE_DIR:\n"
            "  {tier}-ha-entities.yaml   — merged inventory (areas + entities)\n"
            "  {tier}-test-cases.ndjson  — merged test cases\n\n"
            "Example:\n"
            "  uv run scripts/assemble_tier.py --base-dir test_data/ --tier enormous\n"
            "  uv run scripts/assemble_tier.py --base-dir test_data/ --tier large "
            "--domains light,lock,climate\n"
            "  uv run scripts/assemble_tier.py --base-dir test_data/ --tier enormous --validate"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-dir",
        required=True,
        metavar="DIR",
        help=(
            "Base data directory. Must contain inventories/{tier}/ and "
            "test_cases/{tier}/ subdirectories. Output files are written "
            "to this directory as {tier}-ha-entities.yaml and "
            "{tier}-test-cases.ndjson. Example: test_data/"
        ),
    )
    parser.add_argument(
        "--tier",
        required=True,
        metavar="TIER",
        help=(
            "Tier name to assemble (e.g. enormous, large, medium, small, or any custom "
            "name). Determines the source subdirectory under BASE_DIR/inventories/ and "
            "BASE_DIR/test_cases/, and the output file name prefix."
        ),
    )
    parser.add_argument(
        "--domains",
        metavar="DOMAIN,...",
        help=(
            "Comma-separated subset of HA domains to include, e.g. light,lock,climate. "
            "When omitted, all domain YAML files found in the tier directory are included. "
            "Cross-domain test cases are included only when all their target domains are "
            "in the selected set. Inventory-independent (all-tier) cases are always included."
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "After assembling, cross-check every test case's target_entities and "
            "target_areas against the assembled inventory. Exits non-zero and prints "
            "a list of unresolved references if any are found. Inventory-independent "
            "cases (inventory_tier='all') and cases with no target_entities are skipped."
        ),
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    tier = args.tier
    inv_tier_dir = base_dir / "inventories" / tier
    tc_tier_dir = base_dir / "test_cases" / tier

    if not inv_tier_dir.exists():
        sys.exit(f"Error: inventory tier directory not found: {inv_tier_dir}")
    if not tc_tier_dir.exists():
        sys.exit(f"Error: test case tier directory not found: {tc_tier_dir}")

    # Resolve domain set
    if args.domains:
        domains: set[str] = set(args.domains.split(","))
        unknown = domains - _KNOWN_DOMAINS
        if unknown:
            sys.exit(f"Error: unknown domains: {', '.join(sorted(unknown))}")
        include_all_domains = False
    else:
        domains = {
            f.stem
            for f in inv_tier_dir.glob("*.yaml")
            if f.stem != "areas" and f.stem in _KNOWN_DOMAINS
        }
        include_all_domains = True

    if not domains:
        sys.exit(f"Error: no domain YAML files found in {inv_tier_dir}")

    # Build inventory
    areas = _load_areas(inv_tier_dir)
    entities = _load_domain_entities(inv_tier_dir, domains)
    if not include_all_domains:
        areas = _filter_areas_to_active(areas, entities)

    # Collect test cases
    cases = _collect_test_cases(tc_tier_dir, domains)

    # Output paths
    inventory_out = base_dir / f"{tier}-ha-entities.yaml"
    test_cases_out = base_dir / f"{tier}-test-cases.ndjson"

    # Update inventory_file in every case to the repo-relative output path
    try:
        inventory_rel = str(inventory_out.relative_to(_REPO_ROOT))
    except ValueError:
        inventory_rel = str(inventory_out)  # base_dir is outside repo — use absolute path
    for case in cases:
        case["inventory_file"] = inventory_rel

    # Validate before writing (fail fast — don't produce output on error)
    if args.validate:
        entity_ids = {e["entity_id"] for e in entities}
        area_names = {a["name"] for a in areas}
        warnings = _validate(cases, entity_ids, area_names)
        if warnings:
            print(
                f"Validation failed — {len(warnings)} unresolved reference(s):",
                file=sys.stderr,
            )
            for w in warnings:
                print(w, file=sys.stderr)
            sys.exit(1)
        print(f"Validation passed — {len(cases)} test cases, {len(entities)} entities.")

    # Write inventory YAML
    with open(inventory_out, "w") as f:
        yaml.safe_dump(
            {"areas": areas, "entities": entities},
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    # Write test cases NDJSON
    with open(test_cases_out, "w") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(f"Wrote {len(entities):,} entities → {inventory_out}")
    print(f"Wrote {len(cases):,} test cases → {test_cases_out}")


if __name__ == "__main__":
    main()
