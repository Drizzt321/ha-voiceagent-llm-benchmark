#!/usr/bin/env python3
"""
Filter inventory YAML files to produce smaller tier inventories by subtraction.

Reads per-domain YAML files from a source tier directory and writes filtered
versions to the target tier directory, keeping only entities whose entity_id
appears in the keep-list. Preserves exact formatting, comments, and whitespace
from the source files.

This is a mechanical tool — the judgment is in building the keep-list, not here.
The script handles extraction so the LLM (or human) can focus on *which* entities
to keep and why.

Usage:
    python3 filter_inventory.py <tier_name> <keep_list_file> <source_dir> <target_dir>
    
    tier_name:       Name for headers (e.g., "large", "medium", "small")
    keep_list_file:  Text file with one entity_id per line (# comments and blank lines ok)
    source_dir:      Directory containing source tier YAML files
    target_dir:      Directory to write filtered YAML files

Example:
    python3 filter_inventory.py large large_keep.txt enormous/ large/
    python3 filter_inventory.py medium medium_keep.txt large/ medium/

Notes:
    - Does NOT use a YAML parser — preserves exact formatting via regex splitting
    - Updates file headers with tier name and entity count
    - Reports any keep-list entity_ids not found in source (likely typos)
    - Skips domains with no entities in the keep-list (no empty files created)
    - Does NOT handle re-area — apply those fixes after running this script
"""

import sys
import os
import re
from pathlib import Path


def filter_domain_file(source_path, keep_ids, target_path, tier_name):
    """Filter a single domain YAML file to keep only entities in keep_ids."""
    
    with open(source_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # Find header (everything before 'entities:' line)
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip() == 'entities:':
            header_end = i + 1
            break
    
    header = lines[:header_end]
    entity_text = '\n'.join(lines[header_end:])
    
    # Split into entity blocks — each starts with '  - entity_id:'
    blocks = re.split(r'\n(?=  - entity_id:)', entity_text)
    
    kept_blocks = []
    kept_count = 0
    
    for block in blocks:
        match = re.search(r'- entity_id:\s*(\S+)', block)
        if match:
            eid = match.group(1)
            if eid in keep_ids:
                kept_blocks.append(block)
                kept_count += 1
    
    if kept_count == 0:
        return 0
    
    # Update header with tier info
    domain = source_path.stem
    new_header = []
    for line in header:
        if re.match(r'^# .+ domain entities for \w+ inventory', line):
            domain_display = domain.replace("_", " ").title()
            new_header.append(f'# {domain_display} domain entities for {tier_name.capitalize()} inventory')
        elif re.match(r'^# ~?\d+ entities', line):
            new_header.append(f'# {kept_count} entities (derived from Enormous)')
        else:
            new_header.append(line)
    
    output = '\n'.join(new_header) + '\n'
    output += '\n'.join(kept_blocks)
    if not output.endswith('\n'):
        output += '\n'
    
    with open(target_path, 'w') as f:
        f.write(output)
    
    return kept_count


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <tier_name> <keep_list_file> <source_dir> <target_dir>")
        sys.exit(1)
    
    tier_name = sys.argv[1]
    keep_list_file = sys.argv[2]
    source_dir = Path(sys.argv[3])
    target_dir = Path(sys.argv[4])
    
    # Read keep list
    keep_ids = set()
    with open(keep_list_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                keep_ids.add(line)
    
    print(f"Tier: {tier_name}")
    print(f"Keep list: {len(keep_ids)} entities")
    print(f"Source: {source_dir}")
    print(f"Target: {target_dir}")
    print()
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    total_kept = 0
    
    for source_file in sorted(source_dir.glob('*.yaml')):
        if source_file.name == 'areas.yaml':
            continue
        
        domain = source_file.stem
        domain_keep = {eid for eid in keep_ids if eid.startswith(f'{domain}.')}
        
        if not domain_keep:
            print(f"  {domain}: SKIPPED (no entities in keep list)")
            continue
        
        target_file = target_dir / source_file.name
        count = filter_domain_file(source_file, domain_keep, target_file, tier_name)
        total_kept += count
        print(f"  {domain}: {count} entities kept")
    
    print(f"\nTotal: {total_kept} entities")
    
    # Report keep-list entries not found in source
    found_ids = set()
    for source_file in source_dir.glob('*.yaml'):
        if source_file.name == 'areas.yaml':
            continue
        with open(source_file, 'r') as f:
            for line in f:
                match = re.search(r'entity_id:\s*(\S+)', line)
                if match:
                    found_ids.add(match.group(1))
    
    missing = keep_ids - found_ids
    if missing:
        print(f"\nWARNING: {len(missing)} entity_ids in keep list not found in source:")
        for eid in sorted(missing):
            print(f"  {eid}")


if __name__ == '__main__':
    main()
