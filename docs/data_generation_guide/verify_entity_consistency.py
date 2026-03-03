#!/usr/bin/env python3
"""
Verify entity_id consistency across inventory tiers and test case NDJSON files.

Two verification passes:
  1. YAML cross-tier: every entity in a smaller tier exists identically in all
     parent tiers (Small ⊂ Medium ⊂ Large ⊂ Enormous).
  2. NDJSON vs YAML: every target_entities value in Enormous seed NDJSON files
     exists in the corresponding Enormous YAML inventory.

Usage:
    python3 verify_entity_consistency.py <data_dir> [--output <output_dir>]

    <data_dir>     Path to the data directory containing enormous/, large/,
                   medium/, small/ subdirectories.
    --output       Where to write audit reports. Defaults to current directory.

Output:
    audit-yaml-cross-tier.md   — Cross-tier subset and identity verification
    audit-ndjson-entity-ids.md — NDJSON target_entities vs YAML verification

Exit codes:
    0 — All checks passed
    1 — Mismatches found (details in output files)
    2 — Script error (missing directories, parse failures, etc.)
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


# ──────────────────────────────────────────────────────────────
# YAML parsing
# ──────────────────────────────────────────────────────────────

def parse_yaml_inventory(yaml_path: Path) -> dict[str, dict]:
    """Parse a domain YAML file, return {entity_id: entity_dict}."""
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    if data is None or "entities" not in data:
        return {}

    entities = {}
    for entity in data["entities"]:
        eid = entity.get("entity_id")
        if eid:
            entities[eid] = entity
    return entities


def load_tier(tier_dir: Path) -> dict[str, dict]:
    """Load all YAML files in a tier directory, return {entity_id: entity_dict}."""
    all_entities = {}
    if not tier_dir.is_dir():
        return all_entities

    for yaml_file in sorted(tier_dir.glob("*.yaml")):
        # Skip areas.yaml — it has a different structure
        if yaml_file.name == "areas.yaml":
            continue
        try:
            entities = parse_yaml_inventory(yaml_file)
            all_entities.update(entities)
        except Exception as e:
            print(f"  WARNING: Failed to parse {yaml_file}: {e}", file=sys.stderr)

    return all_entities


# ──────────────────────────────────────────────────────────────
# NDJSON parsing
# ──────────────────────────────────────────────────────────────

def parse_ndjson_file(ndjson_path: Path) -> list[dict]:
    """Parse an NDJSON file, return list of test case dicts."""
    cases = []
    with open(ndjson_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(
                    f"  WARNING: {ndjson_path.name} line {line_num}: JSON parse error: {e}",
                    file=sys.stderr,
                )
    return cases


# ──────────────────────────────────────────────────────────────
# Pass 1: YAML cross-tier verification
# ──────────────────────────────────────────────────────────────

TIER_ORDER = ["enormous", "large", "medium", "small"]


def compare_entity_data(eid: str, child_entity: dict, parent_entity: dict) -> list[str]:
    """Compare entity fields between child and parent tier. Return list of diffs."""
    diffs = []
    for field in ("name", "domain", "state", "attributes"):
        child_val = child_entity.get(field)
        parent_val = parent_entity.get(field)
        if child_val != parent_val:
            diffs.append(f"  {field}: child={child_val!r} vs parent={parent_val!r}")

    # Area is allowed to differ (re-area rule), but flag it for awareness
    child_area = child_entity.get("area")
    parent_area = parent_entity.get("area")
    if child_area != parent_area:
        diffs.append(f"  area: child={child_area!r} vs parent={parent_area!r} (re-area — may be intentional)")

    return diffs


def verify_cross_tier(tiers: dict[str, dict[str, dict]]) -> tuple[list[str], int]:
    """
    Verify subset chain and data identity across tiers.
    Returns (report_lines, error_count).
    """
    lines = []
    errors = 0

    lines.append("# YAML Cross-Tier Entity Verification")
    lines.append("")
    lines.append("Verifies: Small ⊂ Medium ⊂ Large ⊂ Enormous")
    lines.append("For matching entities: name, domain, state, attributes must be identical.")
    lines.append("Area differences flagged but allowed (re-area rule).")
    lines.append("")

    # Summary table
    lines.append("## Tier Summary")
    lines.append("")
    lines.append("| Tier | Entities | YAML files |")
    lines.append("|------|----------|------------|")
    for tier_name in TIER_ORDER:
        entities = tiers.get(tier_name, {})
        tier_dir = data_dir / tier_name
        yaml_count = len([f for f in tier_dir.glob("*.yaml") if f.name != "areas.yaml"]) if tier_dir.is_dir() else 0
        lines.append(f"| {tier_name} | {len(entities)} | {yaml_count} |")
    lines.append("")

    # Domain breakdown per tier
    lines.append("## Domain Breakdown")
    lines.append("")
    for tier_name in TIER_ORDER:
        entities = tiers.get(tier_name, {})
        domain_counts = defaultdict(int)
        for eid in entities:
            domain = eid.split(".")[0] if "." in eid else "unknown"
            domain_counts[domain] += 1
        sorted_domains = sorted(domain_counts.items(), key=lambda x: -x[1])
        domain_str = ", ".join(f"{d}: {c}" for d, c in sorted_domains)
        lines.append(f"**{tier_name}** ({len(entities)} total): {domain_str}")
        lines.append("")

    # Subset verification — compare each pair
    lines.append("## Subset Verification")
    lines.append("")

    pairs = [
        ("small", "medium"),
        ("medium", "large"),
        ("large", "enormous"),
    ]

    for child_name, parent_name in pairs:
        child = tiers.get(child_name, {})
        parent = tiers.get(parent_name, {})

        lines.append(f"### {child_name} ⊂ {parent_name}")
        lines.append("")

        missing = []
        data_diffs = []
        re_areas = []

        for eid in sorted(child.keys()):
            if eid not in parent:
                missing.append(eid)
                errors += 1
            else:
                diffs = compare_entity_data(eid, child[eid], parent[eid])
                real_diffs = [d for d in diffs if "re-area" not in d]
                area_diffs = [d for d in diffs if "re-area" in d]

                if real_diffs:
                    data_diffs.append((eid, real_diffs))
                    errors += 1
                if area_diffs:
                    re_areas.append((eid, area_diffs))

        if not missing and not data_diffs:
            lines.append(f"✅ All {len(child)} entities in {child_name} exist in {parent_name} with identical data.")
        else:
            if missing:
                lines.append(f"❌ **{len(missing)} entities in {child_name} NOT FOUND in {parent_name}:**")
                for eid in missing:
                    lines.append(f"- `{eid}`")
            if data_diffs:
                lines.append(f"❌ **{len(data_diffs)} entities with data mismatches:**")
                for eid, diffs in data_diffs:
                    lines.append(f"- `{eid}`:")
                    for d in diffs:
                        lines.append(f"  {d}")

        if re_areas:
            lines.append("")
            lines.append(f"ℹ️ **{len(re_areas)} re-area'd entities** (expected per derivation-guide.md §4):")
            for eid, diffs in re_areas:
                for d in diffs:
                    lines.append(f"- `{eid}`: {d.strip()}")

        lines.append("")

    return lines, errors


# ──────────────────────────────────────────────────────────────
# Pass 2: NDJSON target_entities vs Enormous YAML
# ──────────────────────────────────────────────────────────────

def verify_ndjson_entities(enormous_dir: Path, enormous_entities: dict[str, dict]) -> tuple[list[str], int]:
    """
    Verify every target_entities value in Enormous NDJSON files exists in YAML.
    Also checks id/case_key encoding consistency.
    Returns (report_lines, error_count).
    """
    lines = []
    errors = 0

    lines.append("# NDJSON target_entities vs Enormous YAML Verification")
    lines.append("")
    lines.append("For each test case in Enormous NDJSON files, verifies that every")
    lines.append("`metadata.target_entities` value exists as an `entity_id` in the")
    lines.append("corresponding Enormous YAML inventory file.")
    lines.append("")

    # Build entity_id set for fast lookup
    valid_eids = set(enormous_entities.keys())

    ndjson_files = sorted(enormous_dir.glob("*_test_cases.ndjson"))
    if not ndjson_files:
        lines.append("⚠️ No NDJSON files found in enormous directory.")
        return lines, 0

    lines.append(f"Files scanned: {len(ndjson_files)}")
    lines.append("")

    total_cases = 0
    total_entities_checked = 0
    all_mismatches = []  # (file, case_id, bad_eid, closest_match)

    for ndjson_file in ndjson_files:
        cases = parse_ndjson_file(ndjson_file)
        file_mismatches = []

        for case in cases:
            total_cases += 1
            case_id = case.get("id", "<no id>")
            metadata = case.get("metadata", {})
            target_entities = metadata.get("target_entities", [])

            for eid in target_entities:
                total_entities_checked += 1
                if eid not in valid_eids:
                    # Try to find closest match
                    domain = eid.split(".")[0] if "." in eid else ""
                    candidates = [e for e in valid_eids if e.startswith(f"{domain}.")]
                    # Rank candidates by likelihood of being the intended entity.
                    # Priority 1: bad_eid is valid_eid + extra suffix (confabulation pattern)
                    # Priority 2: edit distance (catches typos, transpositions)
                    closest = _rank_suggestions(eid, candidates)

                    file_mismatches.append({
                        "case_id": case_id,
                        "bad_eid": eid,
                        "suggestions": closest[:3],
                        "case_key": metadata.get("case_key", ""),
                    })
                    errors += 1

        if file_mismatches:
            lines.append(f"### ❌ {ndjson_file.name} — {len(file_mismatches)} mismatches")
            lines.append("")
            lines.append("| Case ID | Bad `target_entities` | Likely correct | case_key |")
            lines.append("|---------|----------------------|----------------|----------|")
            for m in file_mismatches:
                suggestions = ", ".join(f"`{s}`" for s in m["suggestions"]) if m["suggestions"] else "_(no close match)_"
                lines.append(f"| `{m['case_id']}` | `{m['bad_eid']}` | {suggestions} | `{m['case_key']}` |")
            lines.append("")
            all_mismatches.extend([(ndjson_file.name, m) for m in file_mismatches])
        else:
            lines.append(f"### ✅ {ndjson_file.name} — {len(cases)} cases, all target_entities valid")
            lines.append("")

    # ID/case_key encoding check
    lines.append("---")
    lines.append("")
    lines.append("## ID and case_key Encoding Check")
    lines.append("")
    lines.append("Verifies that `id` and `case_key` fields don't contain the erroneous")
    lines.append("entity_id forms (i.e., they use the short form matching the YAML).")
    lines.append("")

    id_issues = []
    for ndjson_file in ndjson_files:
        cases = parse_ndjson_file(ndjson_file)
        for case in cases:
            case_id = case.get("id", "")
            case_key = case.get("metadata", {}).get("case_key", "")
            target_entities = case.get("metadata", {}).get("target_entities", [])

            for eid in target_entities:
                if eid not in valid_eids:
                    # Check if the bad entity_id form leaked into id or case_key
                    # Extract the part after "domain." for comparison
                    bad_suffix = eid.split(".", 1)[1] if "." in eid else eid
                    domain = eid.split(".")[0]

                    # Find what the correct suffix should be
                    candidates = [e for e in valid_eids if e.startswith(f"{domain}.")]
                    for candidate in candidates:
                        correct_suffix = candidate.split(".", 1)[1]
                        # If bad_suffix starts with correct_suffix (e.g., front_door_lock starts with front_door)
                        if bad_suffix.startswith(correct_suffix) and bad_suffix != correct_suffix:
                            extra = bad_suffix[len(correct_suffix):]
                            # Check if this extra part appears in id or case_key
                            if extra in case_id or extra in case_key:
                                id_issues.append({
                                    "file": ndjson_file.name,
                                    "case_id": case_id,
                                    "case_key": case_key,
                                    "bad_eid": eid,
                                    "correct_eid": candidate,
                                    "extra_suffix": extra,
                                })

    if id_issues:
        lines.append(f"❌ **{len(id_issues)} id/case_key encoding issues found:**")
        lines.append("")
        for issue in id_issues:
            lines.append(f"- `{issue['case_id']}`: extra suffix `{issue['extra_suffix']}` from `{issue['bad_eid']}` (should be `{issue['correct_eid']}`)")
    else:
        lines.append("✅ No id/case_key encoding issues — bad entity_id forms did not leak into id or case_key fields.")

    # Summary
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- NDJSON files scanned: {len(ndjson_files)}")
    lines.append(f"- Total test cases: {total_cases}")
    lines.append(f"- Total target_entities checked: {total_entities_checked}")
    lines.append(f"- Mismatches found: {errors}")
    if all_mismatches:
        lines.append("")
        lines.append("### Fix list (copy-paste ready)")
        lines.append("")
        lines.append("Each line: `file | case_id | wrong_eid → suggested_correct_eid`")
        lines.append("")
        lines.append("```")
        for fname, m in all_mismatches:
            suggestion = m["suggestions"][0] if m["suggestions"] else "???"
            lines.append(f"{fname} | {m['case_id']} | {m['bad_eid']} → {suggestion}")
        lines.append("```")

    return lines, errors


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _rank_suggestions(bad_eid: str, candidates: list[str]) -> list[str]:
    """Rank candidate entity_ids by likelihood of being the intended match.

    Scoring (lower = better match):
      - Superstring match (bad_eid starts with candidate): score 0 + suffix length.
        This catches the most common confabulation pattern where an LLM appends
        the domain name as an extra suffix (e.g., lock.front_door_lock for
        lock.front_door). Shorter extra suffix = more likely match.
      - Edit distance: score 100 + distance. Catches typos and transpositions
        but ranks below superstring matches.
    """
    scored = []
    for candidate in candidates:
        if bad_eid.startswith(candidate):
            # Superstring: bad_eid = candidate + extra suffix
            extra = len(bad_eid) - len(candidate)
            scored.append((extra, candidate))  # shorter suffix = better
        elif candidate.startswith(bad_eid):
            # Substring: candidate is longer (less common but possible)
            extra = len(candidate) - len(bad_eid)
            scored.append((50 + extra, candidate))
        else:
            dist = _edit_distance(bad_eid, candidate)
            scored.append((100 + dist, candidate))

    scored.sort(key=lambda x: x[0])
    return [candidate for _, candidate in scored[:3]]


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify entity_id consistency across inventory tiers and NDJSON test cases."
    )
    parser.add_argument("data_dir", type=Path, help="Path to data/ directory")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output directory for audit reports (default: data_dir parent)"
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    output_dir = (args.output or data_dir.parent).resolve()

    if not data_dir.is_dir():
        print(f"ERROR: {data_dir} is not a directory", file=sys.stderr)
        sys.exit(2)

    print(f"Data directory: {data_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Load all tiers
    print("Loading tiers...")
    tiers = {}
    for tier_name in TIER_ORDER:
        tier_dir = data_dir / tier_name
        if tier_dir.is_dir():
            tiers[tier_name] = load_tier(tier_dir)
            print(f"  {tier_name}: {len(tiers[tier_name])} entities")
        else:
            print(f"  {tier_name}: directory not found, skipping")
            tiers[tier_name] = {}
    print()

    total_errors = 0

    # Pass 1: YAML cross-tier
    print("Pass 1: YAML cross-tier verification...")
    yaml_lines, yaml_errors = verify_cross_tier(tiers)
    total_errors += yaml_errors

    yaml_report = output_dir / "audit-yaml-cross-tier.md"
    with open(yaml_report, "w") as f:
        f.write("\n".join(yaml_lines) + "\n")
    print(f"  → {yaml_report} ({yaml_errors} errors)")
    print()

    # Pass 2: NDJSON vs Enormous YAML
    print("Pass 2: NDJSON target_entities vs Enormous YAML...")
    enormous_dir = data_dir / "enormous"
    ndjson_lines, ndjson_errors = verify_ndjson_entities(enormous_dir, tiers.get("enormous", {}))
    total_errors += ndjson_errors

    ndjson_report = output_dir / "audit-ndjson-entity-ids.md"
    with open(ndjson_report, "w") as f:
        f.write("\n".join(ndjson_lines) + "\n")
    print(f"  → {ndjson_report} ({ndjson_errors} errors)")
    print()

    # Final summary
    if total_errors == 0:
        print("✅ All checks passed.")
        sys.exit(0)
    else:
        print(f"❌ {total_errors} total errors found. See audit reports for details.")
        sys.exit(1)
