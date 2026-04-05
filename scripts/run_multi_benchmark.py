#!/usr/bin/env python3
"""HA Voice Benchmark — Multi-config runner.

Runs a list of benchmark configs N times each (sequential), calling
run_benchmark.py for every repetition. Useful for generating averaged
comparison matrices across prompt variants or model sets.

Usage:
    uv run scripts/run_multi_benchmark.py configs/benchmark_test_1.yaml configs/benchmark_test_2.yaml --runs 3
    uv run scripts/run_multi_benchmark.py configs/benchmark_test_1.yaml configs/benchmark_test_2.yaml --runs 3 --dry-run
    uv run scripts/run_multi_benchmark.py configs/benchmark_test_1.yaml --runs 5 --no-warmup
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUN_SCRIPT = _REPO_ROOT / "scripts" / "run_benchmark.py"


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


def _print_plan(configs: list[Path], runs: int, passthrough: list[str]) -> None:
    total = len(configs) * runs
    print("=" * 60)
    print("HA Voice Benchmark — Multi-config run")
    print("=" * 60)
    print(f"Configs:      {len(configs)}")
    print(f"Runs each:    {runs}")
    print(f"Total runs:   {total}")
    if passthrough:
        print(f"Extra flags:  {' '.join(passthrough)}")
    print()
    print("Execution order:")
    i = 1
    for cfg in configs:
        for run_num in range(1, runs + 1):
            print(f"  [{i:>{len(str(total))}}] {cfg.name}  (run {run_num}/{runs})")
            i += 1
    print("=" * 60)


def _print_summary(
    results: list[tuple[Path, int, str, float | None]],
    total_wall: float,
) -> None:
    """Print a summary table of all runs."""
    print()
    print("=" * 60)
    print("Multi-run Complete")
    print("=" * 60)
    print(f"Total wall time: {_fmt_duration(total_wall)}")
    print()

    # Column widths
    name_w = max(len(p.name) for p, _, _, _ in results)
    name_w = max(name_w, 6)  # min "Config"

    completed = sum(1 for _, _, s, _ in results if s == "completed")
    failed = sum(1 for _, _, s, _ in results if s == "failed")
    interrupted = sum(1 for _, _, s, _ in results if s == "interrupted")
    print(f"Runs: {completed} completed, {failed} failed, {interrupted} interrupted")
    print()

    header = f"  {'Config':<{name_w}}  {'Run':>4}  {'Status':<13}  Wall time"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for cfg, run_num, status, wall in results:
        wall_s = _fmt_duration(wall) if wall is not None else "-"
        status_s = status.upper() if status != "completed" else "completed"
        print(f"  {cfg.name:<{name_w}}  {run_num:>4}  {status_s:<13}  {wall_s}")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "configs",
        nargs="+",
        metavar="CONFIG",
        help="One or more benchmark config YAML files to run.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        metavar="N",
        help="Number of times to run each config (default: 1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to each run_benchmark.py invocation and exit.",
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="Pass --no-warmup to each run_benchmark.py invocation.",
    )
    parser.add_argument(
        "--warmup-samples",
        type=int,
        metavar="N",
        help="Pass --warmup-samples N to each run_benchmark.py invocation.",
    )
    args = parser.parse_args()

    if args.runs < 1:
        sys.exit("--runs must be >= 1")

    configs = [Path(c).resolve() for c in args.configs]
    for cfg in configs:
        if not cfg.exists():
            sys.exit(f"Config file not found: {cfg}")

    # Build the passthrough flag list for run_benchmark.py
    passthrough: list[str] = []
    if args.dry_run:
        passthrough.append("--dry-run")
    if args.no_warmup:
        passthrough.append("--no-warmup")
    if args.warmup_samples is not None:
        passthrough += ["--warmup-samples", str(args.warmup_samples)]

    _print_plan(configs, args.runs, passthrough)

    if args.dry_run:
        print()
        print("Dry run — invoking run_benchmark.py --dry-run for each config.")
        print()

    results: list[tuple[Path, int, str, float | None]] = []
    total_start = time.monotonic()
    total = len(configs) * args.runs
    run_index = 0
    interrupted = False

    for cfg in configs:
        for run_num in range(1, args.runs + 1):
            run_index += 1
            print()
            print(f"[{run_index}/{total}] {cfg.name}  (run {run_num}/{args.runs})")
            print("-" * 60)

            cmd = ["uv", "run", "scripts/run_benchmark.py", str(cfg)] + passthrough
            run_start = time.monotonic()
            proc = None
            try:
                proc = subprocess.Popen(cmd, cwd=_REPO_ROOT, start_new_session=True)
                proc.wait()
                wall = time.monotonic() - run_start
                status = "completed" if proc.returncode == 0 else "failed"
                if proc.returncode != 0:
                    print(f"  run_benchmark.py exited with code {proc.returncode}")
            except KeyboardInterrupt:
                wall = time.monotonic() - run_start
                if proc is not None:
                    import os
                    import signal

                    try:
                        pgid = os.getpgid(proc.pid)
                        print(f"\n  Ctrl-C: killing process group {pgid}...")
                        os.killpg(pgid, signal.SIGTERM)
                        proc.wait(timeout=10)
                    except ProcessLookupError:
                        pass
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                results.append((cfg, run_num, "interrupted", wall))
                # Collect remaining as not-run
                remaining = [
                    (c, n)
                    for ci, c in enumerate(configs)
                    for n in range(1, args.runs + 1)
                    if ci * args.runs + n > run_index
                ]
                for rc, rn in remaining:
                    results.append((rc, rn, "not-run", None))
                interrupted = True
                break

            results.append((cfg, run_num, status, wall))

        if interrupted:
            break

    total_wall = time.monotonic() - total_start
    _print_summary(results, total_wall)

    if interrupted:
        sys.exit(1)

    any_failed = any(s in ("failed",) for _, _, s, _ in results)
    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
